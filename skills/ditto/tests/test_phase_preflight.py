"""Compulsory skill and MCP preflight regressions."""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent.parent / 'scripts'
sys.path.insert(0, str(HERE))

import phase_capture  # noqa: E402
import phase_preflight as preflight  # noqa: E402
import phase_store as store  # noqa: E402


class PreflightTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='ditto-preflight-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        phase_capture.init_phase(self.root, 'daily_logging')
        contract_path = self.root / 'phases/daily_logging/phase.json'
        contract = store.load_json(contract_path)
        contract['runtime_target'] = {'kind': 'emulator', 'id': 'pixel_api_35'}
        store.atomic_write_json(contract_path, contract)
        self.package = self.root / 'original.apk'
        self.package.write_bytes(b'identified apk')
        self.package_sha = store.sha256_file(self.package)
        self.receipts = []
        for capability in preflight.REQUIRED_ANDROID_FLUTTER_MCPS:
            receipt = self.receipt(capability)
            path = self.root / 'receipts' / f'{capability}.json'
            path.parent.mkdir(exist_ok=True)
            path.write_text(json.dumps(receipt), encoding='utf-8')
            self.receipts.append(path)

    def receipt(self, capability):
        common = {
            'schema_version': 1,
            'server': f'{capability}-mcp-server',
            'tool': f'{capability}_probe',
            'capability': capability,
            'tool_version': '1.0.0',
            'session_id': f'session-{capability}',
            'observed_at': datetime.now(timezone.utc).isoformat(),
            'request_sha256': '1' * 64,
            'response_sha256': '2' * 64,
            'status': 'healthy',
            'limitations': [],
            'provenance': 'mcp',
        }
        if capability == 'mobile-control':
            common.update({
                'target': {'kind': 'emulator', 'id': 'pixel_api_35'},
                'environment': {'viewport_px': '1080x2400', 'density_dpi': 420},
                'probes': {name: True for name in (
                    'launch', 'tap', 'type', 'swipe', 'back', 'screenshot', 'hierarchy')},
                'screenshot_sha256': '3' * 64,
            })
        else:
            common['target'] = {'package_sha256': self.package_sha}
            if capability == 'r2flutter':
                common.update({'supported': True, 'abi': 'arm64-v8a',
                               'dart_profile': '3.9'})
        return common

    def run_preflight(self, receipts=None):
        return preflight.record_preflight(
            self.root, 'daily_logging', self.package,
            self.receipts if receipts is None else receipts)

    def replace_receipt(self, capability, mutate):
        path = next(path for path in self.receipts if path.stem == capability)
        data = json.loads(path.read_text(encoding='utf-8'))
        mutate(data)
        path.write_text(json.dumps(data), encoding='utf-8')

    def test_valid_preflight_needs_no_other_skills_and_advances_phase(self):
        self.assertIn('properties', preflight.ReceiptModel.model_json_schema())
        result = self.run_preflight()
        self.assertEqual(result['package_sha256'], self.package_sha)
        self.assertNotIn('skill', result)
        self.assertNotIn('skills', result)
        self.assertEqual(set(result['mcps']), set(preflight.REQUIRED_ANDROID_FLUTTER_MCPS))
        status = store.load_json(self.root / 'phases/daily_logging/status.json')
        self.assertEqual(status['state'], 'collecting_original')
        self.assertEqual(status['preflight_revision'], 1)
        self.assertTrue((self.root / 'phases/daily_logging/preflight.json').is_file())

    def test_missing_mcp_blocks(self):
        for label, receipts in (('MCP', self.receipts[:-1]),):
            with self.subTest(label=label):
                with self.assertRaises(store.PhaseError):
                    self.run_preflight(receipts)
                status = store.load_json(self.root / 'phases/daily_logging/status.json')
                self.assertEqual(status['state'], 'blocked')
                self.assertTrue(status['blockers'])

    def test_wrong_package_unsupported_flutter_and_bad_controller_block(self):
        mutations = (
            ('package', 'jadx', lambda d: d['target'].update(package_sha256='f' * 64)),
            ('Flutter ABI', 'r2flutter', lambda d: d.update(supported=False)),
            ('controller target', 'mobile-control',
             lambda d: d['target'].update(id='another_emulator')),
            ('controller capability', 'mobile-control',
             lambda d: d['probes'].update(swipe=False)),
        )
        for label, capability, mutate in mutations:
            with self.subTest(label=label):
                self.replace_receipt(capability, mutate)
                with self.assertRaises(store.PhaseError):
                    self.run_preflight()
                self.setUp()

    def test_stale_unknown_and_non_mcp_receipts_block(self):
        mutations = (
            ('future', 'jadx', lambda d: d.update(
                observed_at=(datetime.now(timezone.utc) + timedelta(days=2)).isoformat())),
            ('schema', 'jadx', lambda d: d.update(schema_version=99)),
            ('provenance', 'jadx', lambda d: d.update(provenance='cli')),
            ('unhealthy', 'jadx', lambda d: d.update(status='unhealthy')),
        )
        for label, capability, mutate in mutations:
            with self.subTest(label=label):
                self.replace_receipt(capability, mutate)
                with self.assertRaises(store.PhaseError):
                    self.run_preflight()
                self.setUp()

    def test_unchanged_static_analysis_does_not_expire(self):
        self.replace_receipt('jadx', lambda d: d.update(
            observed_at=(datetime.now(timezone.utc) - timedelta(days=90)).isoformat()))
        self.assertEqual(self.run_preflight()['package_sha256'], self.package_sha)

    def test_duplicate_capability_blocks(self):
        duplicate = self.root / 'receipts/duplicate.json'
        duplicate.write_text(self.receipts[0].read_text(encoding='utf-8'), encoding='utf-8')
        with self.assertRaisesRegex(store.PhaseError, 'duplicate'):
            self.run_preflight(receipts=[*self.receipts, duplicate])

    def test_unknown_capability_is_rejected(self):
        unknown = self.root / 'receipts/unsupported.json'
        unknown.write_text(json.dumps(self.receipt('unsupported')), encoding='utf-8')
        with self.assertRaisesRegex(store.PhaseError, 'unknown MCP capability'):
            self.run_preflight([*self.receipts, unknown])

if __name__ == '__main__':
    unittest.main()
