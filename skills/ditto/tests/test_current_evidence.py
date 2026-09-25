"""Current checkpoint evidence replaces prior files without stale verdicts."""
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

HERE = Path(__file__).resolve().parent.parent / 'scripts'
sys.path.insert(0, str(HERE))
import phase_capture
import phase_current
import phase_compare
import phase_preflight
import phase_store as store
import pngtool


class CurrentEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name)
        self.phase = phase_capture.init_phase(self.project, 'demo')
        self.contract = store.load_json(self.phase / 'phase.json')
        self.contract.update({
            'scope': {'summary': 'Home', 'unknowns': []},
            'runtime_target': {'kind': 'emulator', 'id': 'device'},
            'fixtures': {'default': {}},
            'checkpoints': [{'number': 1, 'id': 'home', 'fixture': 'default',
                             'setup': 'launch', 'actions': ['open home'],
                             'artifacts': ['png'], 'required_dimensions': ['visual'],
                             'dependencies': []}],
        })
        store.atomic_write_json(self.phase / 'phase.json', self.contract)
        self.original_apk = self.project / 'original.apk'
        self.clone_apk = self.project / 'clone.apk'
        for apk, content in ((self.original_apk, b'original'),
                             (self.clone_apk, b'clone')):
            with zipfile.ZipFile(apk, 'w') as archive:
                archive.writestr('AndroidManifest.xml', content)
        self.receipt = {'server': 'ditto-mobile', 'tool': 'recorder_control',
                        'session_id': 'session', 'provenance': 'mcp',
                        'target': self.contract['runtime_target'],
                        'environment': {'viewport_px': '12x16'}}
        receipts = {}
        for capability in phase_preflight.REQUIRED_ANDROID_FLUTTER_MCPS:
            receipt = {**self.receipt, 'schema_version': 1, 'capability': capability,
                       'tool_version': '1', 'observed_at': datetime.now(timezone.utc).isoformat(),
                       'request_sha256': '1'*64, 'response_sha256': '2'*64,
                       'status': 'healthy', 'limitations': []}
            if capability == 'mobile-control':
                receipt.update(probes={name: True for name in phase_preflight.CONTROLLER_PROBES},
                               screenshot_sha256='3'*64)
            else:
                receipt['target'] = {'package_sha256': store.sha256_file(self.original_apk)}
                if capability == 'r2flutter':
                    receipt.update(supported=True, abi='arm64-v8a', dart_profile='3.9')
            receipts[capability] = receipt
        preflight = {'schema_version': 1, 'phase_id': 'demo', 'revision': 1,
                     'phase_revision': 1, 'package': str(self.original_apk),
                     'package_sha256': store.sha256_file(self.original_apk),
                     'mcps': receipts}
        store.atomic_write_json(self.phase / 'preflight.json', preflight)
        status = store.load_json(self.phase / 'status.json')
        status['state'] = 'collecting_original'
        status['preflight_revision'] = 1
        store.atomic_write_json(self.phase / 'status.json', status)
        self.action_log = self.project / 'journal.json'
        self.action_log.write_text('[]')
        self.original_png = self.project / 'original.png'
        self.clone_png = self.project / 'clone.png'
        pngtool.encode(self.original_png, 12, 16, bytes((20, 30, 40)) * 192)
        pngtool.encode(self.clone_png, 12, 16, bytes((20, 31, 40)) * 192)

    def selection(self, kind, apk, png, *, original_sha=None):
        selected = {
            'checkpoint_id': 'home', 'png': str(png),
            'png_sha256': store.sha256_file(png), 'xml': None, 'xml_sha256': None,
            'captured_at': datetime.now(timezone.utc).isoformat(),
            'after_input': 0, 'observed_actions': [],
        }
        if original_sha:
            selected['original_png_sha256'] = original_sha
        payload = {
            'schema_version': 1, 'kind': kind, 'phase_id': 'demo',
            'installed_package_sha256': store.sha256_file(apk),
            'target': self.receipt['target'],
            'environment': self.receipt['environment'],
            'mcp_receipt': self.receipt,
            'server': self.receipt['server'], 'tool': self.receipt['tool'],
            'session_id': self.receipt['session_id'], 'provenance': 'mcp',
            'action_log': {'path': str(self.action_log),
                           'sha256': store.sha256_file(self.action_log)},
            'selections': [selected],
        }
        path = self.project / f'{kind}.json'
        store.atomic_write_json(path, payload)
        return path

    def test_selected_original_freezes_and_clone_overwrite_resets_verdict(self):
        selection = self.selection('ditto_selected_original', self.original_apk,
                                   self.original_png)
        phase_current.select_original(self.project, 'demo', selection,
                                      self.original_apk)
        self.assertTrue((self.phase / 'original/001_home.png').is_file())
        self.assertTrue((self.phase / 'original/manifest.json').is_file())
        phase_current.freeze_original(self.project, 'demo')
        original_sha = store.sha256_file(self.original_png)
        clone_selection = self.selection('ditto_selected_clone', self.clone_apk,
                                         self.clone_png, original_sha=original_sha)
        first = phase_current.capture_clone(self.project, 'demo', clone_selection,
                                            self.clone_apk)
        self.assertTrue(Path(first['triptych']).is_file())
        self.assertEqual(first['status'], 'comparing')
        status = store.load_json(self.phase / 'status.json')
        status['checkpoints']['home']['dimensions']['visual']['status'] = 'pass'
        store.atomic_write_json(self.phase / 'status.json', status)
        pngtool.encode(self.clone_png, 12, 16, bytes((50, 31, 40)) * 192)
        clone_selection = self.selection('ditto_selected_clone', self.clone_apk,
                                         self.clone_png, original_sha=original_sha)
        phase_current.capture_clone(self.project, 'demo', clone_selection,
                                    self.clone_apk)
        current = store.load_json(self.phase / 'status.json')
        self.assertEqual(current['checkpoints']['home']['dimensions']['visual']['status'],
                         'pending')
        self.assertEqual(len(list((self.phase / 'clone').glob('*.png'))), 1)
        self.assertEqual(len(list((self.phase / 'diff').glob('*.triptych.png'))), 1)

    def test_frozen_original_requires_explicit_replacement(self):
        selection = self.selection('ditto_selected_original', self.original_apk,
                                   self.original_png)
        phase_current.select_original(self.project, 'demo', selection,
                                      self.original_apk)
        phase_current.freeze_original(self.project, 'demo')
        with self.assertRaisesRegex(store.PhaseError, 'replace-frozen'):
            phase_current.select_original(self.project, 'demo', selection,
                                          self.original_apk)

    def test_rejects_changed_candidate_before_touching_current(self):
        selection = self.selection('ditto_selected_original', self.original_apk,
                                   self.original_png)
        self.original_png.write_bytes(b'changed')
        with self.assertRaisesRegex(store.PhaseError, 'hash'):
            phase_current.select_original(self.project, 'demo', selection,
                                          self.original_apk)
        self.assertFalse((self.phase / 'original/manifest.json').exists())


    def prepare_comparison(self):
        original = self.selection('ditto_selected_original', self.original_apk, self.original_png)
        phase_current.select_original(self.project, 'demo', original, self.original_apk)
        phase_current.freeze_original(self.project, 'demo')
        clone = self.selection('ditto_selected_clone', self.clone_apk, self.clone_png,
                               original_sha=store.sha256_file(self.original_png))
        phase_current.capture_clone(self.project, 'demo', clone, self.clone_apk)
        return clone

    def test_readiness_needs_review_and_current_hashes(self):
        self.prepare_comparison()
        with self.assertRaises(phase_compare.ReadinessError):
            phase_compare.ready_phase(self.project, 'demo')
        phase_compare.record_verdict(self.project, 'demo', 'home', 'visual', 'pass',
                                     'Compared visible content', ['diff:001_home.triptych.png'])
        self.assertEqual(phase_compare.ready_phase(self.project, 'demo')['state'], 'automated_ready')
        phase_compare.record_review(self.project, 'demo', 'accept', 'Human reviewed')
        (self.phase / 'clone/001_home.png').write_bytes(b'changed')
        with self.assertRaises(phase_compare.ReadinessError):
            phase_compare.ready_phase(self.project, 'demo')

    def test_trace_is_retained_and_dimension_evidence_is_checked(self):
        self.prepare_comparison()
        self.action_log.unlink()
        phase_current._verify_manifest(self.phase, 'clone', phase_current._load_manifest(self.phase, 'clone'))
        self.assertTrue((self.phase / 'clone/001_home.trace.json').exists())
        with self.assertRaisesRegex(store.PhaseError, 'cannot support'):
            phase_compare.record_verdict(self.project, 'demo', 'home', 'visual', 'pass',
                                         'wrong evidence', ['clone:001_home.trace.json'])

    def test_failed_publish_restores_previous_current_set(self):
        selection = self.prepare_comparison()
        previous = (self.phase / 'status.json').read_bytes()
        with patch.object(phase_current, 'write_report', side_effect=OSError('disk full')):
            with self.assertRaises(OSError):
                phase_current.capture_clone(self.project, 'demo', selection, self.clone_apk)
        phase_current.recover_pending(self.project, 'demo')
        self.assertEqual((self.phase / 'status.json').read_bytes(), previous)
        phase_current._verify_manifest(self.phase, 'clone', phase_current._load_manifest(self.phase, 'clone'))

    def test_invalidation_rejects_old_verdict(self):
        self.prepare_comparison()
        phase_compare.invalidate(self.project, 'demo', ['unmapped.dart'])
        with self.assertRaisesRegex(store.PhaseError, 'invalidated'):
            phase_compare.record_verdict(self.project, 'demo', 'home', 'visual', 'pass',
                                         'stale', ['diff:001_home.triptych.png'])

    def test_frozen_original_detects_contract_changes(self):
        clone = self.prepare_comparison()
        contract = store.load_json(self.phase / 'phase.json')
        contract['scope']['summary'] = 'Changed scope'
        store.atomic_write_json(self.phase / 'phase.json', contract)
        with self.assertRaisesRegex(store.PhaseError, 'contract changed'):
            phase_current.capture_clone(self.project, 'demo', clone, self.clone_apk)

    def test_partial_new_build_keeps_unaffected_checkpoint(self):
        import copy
        second = copy.deepcopy(self.contract['checkpoints'][0])
        second.update(id='details', number=2)
        self.contract['checkpoints'].append(second)
        store.atomic_write_json(self.phase / 'phase.json', self.contract)
        original = self.selection('ditto_selected_original', self.original_apk, self.original_png)
        data = store.load_json(original)
        data['selections'].append({**data['selections'][0], 'checkpoint_id': 'details'})
        store.atomic_write_json(original, data)
        phase_current.select_original(self.project, 'demo', original, self.original_apk)
        phase_current.freeze_original(self.project, 'demo')
        old_build = store.sha256_file(self.clone_apk)
        for identifier in ('home', 'details'):
            if identifier == 'details':
                self.clone_apk.write_bytes(b'new-debug-package')
            selection = self.selection('ditto_selected_clone', self.clone_apk, self.clone_png,
                                       original_sha=store.sha256_file(self.original_png))
            data = store.load_json(selection)
            data['selections'][0]['checkpoint_id'] = identifier
            store.atomic_write_json(selection, data)
            phase_current.capture_clone(self.project, 'demo', selection, self.clone_apk)
            number = 1 if identifier == 'home' else 2
            phase_compare.record_verdict(self.project, 'demo', identifier, 'visual', 'pass',
                                         'Reviewed visible geometry',
                                         [f'diff:{number:03d}_{identifier}.triptych.png'])
        status = phase_compare.ready_phase(self.project, 'demo')
        self.assertEqual(status['checkpoints']['home']['build_sha256'], old_build)
        self.assertNotEqual(status['checkpoints']['details']['build_sha256'], old_build)
        self.assertEqual(len(list((self.phase / 'clone').glob('*.apk'))), 1)

if __name__ == '__main__':
    unittest.main()
