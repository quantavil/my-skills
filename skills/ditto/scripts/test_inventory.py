"""Regression checks using synthetic archives, no mobile SDK required."""
import hashlib
import json
from pathlib import Path
import plistlib
import subprocess
import sys
import tempfile
import unittest
import zipfile

SCRIPT = Path(__file__).with_name('inventory.py')


class InventoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='ditto-test-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def archive(self, name, entries):
        path = self.root / name
        with zipfile.ZipFile(path, 'w') as archive:
            for member, data in entries:
                archive.writestr(member, data)
        return path

    def run_cli(self, path, *args):
        return subprocess.run([sys.executable, str(SCRIPT), str(path), *args],
                              capture_output=True, text=True)

    def report(self, path):
        result = self.run_cli(path)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_android_flutter_hash_and_space_path(self):
        path = self.archive('app with spaces.apk', [(name, b'test') for name in (
            'AndroidManifest.xml', 'classes.dex', 'lib/arm64-v8a/libapp.so',
            'lib/arm64-v8a/libflutter.so', 'assets/flutter_assets/icon.png')])
        data = self.report(path)
        self.assertEqual(data['sha256'], hashlib.sha256(path.read_bytes()).hexdigest())
        self.assertEqual(data['android_abis'], ['arm64-v8a'])
        self.assertEqual(data['indicators']['flutter_aot'], ['lib/arm64-v8a/libapp.so'])
        self.assertEqual(data['indicators']['dex'], ['classes.dex'])

    def test_output_refuses_overwrite(self):
        path = self.archive('app.apk', [('classes.dex', b'test')])
        output = self.root / 'nested' / 'inventory.json'
        self.assertEqual(self.run_cli(path, '--output', str(output)).returncode, 0)
        original = output.read_bytes()
        self.assertEqual(self.run_cli(path, '--output', str(output)).returncode, 2)
        self.assertEqual(output.read_bytes(), original)

    def test_binary_ios_plist(self):
        path = self.archive('app.ipa', [('Payload/App.app/Info.plist', plistlib.dumps(
            {'CFBundleIdentifier': 'test.app', 'CFBundleExecutable': 'App'},
            fmt=plistlib.FMT_BINARY))])
        self.assertEqual(self.report(path)['ios_bundles'][0]['CFBundleIdentifier'], 'test.app')

    def test_unsafe_paths_and_symlink_are_reported_not_extracted(self):
        link = zipfile.ZipInfo('link')
        link.create_system = 3
        link.external_attr = 0o120777 << 16
        path = self.archive('unsafe.apk', [('../escape', b'x'), ('C:\\escape', b'x'),
                                            (link, b'/tmp/example')])
        self.assertEqual(len(self.report(path)['archive']['unsafe_members']), 3)
        self.assertEqual(sorted(p.name for p in self.root.iterdir()), ['unsafe.apk'])

    def test_malformed_plist_is_partial_evidence(self):
        path = self.archive('malformed.ipa', [('Payload/App.app/Info.plist',
                                              b'<?xml version="1.0"?><plist><dict>')])
        self.assertEqual(self.report(path)['ios_bundles'][0]['status'], 'invalid')

    def test_oversized_plist_is_not_read(self):
        path = self.archive('large.ipa', [('Payload/App.app/Info.plist', b'x' * 1048577)])
        self.assertEqual(self.report(path)['ios_bundles'][0]['status'], 'not_read')

    def test_invalid_and_missing_files_have_error_exit(self):
        path = self.root / 'not-a-zip.apk'
        path.write_text('invalid')
        for target in (path, self.root / 'missing.apk', self.root):
            result = self.run_cli(target)
            self.assertEqual(result.returncode, 2)
            self.assertNotIn('Traceback', result.stderr)


if __name__ == '__main__':
    unittest.main()
