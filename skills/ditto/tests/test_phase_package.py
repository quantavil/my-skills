"""Package analysis and MCP export import regressions."""
import json
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch
import warnings
import zipfile

HERE = Path(__file__).resolve().parent.parent / 'scripts'
sys.path.insert(0, str(HERE))

import phase_package  # noqa: E402
import phase_store as store  # noqa: E402


class PackageAnalysisTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='ditto-package-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.package = self.root / 'app.apk'
        self.members = {
            'AndroidManifest.xml': b'manifest',
            'res/drawable/icon.png': b'icon',
            'assets/config.json': b'{}',
            'lib/arm64-v8a/libapp.so': b'dart-aot',
            'classes.dex': b'dex',
        }
        self.write_zip(self.package, self.members)
        self.package_sha = store.sha256_file(self.package)
        self.receipts = {
            capability: self.receipt(capability)
            for capability in ('jadx', 'apktool', 'r2flutter')
        }
        self.preflight = {
            'schema_version': 1,
            'package_sha256': self.package_sha,
            'mcps': dict(self.receipts),
        }
        self.exports = {}
        for capability, receipt in self.receipts.items():
            directory = self.root / 'exports' / capability
            directory.mkdir(parents=True)
            (directory / 'receipt.json').write_text(json.dumps(receipt), encoding='utf-8')
            (directory / 'result.json').write_text(
                json.dumps({'capability': capability, 'finding': 'phase fact'}),
                encoding='utf-8')
            self.exports[capability] = directory

    @staticmethod
    def write_zip(path, members):
        with zipfile.ZipFile(path, 'w') as archive:
            for name, data in members.items():
                archive.writestr(name, data)

    def receipt(self, capability):
        data = {
            'schema_version': 1,
            'capability': capability,
            'server': f'{capability}-mcp-server',
            'tool': f'{capability}_analyze',
            'tool_version': '1.0.0',
            'session_id': f'session-{capability}',
            'target': {'package_sha256': self.package_sha},
            'status': 'healthy',
            'provenance': 'mcp',
        }
        if capability == 'r2flutter':
            data.update({'supported': True, 'abi': 'arm64-v8a', 'dart_profile': '3.9'})
        return data

    def analyze(self, destination=None):
        return phase_package.analyze_package(
            self.package, destination or self.root / 'original',
            ['AndroidManifest.xml', 'res/drawable/*', 'assets/*.json'],
            {'res/drawable/icon.png': ['log_top']}, self.exports, self.preflight)

    def test_analysis_writes_hashed_index_and_preserves_paths(self):
        result = self.analyze()
        destination = self.root / 'original'
        self.assertEqual(result['package_sha256'], self.package_sha)
        self.assertEqual(result['framework_inventory']['framework_guess'][0],
                         'Flutter AOT present (libapp.so or App.framework)')
        self.assertEqual(set(result['mcps']), set(self.receipts))
        retained = {item['source']: item for item in result['retained_files']}
        self.assertEqual(retained['res/drawable/icon.png']['checkpoints'], ['log_top'])
        self.assertTrue((destination / 'reverse.001/res/drawable/icon.png').is_file())
        self.assertTrue((destination / 'reverse.001/mcp/r2flutter/result.json').is_file())
        self.assertEqual(store.load_json(destination / 'reverse.001.json'), result)
        for item in result['retained_files']:
            self.assertEqual(store.sha256_file(destination / item['path']), item['sha256'])

    def test_requires_all_matching_mcp_exports(self):
        del self.exports['r2flutter']
        with self.assertRaisesRegex(store.PhaseError, 'missing MCP export'):
            self.analyze()

        self.setUp()
        receipt_path = self.exports['jadx'] / 'receipt.json'
        bad = json.loads(receipt_path.read_text())
        bad['provenance'] = 'cli'
        receipt_path.write_text(json.dumps(bad))
        with self.assertRaisesRegex(store.PhaseError, 'does not match active preflight'):
            self.analyze()

    def test_rejects_symlinked_mcp_export_directory(self):
        alias = self.root / 'jadx-alias'
        alias.symlink_to(self.exports['jadx'], target_is_directory=True)
        self.exports['jadx'] = alias
        with self.assertRaisesRegex(store.PhaseError, 'real directory'):
            self.analyze()

    def test_refuses_existing_output(self):
        self.analyze()
        with self.assertRaisesRegex(store.PhaseError, 'already exists'):
            self.analyze()

    def test_rejects_unsafe_duplicate_symlink_and_encrypted_members(self):
        unsafe = self.root / 'unsafe.apk'
        self.write_zip(unsafe, {'../escape': b'x'})
        cases = [('unsafe', unsafe)]

        duplicate = self.root / 'duplicate.apk'
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', UserWarning)
            with zipfile.ZipFile(duplicate, 'w') as archive:
                archive.writestr('assets/x', b'1')
                archive.writestr('assets/x', b'2')
        cases.append(('duplicate', duplicate))

        symlink = self.root / 'symlink.apk'
        with zipfile.ZipFile(symlink, 'w') as archive:
            info = zipfile.ZipInfo('assets/link')
            info.create_system = 3
            info.external_attr = (stat.S_IFLNK | 0o777) << 16
            archive.writestr(info, 'target')
        cases.append(('link', symlink))

        encrypted = self.root / 'encrypted.apk'
        self.write_zip(encrypted, {'assets/secret.json': b'x'})
        raw = bytearray(encrypted.read_bytes())
        local = raw.index(b'PK\x03\x04')
        central = raw.index(b'PK\x01\x02')
        raw[local + 6:local + 8] = (1).to_bytes(2, 'little')
        raw[central + 8:central + 10] = (1).to_bytes(2, 'little')
        encrypted.write_bytes(raw)
        cases.append(('encrypted', encrypted))

        for label, package in cases:
            with self.subTest(label=label):
                self.package = package
                with self.assertRaises(store.PhaseError):
                    self.analyze(self.root / f'out-{label}')

    def test_rejects_selection_over_size_limit(self):
        with patch.object(phase_package, 'MAX_SELECTED_BYTES', 3):
            with self.assertRaisesRegex(store.PhaseError, 'size limit'):
                self.analyze()


if __name__ == '__main__':
    unittest.main()
