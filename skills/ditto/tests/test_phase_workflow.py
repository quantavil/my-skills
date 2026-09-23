"""Phase CLI and workspace regressions."""
import contextlib
from datetime import datetime, timezone
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

HERE = Path(__file__).resolve().parent.parent / 'scripts'
sys.path.insert(0, str(HERE))

import ditto  # noqa: E402
import phase_capture  # noqa: E402
import phase_compare  # noqa: E402
import phase_package  # noqa: E402
import phase_preflight  # noqa: E402
import phase_store as store  # noqa: E402
import pngtool  # noqa: E402


class PhaseWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='ditto-phase-workflow-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_init_creates_new_phase_workspace(self):
        self.assertEqual(ditto.main([
            'phase', 'init', 'daily_logging', '--project', str(self.root)]), 0)
        phase = self.root / 'phases/daily_logging'
        for relative in ('phase.001.json', 'status.json', 'notes.md',
                         'original', 'clone', 'diff'):
            self.assertTrue((phase / relative).exists(), relative)
        contract = store.validate_contract(store.load_json(phase / 'phase.001.json'))
        status = store.validate_status(store.load_json(phase / 'status.json'), contract)
        self.assertEqual(status['state'], 'preflight')

    def test_typer_exposes_phase_commands_without_changing_cli_shape(self):
        from typer.main import get_command
        root = get_command(ditto.app)
        self.assertIn('phase', root.commands)
        self.assertIn('collect-original', root.commands['phase'].commands)

    def test_init_refuses_overwrite_and_collection_before_preflight(self):
        phase_capture.init_phase(self.root, 'daily_logging')
        with self.assertRaisesRegex(store.PhaseError, 'already exists'):
            phase_capture.init_phase(self.root, 'daily_logging')
        with self.assertRaisesRegex(store.PhaseError, 'preflight'):
            phase_capture.require_collection_state(self.root, 'daily_logging')

    def test_phase_report_is_compact_json(self):
        phase_capture.init_phase(self.root, 'daily_logging')
        report = phase_capture.phase_report(self.root, 'daily_logging')
        self.assertEqual(report['phase_id'], 'daily_logging')
        self.assertEqual(report['state'], 'preflight')
        self.assertEqual(report['checkpoint_counts'], {'total': 0, 'closed': 0, 'open': 0})
        self.assertEqual(report['invalidations'], 0)
        self.assertEqual(report['human_review'], 'pending')
        with contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(ditto.main([
                'phase', 'report', 'daily_logging', '--project', str(self.root)]), 0)
        self.assertEqual(json.loads(output.getvalue())['state'], 'preflight')

    def test_removed_commands_are_not_parsed(self):
        for command in ('check', 'graph', 'report'):
            with self.subTest(command=command), \
                 contextlib.redirect_stderr(io.StringIO()), \
                 self.assertRaises(SystemExit):
                ditto.main([command])


class OriginalPackTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='ditto-original-pack-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.phase_id = 'daily_logging'
        self.clone = None
        phase_capture.init_phase(self.root, self.phase_id)
        self.phase = self.root / 'phases' / self.phase_id
        contract_path = self.phase / 'phase.001.json'
        contract = store.load_json(contract_path)
        contract.update({
            'scope': {'summary': 'Daily log header', 'unknowns': []},
            'runtime_target': {'kind': 'emulator', 'id': 'pixel_api_35'},
            'fixtures': {'default': {'account': 'fixture-user'}},
            'checkpoints': [{
                'number': 1, 'id': 'log_top', 'fixture': 'default',
                'setup': 'Reset and launch', 'actions': ['tap Log'],
                'artifacts': ['png', 'xml'],
                'required_dimensions': ['visual', 'layout'],
                'dependencies': ['theme'],
            }],
            'reverse_engineering': {
                'include_globs': ['AndroidManifest.xml', 'res/drawable/*'],
                'questions': ['Which icon is used?'],
            },
            'dependency_graph': {
                'components': ['theme'], 'path_rules': [],
                'component_edges': {'theme': []},
            },
            'authorized_differences': [{
                'id': 'theme_change', 'summary': 'Approved theme artwork change'}],
        })
        store.atomic_write_json(contract_path, contract)
        self.package = self.root / 'original.apk'
        with zipfile.ZipFile(self.package, 'w') as archive:
            archive.writestr('AndroidManifest.xml', b'manifest')
            archive.writestr('res/drawable/icon.png', b'icon')
            archive.writestr('lib/arm64-v8a/libapp.so', b'aot')
        self.package_sha = store.sha256_file(self.package)
        self.receipts = {}
        receipt_paths = []
        for capability in phase_preflight.REQUIRED_ANDROID_FLUTTER_MCPS:
            receipt = self._receipt(capability)
            self.receipts[capability] = receipt
            path = self.root / 'receipts' / f'{capability}.json'
            path.parent.mkdir(exist_ok=True)
            path.write_text(json.dumps(receipt), encoding='utf-8')
            receipt_paths.append(path)
        self.preflight = phase_preflight.record_preflight(
            self.root, self.phase_id, self.package, receipt_paths)
        self.exports = {}
        for capability in phase_package.REQUIRED_REVERSE_MCPS:
            directory = self.root / 'exports' / capability
            directory.mkdir(parents=True)
            (directory / 'receipt.json').write_text(
                json.dumps(self.receipts[capability]), encoding='utf-8')
            (directory / 'result.json').write_text(
                json.dumps({'finding': capability}), encoding='utf-8')
            self.exports[capability] = directory
        self.controller = self.root / 'controller'
        self._write_controller_export()

    def _receipt(self, capability):
        data = {
            'schema_version': 1, 'capability': capability,
            'server': f'{capability}-mcp-server', 'tool': f'{capability}_probe',
            'tool_version': '1.0.0', 'session_id': f'session-{capability}',
            'observed_at': datetime.now(timezone.utc).isoformat(),
            'request_sha256': '1' * 64, 'response_sha256': '2' * 64,
            'status': 'healthy', 'limitations': [], 'provenance': 'mcp',
        }
        if capability == 'mobile-control':
            data.update({
                'target': {'kind': 'emulator', 'id': 'pixel_api_35'},
                'environment': {'viewport_px': '1080x2400', 'density_dpi': 420},
                'probes': {name: True for name in phase_preflight.CONTROLLER_PROBES},
                'screenshot_sha256': '3' * 64,
            })
        else:
            data['target'] = {'package_sha256': self.package_sha}
            if capability == 'r2flutter':
                data.update({'supported': True, 'abi': 'arm64-v8a',
                             'dart_profile': '3.9'})
        return data

    def _write_controller_export(self, mutate=None, filenames=None, build=None):
        self.controller.mkdir(exist_ok=True)
        filenames = filenames or ('001_log_top.png', '001_log_top.xml')
        build = build or getattr(self, 'clone', None) or self.package
        build_sha = store.sha256_file(build)
        contract = store.load_json(self.phase / 'phase.001.json')
        checkpoints = {item['id']: item for item in contract['checkpoints']}
        records = []
        mobile = self.receipts['mobile-control']
        for filename in filenames:
            path = self.controller / filename
            checkpoint_id = filename.split('_', 1)[1].rsplit('.', 1)[0]
            checkpoint = checkpoints[checkpoint_id]
            if path.suffix == '.png':
                pngtool.encode(path, 12, 16, bytes((20, 30, 40)) * (12 * 16))
            else:
                path.write_text(
                    '<hierarchy><node text="Log" bounds="[0,0][10,10]"/>'
                    '</hierarchy>', encoding='utf-8')
            records.append({
                'checkpoint_id': checkpoint_id, 'kind': path.suffix.lstrip('.'),
                'path': filename, 'sha256': store.sha256_file(path),
                'server': mobile['server'], 'tool': mobile['tool'],
                'session_id': mobile['session_id'], 'target': mobile['target'],
                'action_result': 'success', 'provenance': 'mcp',
                'installed_package_sha256': build_sha,
                'fixture': checkpoint['fixture'],
                'setup_sha256': store.sha256_json(checkpoint['setup']),
                'actions_sha256': store.sha256_json(checkpoint['actions']),
            })
        capture = {
            'schema_version': 1, 'provenance': 'mcp',
            'server': mobile['server'], 'tool': mobile['tool'],
            'session_id': mobile['session_id'], 'target': mobile['target'],
            'environment': mobile['environment'], 'limitations': [],
            'installed_package_sha256': build_sha,
            'captured_at': datetime.now(timezone.utc).isoformat(),
            'artifacts': records,
        }
        if mutate:
            mutate(capture)
        (self.controller / 'capture.json').write_text(json.dumps(capture), encoding='utf-8')

    def collect(self):
        return phase_capture.collect_pack(
            'original', self.root, self.phase_id, self.package, self.controller,
            {'package_name': 'example.app', 'version': '1.0'}, self.preflight,
            self.exports)

    def test_collects_complete_original_pack_and_recaptures_immutably(self):
        first = self.collect()
        original = self.phase / 'original'
        self.assertEqual(first['revision'], 1)
        self.assertTrue((original / '001_log_top.r001.png').is_file())
        self.assertTrue((original / '001_log_top.r001.xml').is_file())
        self.assertTrue((original / f'app.{self.package_sha[:8]}.apk').is_file())
        self.assertTrue((original / 'reverse.001.json').is_file())
        status = store.load_json(self.phase / 'status.json')
        self.assertEqual(status['original_manifest_revision'], 1)
        old_hash = store.sha256_file(original / '001_log_top.r001.png')

        (self.controller / '001_log_top.png').write_bytes(b'new screenshot')
        capture = store.load_json(self.controller / 'capture.json')
        capture['artifacts'][0]['sha256'] = store.sha256_file(
            self.controller / '001_log_top.png')
        store.atomic_write_json(self.controller / 'capture.json', capture)
        second = self.collect()
        self.assertEqual(second['revision'], 2)
        self.assertEqual(store.sha256_file(original / '001_log_top.r001.png'), old_hash)
        self.assertTrue((original / '001_log_top.r002.png').is_file())
        self.assertTrue((original / 'manifest.002.json').is_file())

    def test_original_recapture_rejects_changed_reverse_export(self):
        self.collect()
        (self.exports['jadx'] / 'result.json').write_text(
            json.dumps({'finding': 'changed'}), encoding='utf-8')
        with self.assertRaisesRegex(store.PhaseError, 'reverse evidence differs'):
            self.collect()
        self.assertFalse((self.phase / 'original/manifest.002.json').exists())
        self.assertEqual(store.load_json(self.phase / 'status.json')[
            'original_manifest_revision'], 1)

    def test_collection_rejects_bad_sets_and_provenance_without_publishing(self):
        cases = (
            ('missing', lambda: (self.controller / '001_log_top.xml').unlink()),
            ('renamed', lambda: (self.controller / '001_log_top.png').rename(
                self.controller / 'wrong.png')),
            ('unexpected', lambda: (self.controller / 'extra.png').write_bytes(b'x')),
            ('manual', lambda: self._mutate_capture(
                lambda d: d['artifacts'][0].update(provenance='manual'))),
            ('adb', lambda: self._mutate_capture(
                lambda d: d['artifacts'][0].update(tool='adb'))),
            ('session', lambda: self._mutate_capture(
                lambda d: d['artifacts'][0].update(session_id='other'))),
            ('target', lambda: self._mutate_capture(
                lambda d: d['artifacts'][0].update(target={
                    'kind': 'emulator', 'id': 'other'}))),
        )
        for label, corrupt in cases:
            with self.subTest(label=label):
                corrupt()
                with self.assertRaises(store.PhaseError):
                    self.collect()
                self.assertFalse((self.phase / 'original/manifest.001.json').exists())
                self.assertIsNone(store.load_json(
                    self.phase / 'status.json')['original_manifest_revision'])
                self.tearDown()
                self.setUp()

    def _mutate_capture(self, mutate):
        path = self.controller / 'capture.json'
        data = store.load_json(path)
        mutate(data)
        store.atomic_write_json(path, data)

    def test_rejects_duplicate_record_and_symlink(self):
        capture = store.load_json(self.controller / 'capture.json')
        capture['artifacts'].append(dict(capture['artifacts'][0]))
        store.atomic_write_json(self.controller / 'capture.json', capture)
        with self.assertRaises(store.PhaseError):
            self.collect()
        self.tearDown()
        self.setUp()
        (self.controller / '001_log_top.png').unlink()
        (self.controller / '001_log_top.png').symlink_to('001_log_top.xml')
        with self.assertRaisesRegex(store.PhaseError, 'symbolic'):
            self.collect()

        self.tearDown()
        self.setUp()
        alias = self.root / 'controller-alias'
        alias.symlink_to(self.controller, target_is_directory=True)
        with self.assertRaisesRegex(store.PhaseError, 'real directory'):
            phase_capture.collect_pack(
                'original', self.root, self.phase_id, self.package, alias,
                {'package_name': 'example.app'}, self.preflight, self.exports)

    def test_freeze_validates_scope_artifacts_reverse_and_hashes(self):
        self.collect()
        result = phase_capture.freeze_original(self.root, self.phase_id)
        self.assertEqual(result['state'], 'oracle_frozen')
        contract_path = self.phase / 'phase.001.json'
        original_mode = contract_path.stat().st_mode
        self.assertEqual(original_mode & 0o222, 0)

        self.tearDown()
        self.setUp()
        self.collect()
        (self.phase / 'original/001_log_top.r001.png').write_bytes(b'tampered')
        with self.assertRaisesRegex(store.PhaseError, 'hash'):
            phase_capture.freeze_original(self.root, self.phase_id)

    def test_freeze_rejects_changed_reverse_evidence(self):
        self.collect()
        reverse = store.load_json(self.phase / 'original/reverse.001.json')
        retained = reverse['retained_files'][0]
        (self.phase / 'original' / retained['path']).write_bytes(b'tampered')
        with self.assertRaisesRegex(store.PhaseError, 'reverse evidence'):
            phase_capture.freeze_original(self.root, self.phase_id)

    def test_repreflight_cannot_reopen_frozen_original(self):
        self.collect()
        phase_capture.freeze_original(self.root, self.phase_id)
        receipt_paths = [self.root / 'receipts' / f'{name}.json'
                         for name in phase_preflight.REQUIRED_ANDROID_FLUTTER_MCPS]
        phase_preflight.record_preflight(
            self.root, self.phase_id, self.package, receipt_paths)
        self.assertEqual(store.load_json(self.phase / 'status.json')['state'],
                         'oracle_frozen')
        with self.assertRaisesRegex(store.PhaseError, 'preflight'):
            self.collect()

    def test_cli_collect_original_is_atomic(self):
        args = ['phase', 'collect-original', self.phase_id,
                '--project', str(self.root), '--package', str(self.package),
                '--controller-export', str(self.controller),
                '--build-metadata', json.dumps({'package_name': 'example.app'})]
        for capability, path in self.exports.items():
            args.extend(['--mcp-export', f'{capability}={path}'])
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(ditto.main(args), 0)
        self.assertTrue((self.phase / 'original/manifest.001.json').is_file())

    def _prepare_clone(self):
        self.collect()
        phase_capture.freeze_original(self.root, self.phase_id)
        self.clone = self.root / 'clone.apk'
        with zipfile.ZipFile(self.clone, 'w') as archive:
            archive.writestr('AndroidManifest.xml', b'clone manifest')
            archive.writestr('lib/arm64-v8a/libapp.so', b'clone aot')
        filenames = tuple(item['path'] for item in store.load_json(
            self.controller / 'capture.json')['artifacts'])
        self._write_controller_export(filenames=filenames, build=self.clone)
        return store.sha256_file(self.clone)

    def test_collects_clone_against_frozen_oracle_and_keeps_build_identity(self):
        clone_sha = self._prepare_clone()
        manifest = phase_capture.collect_pack(
            'clone', self.root, self.phase_id, self.clone, self.controller,
            {'package_name': 'example.clone', 'version': '7'}, self.preflight)
        clone_dir = self.phase / 'clone'
        self.assertEqual(manifest['revision'], 1)
        self.assertEqual(manifest['package']['sha256'], clone_sha)
        self.assertTrue((clone_dir / f'app.{clone_sha[:8]}.apk').is_file())
        self.assertTrue((clone_dir / '001_log_top.r001.png').is_file())
        self.assertNotIn('reverse_index', manifest)
        for artifact in manifest['artifacts']:
            self.assertEqual(artifact['build_sha256'], clone_sha)
        status = store.load_json(self.phase / 'status.json')
        self.assertEqual(status['state'], 'comparing')
        self.assertEqual(status['clone_manifest_revisions'], [1])
        self.assertEqual(status['active_clone_manifest_revision'], 1)

    def test_clone_requires_frozen_oracle_and_matching_environment(self):
        self.clone = self.root / 'clone.apk'
        self.clone.write_bytes(b'not collected')
        with self.assertRaisesRegex(store.PhaseError, 'oracle'):
            phase_capture.collect_pack(
                'clone', self.root, self.phase_id, self.clone, self.controller,
                {}, self.preflight)

        self._prepare_clone()
        self._mutate_capture(lambda data: data.update(
            environment={'viewport_px': '720x1280', 'density_dpi': 320}))
        with self.assertRaisesRegex(store.PhaseError, 'environment'):
            phase_capture.collect_pack(
                'clone', self.root, self.phase_id, self.clone, self.controller,
                {}, self.preflight)
        self.assertIsNone(store.load_json(
            self.phase / 'status.json')['active_clone_manifest_revision'])

    def test_clone_capture_rejects_wrong_installed_build_and_protocol(self):
        self._prepare_clone()
        self._mutate_capture(lambda data: data.update(
            installed_package_sha256=self.package_sha))
        with self.assertRaisesRegex(store.PhaseError, 'installed package'):
            phase_capture.collect_pack(
                'clone', self.root, self.phase_id, self.clone, self.controller,
                {}, self.preflight)
        self._write_controller_export(build=self.clone)
        self._mutate_capture(lambda data: data['artifacts'][0].update(
            actions_sha256='0' * 64))
        with self.assertRaisesRegex(store.PhaseError, 'provenance'):
            phase_capture.collect_pack(
                'clone', self.root, self.phase_id, self.clone, self.controller,
                {}, self.preflight)

    def test_cli_capture_clone(self):
        clone_sha = self._prepare_clone()
        args = ['phase', 'capture-clone', self.phase_id,
                '--project', str(self.root), '--apk', str(self.clone),
                '--controller-export', str(self.controller),
                '--build-metadata', json.dumps({'package_name': 'example.clone'})]
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(ditto.main(args), 0)
        self.assertTrue((self.phase / f'clone/app.{clone_sha[:8]}.apk').is_file())

    def _prepare_comparison(self):
        self._prepare_clone()
        phase_capture.collect_pack(
            'clone', self.root, self.phase_id, self.clone, self.controller,
            {'package_name': 'example.clone'}, self.preflight)

    def test_batch_compare_writes_immutable_results_triptychs_and_overview(self):
        self._prepare_comparison()
        report = phase_compare.compare_phase(self.root, self.phase_id)
        diff_dir = self.phase / 'diff'
        self.assertEqual(report['checkpoint_count'], 1)
        entry = report['checkpoints'][0]
        self.assertEqual(entry['checkpoint_id'], 'log_top')
        self.assertEqual(entry['visual_metric_status'], 'pass')
        self.assertEqual(entry['layout_comparison_status'], 'compared')
        self.assertIn('Full-resolution triptychs govern acceptance',
                      report['overview_limitation'])
        self.assertTrue((diff_dir / '001_log_top.r001.triptych.png').is_file())
        self.assertTrue((diff_dir / '001_log_top.r001.result.json').is_file())
        self.assertTrue((diff_dir / 'phase_overview.png').is_file())
        self.assertEqual(store.load_json(diff_dir / 'report.json'), report)
        status = store.load_json(self.phase / 'status.json')
        dimensions = status['checkpoints']['log_top']['dimensions']
        self.assertEqual(dimensions['visual']['status'], 'pending')
        self.assertEqual(dimensions['layout']['status'], 'pending')

    def test_semantic_verdicts_validate_ratio_evidence_and_authorization(self):
        self._prepare_comparison()
        phase_compare.compare_phase(self.root, self.phase_id)
        status = store.load_json(self.phase / 'status.json')
        result_name = status['checkpoints']['log_top']['active_result']
        result = store.load_json(self.phase / 'diff' / result_name)
        visual_evidence = next(key for key, value in result['evidence_catalog'].items()
                               if value['kind'] == 'visual_result')
        xml_evidence = next(key for key, value in result['evidence_catalog'].items()
                            if value['kind'] == 'xml')

        failed = phase_compare.record_verdict(
            self.root, self.phase_id, 'log_top', 'visual', 'fail',
            'The primary action label is wrong despite a small ratio.', [visual_evidence])
        self.assertEqual(failed['status'], 'fail')
        with self.assertRaisesRegex(store.PhaseError, 'evidence kind'):
            phase_compare.record_verdict(
                self.root, self.phase_id, 'log_top', 'visual', 'pass',
                'Pixels and content match.', [xml_evidence])
        with self.assertRaisesRegex(store.PhaseError, 'rationale'):
            phase_compare.record_verdict(
                self.root, self.phase_id, 'log_top', 'visual', 'pass', ' ',
                [visual_evidence])
        with self.assertRaisesRegex(store.PhaseError, 'evidence'):
            phase_compare.record_verdict(
                self.root, self.phase_id, 'log_top', 'visual', 'pass',
                'Pixels match.', ['diff:missing'])
        with self.assertRaisesRegex(store.PhaseError, 'authorization'):
            phase_compare.record_verdict(
                self.root, self.phase_id, 'log_top', 'visual',
                'accepted_difference', 'Approved artwork differs.', [visual_evidence])
        accepted = phase_compare.record_verdict(
            self.root, self.phase_id, 'log_top', 'visual',
            'accepted_difference', 'Approved artwork differs.', [visual_evidence],
            authorization='theme_change')
        self.assertEqual(accepted['authorization'], 'theme_change')
        with self.assertRaisesRegex(store.PhaseError, 'proposal'):
            phase_compare.record_verdict(
                self.root, self.phase_id, 'log_top', 'visual',
                'proposed_difference', 'New artwork should be considered.', [visual_evidence])

    def test_ratio_does_not_override_semantic_judgment(self):
        self._prepare_clone()
        pngtool.encode(self.controller / '001_log_top.png', 12, 16,
                       bytes((250, 250, 250)) * (12 * 16))
        capture = store.load_json(self.controller / 'capture.json')
        capture['artifacts'][0]['sha256'] = store.sha256_file(
            self.controller / '001_log_top.png')
        store.atomic_write_json(self.controller / 'capture.json', capture)
        phase_capture.collect_pack(
            'clone', self.root, self.phase_id, self.clone, self.controller,
            {}, self.preflight)
        phase_compare.compare_phase(self.root, self.phase_id)
        status = store.load_json(self.phase / 'status.json')
        result = store.load_json(
            self.phase / 'diff' / status['checkpoints']['log_top']['active_result'])
        evidence = next(key for key, value in result['evidence_catalog'].items()
                        if value['kind'] == 'visual_result')
        self.assertGreater(result['changed_ratio'], 0.05)
        verdict = phase_compare.record_verdict(
            self.root, self.phase_id, 'log_top', 'visual', 'pass',
            'Paired evidence shows matching content and geometry; rendering accounts for the delta.', [evidence])
        self.assertEqual(verdict['status'], 'pass')
        verdict = phase_compare.record_verdict(
            self.root, self.phase_id, 'log_top', 'visual', 'accepted_difference',
            'The approved theme accounts for the visual delta.', [evidence],
            authorization='theme_change')
        self.assertEqual(verdict['status'], 'accepted_difference')

    def test_dependency_resolution_is_transitive_and_conservative(self):
        contract = {
            'checkpoints': [
                {'id': 'home', 'dependencies': ['theme']},
                {'id': 'settings', 'dependencies': ['navigation']},
                {'id': 'saved', 'dependencies': ['persistence']},
            ],
            'dependency_graph': {
                'components': ['theme', 'navigation', 'model', 'persistence', 'docs',
                               'native_build'],
                'path_rules': [
                    {'glob': 'lib/theme.dart', 'components': ['theme']},
                    {'glob': 'lib/nav/**', 'components': ['navigation']},
                    {'glob': 'lib/model/**', 'components': ['model']},
                    {'glob': 'docs/**', 'components': ['docs']},
                    {'glob': 'android/**', 'components': ['native_build']},
                ],
                'component_edges': {'theme': [], 'navigation': [],
                                    'model': ['persistence'], 'persistence': [], 'docs': [],
                                    'native_build': []},
            },
        }
        self.assertEqual(phase_compare.affected_checkpoints(
            contract, ['lib/theme.dart']), ({'home'}, ['theme']))
        self.assertEqual(phase_compare.affected_checkpoints(
            contract, ['lib/model/user.dart']),
            ({'saved'}, ['model', 'persistence']))
        self.assertEqual(phase_compare.affected_checkpoints(
            contract, ['lib/theme.dart', 'lib/nav/router.dart'])[0],
            {'home', 'settings'})
        self.assertEqual(phase_compare.affected_checkpoints(
            contract, ['docs/readme.md']), (set(), ['docs']))
        self.assertEqual(phase_compare.affected_checkpoints(
            contract, ['android/app/build.gradle'])[0], {'home', 'settings', 'saved'})
        self.assertEqual(phase_compare.affected_checkpoints(
            contract, ['unknown.file'])[0], {'home', 'settings', 'saved'})
        contract['dependency_graph']['component_edges']['persistence'] = ['model']
        self.assertEqual(phase_compare.affected_checkpoints(
            contract, ['lib/model/user.dart'])[0], {'home', 'settings', 'saved'})

    def test_invalidation_reopens_only_affected_checkpoint_and_keeps_other_build(self):
        contract_path = self.phase / 'phase.001.json'
        contract = store.load_json(contract_path)
        contract['dependency_graph'] = {
            'components': ['theme', 'navigation'],
            'path_rules': [
                {'glob': 'lib/theme.dart', 'components': ['theme']},
                {'glob': 'lib/navigation.dart', 'components': ['navigation']},
            ],
            'component_edges': {'theme': [], 'navigation': []},
        }
        contract['checkpoints'][0]['dependencies'] = ['theme']
        contract['checkpoints'].append({
            'number': 2, 'id': 'settings', 'fixture': 'default',
            'setup': 'Reset and launch', 'actions': ['tap Settings'],
            'artifacts': ['png', 'xml'],
            'required_dimensions': ['visual', 'layout'],
            'dependencies': ['navigation'],
        })
        store.atomic_write_json(contract_path, contract)
        self._write_controller_export(filenames=(
            '001_log_top.png', '001_log_top.xml',
            '002_settings.png', '002_settings.xml'))
        self._prepare_comparison()
        phase_compare.compare_phase(self.root, self.phase_id)
        before = store.load_json(self.phase / 'status.json')
        untouched_build = before['checkpoints']['settings']['build_sha256']
        untouched_manifest = before['checkpoints']['settings']['clone_manifest_revision']

        newer = self.root / 'clone-new.apk'
        with zipfile.ZipFile(newer, 'w') as archive:
            archive.writestr('AndroidManifest.xml', b'new clone')
        self._write_controller_export(filenames=(
            '001_log_top.png', '001_log_top.xml',
            '002_settings.png', '002_settings.xml'), build=newer)
        phase_capture.collect_pack(
            'clone', self.root, self.phase_id, newer, self.controller,
            {'version': '8'}, self.preflight)
        record = phase_compare.invalidate(
            self.root, self.phase_id, ['lib/theme.dart'])
        self.assertEqual(record['reopened_checkpoints'], ['log_top'])
        self.assertEqual(record['resolved_components'], ['theme'])
        after = store.load_json(self.phase / 'status.json')
        self.assertEqual(after['state'], 'correcting')
        self.assertTrue(after['checkpoints']['log_top']['invalidated'])
        self.assertTrue(all(value['status'] == 'pending' for value in
                            after['checkpoints']['log_top']['dimensions'].values()))
        self.assertFalse(after['checkpoints']['settings']['invalidated'])
        self.assertEqual(after['checkpoints']['settings']['build_sha256'], untouched_build)
        self.assertEqual(after['checkpoints']['settings']['clone_manifest_revision'],
                         untouched_manifest)
        self.assertEqual(record['superseded_results']['log_top'], 1)

    def test_partial_clone_recapture_preserves_unaffected_verdict_and_build(self):
        contract_path = self.phase / 'phase.001.json'
        contract = store.load_json(contract_path)
        contract['dependency_graph'] = {
            'components': ['theme', 'navigation'],
            'path_rules': [{'glob': 'lib/theme.dart', 'components': ['theme']}],
            'component_edges': {'theme': [], 'navigation': []},
        }
        contract['checkpoints'].append({
            'number': 2, 'id': 'settings', 'fixture': 'default',
            'setup': 'Reset and launch', 'actions': ['tap Settings'],
            'artifacts': ['png'], 'required_dimensions': ['visual'],
            'dependencies': ['navigation'],
        })
        store.atomic_write_json(contract_path, contract)
        self._write_controller_export(filenames=(
            '001_log_top.png', '001_log_top.xml', '002_settings.png'))
        self._prepare_comparison()
        phase_compare.compare_phase(self.root, self.phase_id)
        status = store.load_json(self.phase / 'status.json')
        before = status['checkpoints']['settings']
        result = store.load_json(self.phase / 'diff' / before['active_result'])
        evidence = next(key for key, value in result['evidence_catalog'].items()
                        if value['kind'] == 'visual_result')
        phase_compare.record_verdict(
            self.root, self.phase_id, 'settings', 'visual', 'pass',
            'Settings screen matches the original.', [evidence])
        before = store.load_json(self.phase / 'status.json')['checkpoints']['settings']
        self.assertTrue(before['closed'])

        phase_compare.invalidate(self.root, self.phase_id, ['lib/theme.dart'])
        self._write_controller_export(filenames=('001_log_top.png', '001_log_top.xml'))
        (self.controller / '002_settings.png').unlink()
        newer = self.root / 'clone-new.apk'
        with zipfile.ZipFile(newer, 'w') as archive:
            archive.writestr('AndroidManifest.xml', b'new clone')
        self._write_controller_export(filenames=(
            '001_log_top.png', '001_log_top.xml'), build=newer)
        manifest = phase_capture.collect_pack(
            'clone', self.root, self.phase_id, newer, self.controller,
            {'version': '8'}, self.preflight)
        self.assertEqual({item['checkpoint_id'] for item in manifest['artifacts']},
                         {'log_top'})
        phase_compare.compare_phase(self.root, self.phase_id)
        after = store.load_json(self.phase / 'status.json')['checkpoints']['settings']
        self.assertEqual(after, before)
        result = store.load_json(self.phase / 'diff' /
                                 store.load_json(self.phase / 'status.json')[
                                     'checkpoints']['log_top']['active_result'])
        for dimension, kind in (('visual', 'visual_result'),
                                ('layout', 'layout_result')):
            evidence = next(key for key, value in result['evidence_catalog'].items()
                            if value['kind'] == kind)
            phase_compare.record_verdict(
                self.root, self.phase_id, 'log_top', dimension, 'pass',
                'Corrected checkpoint matches the original.', [evidence])
        old_manifest = self.phase / 'clone/manifest.001.json'
        tampered = store.load_json(old_manifest)
        tampered['controller']['provenance'] = 'manual'
        store.atomic_write_json(old_manifest, tampered)
        with self.assertRaises(phase_compare.ReadinessError) as caught:
            phase_compare.ready_phase(self.root, self.phase_id)
        self.assertTrue(any('settings clone manifest hash' in error or
                            'settings clone controller' in error
                            for error in caught.exception.errors))

    def test_invalidated_checkpoint_cannot_reuse_its_old_clone_capture(self):
        self._prepare_comparison()
        phase_compare.compare_phase(self.root, self.phase_id)
        phase_compare.invalidate(self.root, self.phase_id, ['unknown.dart'])
        with self.assertRaisesRegex(store.PhaseError, 'new clone capture'):
            phase_compare.compare_phase(self.root, self.phase_id)
        phase_capture.collect_pack(
            'clone', self.root, self.phase_id, self.clone, self.controller,
            {'version': 'stale-capture'}, self.preflight)
        with self.assertRaisesRegex(store.PhaseError, 'new clone capture'):
            phase_compare.compare_phase(self.root, self.phase_id)

    def test_postfreeze_original_recapture_revises_only_selected_checkpoint(self):
        contract_path = self.phase / 'phase.001.json'
        contract = store.load_json(contract_path)
        contract['checkpoints'].append({
            'number': 2, 'id': 'settings', 'fixture': 'default',
            'setup': 'Reset and launch', 'actions': ['tap Settings'],
            'artifacts': ['png'], 'required_dimensions': ['visual'],
            'dependencies': ['navigation'],
        })
        contract['dependency_graph']['components'].append('navigation')
        contract['dependency_graph']['component_edges']['navigation'] = []
        store.atomic_write_json(contract_path, contract)
        self._write_controller_export(filenames=(
            '001_log_top.png', '001_log_top.xml', '002_settings.png'))
        self._prepare_comparison()
        phase_compare.compare_phase(self.root, self.phase_id)
        initial = store.load_json(self.phase / 'status.json')['checkpoints']['settings']
        settings_result = store.load_json(self.phase / 'diff' / initial['active_result'])
        visual = next(key for key, value in settings_result['evidence_catalog'].items()
                      if value['kind'] == 'visual_result')
        phase_compare.record_verdict(
            self.root, self.phase_id, 'settings', 'visual', 'pass',
            'Settings still matches.', [visual])
        before = store.load_json(self.phase / 'status.json')['checkpoints']['settings']
        self._write_controller_export(filenames=(
            '001_log_top.png', '001_log_top.xml'), build=self.package)
        (self.controller / '002_settings.png').unlink()
        revised = phase_capture.collect_pack(
            'original', self.root, self.phase_id, self.package, self.controller,
            {'version': 'oracle-revision'}, self.preflight, self.exports,
            checkpoint_ids=['log_top'])
        artifacts = {(item['checkpoint_id'], item['kind']): item
                     for item in revised['artifacts']}
        self.assertEqual(artifacts['settings', 'png']['path'],
                         '002_settings.r001.png')
        self.assertEqual(artifacts['log_top', 'png']['path'],
                         '001_log_top.r002.png')
        status = store.load_json(self.phase / 'status.json')
        self.assertEqual(status['state'], 'correcting')
        self.assertTrue(status['checkpoints']['log_top']['invalidated'])
        self.assertEqual(status['checkpoints']['settings'], before)
        self._write_controller_export(filenames=(
            '001_log_top.png', '001_log_top.xml'), build=self.clone)
        phase_capture.collect_pack(
            'clone', self.root, self.phase_id, self.clone, self.controller,
            {'version': 'after-oracle-revision'}, self.preflight)
        phase_compare.compare_phase(self.root, self.phase_id)
        self._pass_required_dimensions()
        ready = phase_compare.ready_phase(self.root, self.phase_id)
        self.assertEqual(ready['state'], 'automated_ready')
        self.assertEqual(ready['checkpoints']['settings'], before)

    def test_cli_phase_pipeline_end_to_end(self):
        def cli(command, expected=0):
            result = subprocess.run(
                [sys.executable, str(HERE / 'ditto.py'), 'phase', command,
                 self.phase_id, '--project', str(self.root), *options],
                capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, expected, result.stderr)
            return json.loads(result.stdout) if result.stdout.startswith('{') else result

        contract = store.load_json(self.phase / 'phase.001.json')
        contract['dependency_graph'] = {
            'components': ['theme', 'navigation'],
            'path_rules': [{'glob': 'lib/theme.dart', 'components': ['theme']}],
            'component_edges': {'theme': [], 'navigation': []},
        }
        contract['checkpoints'][0]['artifacts'].append('trace')
        contract['checkpoints'][0]['required_dimensions'].append('behavior')
        contract['checkpoints'].append({
            'number': 2, 'id': 'settings', 'fixture': 'default',
            'setup': 'Reset and launch', 'actions': ['tap Settings'],
            'artifacts': ['png', 'trace'],
            'required_dimensions': ['visual', 'behavior'],
            'dependencies': ['navigation'],
        })
        shutil.rmtree(self.phase)
        options = []
        cli('init')
        store.validate_contract(contract)
        store.atomic_write_json(self.phase / 'phase.001.json', contract)
        options = ['--package', str(self.package)]
        for capability in phase_preflight.REQUIRED_ANDROID_FLUTTER_MCPS:
            options.extend(['--receipt', str(self.root / 'receipts' /
                                             f'{capability}.json')])
        cli('preflight')
        self._write_controller_export(filenames=(
            '001_log_top.png', '001_log_top.xml', '001_log_top.trace',
            '002_settings.png', '002_settings.trace'))
        options = ['--package', str(self.package),
                   '--controller-export', str(self.controller)]
        for name, path in self.exports.items():
            options.extend(['--mcp-export', f'{name}={path}'])
        cli('collect-original')
        reverse = store.load_json(self.phase / 'original/reverse.001.json')
        self.assertEqual(reverse['package_sha256'], self.package_sha)
        options = []
        cli('freeze-original')
        self.clone = self.root / 'clone.apk'
        with zipfile.ZipFile(self.clone, 'w') as archive:
            archive.writestr('AndroidManifest.xml', b'clone manifest')
        self._write_controller_export(filenames=(
            '001_log_top.png', '001_log_top.xml', '001_log_top.trace',
            '002_settings.png', '002_settings.trace'), build=self.clone)
        options = ['--apk', str(self.clone),
                   '--controller-export', str(self.controller)]
        cli('capture-clone')
        options = []
        cli('compare')
        first_status = store.load_json(self.phase / 'status.json')
        for checkpoint in contract['checkpoints']:
            identifier = checkpoint['id']
            result = store.load_json(self.phase / 'diff' /
                                     first_status['checkpoints'][identifier]['active_result'])
            triptych = self.phase / 'diff' / result['triptych']
            self.assertTrue(triptych.is_file())
            self.assertEqual(pngtool.decode(triptych)[0], 12 * 3 + 4 * 12)
            if identifier == 'settings':
                self.assertEqual(result['layout_comparison_status'], 'not_run')
                options = ['--dimension', 'layout', '--status', 'pass',
                           '--rationale', 'No paired XML.',
                           '--evidence', f"diff:{result['triptych']}"]
                cli('verdict', expected=2)
            for dimension in checkpoint['required_dimensions']:
                kind = {'visual': 'visual_result', 'layout': 'layout_result',
                        'behavior': 'trace'}[dimension]
                evidence = next(key for key, value in result['evidence_catalog'].items()
                                if value['kind'] == kind)
                options = [identifier, '--dimension', dimension, '--status', 'pass',
                           '--rationale', f'{dimension} matches original evidence.',
                           '--evidence', evidence]
                cli('verdict')
        options = []
        cli('ready')
        before = store.load_json(self.phase / 'status.json')['checkpoints']['settings']
        options = ['--changed', 'lib/theme.dart']
        cli('invalidate')
        self._write_controller_export(filenames=(
            '001_log_top.png', '001_log_top.xml', '001_log_top.trace'))
        for name in ('002_settings.png', '002_settings.trace'):
            (self.controller / name).unlink()
        newer = self.root / 'clone-new.apk'
        with zipfile.ZipFile(newer, 'w') as archive:
            archive.writestr('AndroidManifest.xml', b'corrected clone')
        self._write_controller_export(filenames=(
            '001_log_top.png', '001_log_top.xml', '001_log_top.trace'), build=newer)
        options = ['--apk', str(newer),
                   '--controller-export', str(self.controller)]
        cli('capture-clone')
        options = []
        cli('compare')
        corrected = store.load_json(self.phase / 'status.json')
        self.assertEqual(corrected['checkpoints']['settings'], before)
        result = store.load_json(self.phase / 'diff' /
                                 corrected['checkpoints']['log_top']['active_result'])
        for dimension in contract['checkpoints'][0]['required_dimensions']:
            kind = {'visual': 'visual_result', 'layout': 'layout_result',
                    'behavior': 'trace'}[dimension]
            evidence = next(key for key, value in result['evidence_catalog'].items()
                            if value['kind'] == kind)
            options = ['log_top', '--dimension', dimension, '--status', 'pass',
                       '--rationale', f'Corrected {dimension} matches.',
                       '--evidence', evidence]
            cli('verdict')
        options = []
        cli('ready')
        options = ['--accept', '--note', 'Reviewed the completed phase.']
        self.assertEqual(cli('review')['state'], 'human_accepted')
        self.assertFalse((self.phase / 'ledger.json').exists())
        self.assertFalse((self.root / 'spec/coverage.json').exists())

    def _pass_required_dimensions(self):
        status = store.load_json(self.phase / 'status.json')
        result = store.load_json(
            self.phase / 'diff' / status['checkpoints']['log_top']['active_result'])
        visual = next(key for key, value in result['evidence_catalog'].items()
                      if value['kind'] == 'visual_result')
        layout = next(key for key, value in result['evidence_catalog'].items()
                      if value['kind'] == 'layout_result')
        phase_compare.record_verdict(
            self.root, self.phase_id, 'log_top', 'visual', 'pass',
            'The visible content, alignment, and controls match.', [visual])
        phase_compare.record_verdict(
            self.root, self.phase_id, 'log_top', 'layout', 'pass',
            'The paired hierarchy bounds and node identities match.', [layout])

    def test_readiness_requires_complete_current_evidence_then_waits_for_human(self):
        self._prepare_comparison()
        phase_compare.compare_phase(self.root, self.phase_id)
        with self.assertRaises(phase_compare.ReadinessError) as caught:
            phase_compare.ready_phase(self.root, self.phase_id)
        self.assertTrue(any('pending' in item for item in caught.exception.errors))
        with self.assertRaisesRegex(store.PhaseError, 'automated readiness'):
            phase_compare.record_review(
                self.root, self.phase_id, 'accept', 'Reviewed phase evidence.')

        self._pass_required_dimensions()
        ready = phase_compare.ready_phase(self.root, self.phase_id)
        self.assertEqual(ready['state'], 'automated_ready')
        self.assertEqual(ready['human_review']['status'], 'pending')
        report = store.load_json(self.phase / 'diff/report.json')
        self.assertEqual(report['readiness']['status'], 'ready')

    def test_readiness_rechecks_package_artifacts_and_layout(self):
        self._prepare_comparison()
        phase_compare.compare_phase(self.root, self.phase_id)
        self._pass_required_dimensions()
        self.package.write_bytes(b'changed after preflight')
        with self.assertRaises(phase_compare.ReadinessError):
            phase_compare.ready_phase(self.root, self.phase_id)

        self.tearDown()
        self.setUp()
        self._prepare_comparison()
        phase_compare.compare_phase(self.root, self.phase_id)
        self._pass_required_dimensions()
        status = store.load_json(self.phase / 'status.json')
        result = store.load_json(
            self.phase / 'diff' / status['checkpoints']['log_top']['active_result'])
        (self.phase / 'diff' / result['triptych']).write_bytes(b'tampered')
        with self.assertRaises(phase_compare.ReadinessError) as caught:
            phase_compare.ready_phase(self.root, self.phase_id)
        self.assertTrue(any('hash' in item for item in caught.exception.errors))

    def test_visible_layout_can_use_triptych_without_xml(self):
        contract_path = self.phase / 'phase.001.json'
        contract = store.load_json(contract_path)
        contract['checkpoints'][0]['artifacts'] = ['png']
        store.atomic_write_json(contract_path, contract)
        self._write_controller_export(filenames=('001_log_top.png',))
        (self.controller / '001_log_top.xml').unlink()
        self._prepare_comparison()
        phase_compare.compare_phase(self.root, self.phase_id)
        status = store.load_json(self.phase / 'status.json')
        result = store.load_json(self.phase / 'diff' /
                                 status['checkpoints']['log_top']['active_result'])
        self.assertEqual(result['layout_comparison_status'], 'not_run')
        self.assertFalse(any(item['kind'] == 'layout_result' for item in
                             result['evidence_catalog'].values()))
        verdict = phase_compare.record_verdict(
            self.root, self.phase_id, 'log_top', 'layout', 'pass',
            'Paired screenshots show matching bounds, spacing, and no clipping.',
            [f"diff:{result['triptych']}"])
        self.assertEqual(verdict['status'], 'pass')

    def test_controller_restart_preserves_historical_manifest(self):
        self._prepare_comparison()
        phase_compare.compare_phase(self.root, self.phase_id)
        manifest = store.load_json(self.phase / 'original/manifest.001.json')
        current = dict(self.preflight)
        current['mcps'] = dict(current['mcps'])
        current['mcps']['mobile-control'] = dict(current['mcps']['mobile-control'],
                                                   session_id='restarted-session')
        contract = store.load_json(self.phase / 'phase.001.json')
        errors = []
        phase_compare._check_manifest_provenance(manifest, current, contract,
                                                  'original', errors)
        self.assertEqual(errors, [])

    def test_final_review_accepts_or_reopens_only_after_readiness(self):
        self._prepare_comparison()
        phase_compare.compare_phase(self.root, self.phase_id)
        self._pass_required_dimensions()
        phase_compare.ready_phase(self.root, self.phase_id)
        with self.assertRaisesRegex(store.PhaseError, 'note'):
            phase_compare.record_review(self.root, self.phase_id, 'accept', ' ')
        reopened = phase_compare.record_review(
            self.root, self.phase_id, 'request_changes',
            'Correct the top action color.', ['log_top'])
        self.assertEqual(reopened['state'], 'correcting')
        self.assertEqual(reopened['human_review']['status'], 'changes_requested')
        self.assertTrue(reopened['checkpoints']['log_top']['invalidated'])
        with self.assertRaisesRegex(store.PhaseError, 'automated readiness'):
            phase_compare.record_review(
                self.root, self.phase_id, 'accept', 'Premature acceptance.')

        self._write_controller_export(build=self.clone)
        phase_capture.collect_pack(
            'clone', self.root, self.phase_id, self.clone, self.controller,
            {'version': 'after-review'}, self.preflight)
        phase_compare.compare_phase(self.root, self.phase_id)
        self._pass_required_dimensions()
        phase_compare.ready_phase(self.root, self.phase_id)
        accepted = phase_compare.record_review(
            self.root, self.phase_id, 'accept', 'Reviewed the corrected phase evidence.')
        self.assertEqual(accepted['state'], 'human_accepted')
        self.assertEqual(accepted['human_review']['status'], 'accepted')
        self.assertEqual(len(accepted['human_review']['history']), 2)

    def test_failed_report_publication_never_advances_ready_or_review(self):
        self._prepare_comparison()
        phase_compare.compare_phase(self.root, self.phase_id)
        self._pass_required_dimensions()
        with patch.object(phase_compare, '_write_readiness_report',
                          side_effect=store.PhaseError('report failed')):
            with self.assertRaisesRegex(store.PhaseError, 'report failed'):
                phase_compare.ready_phase(self.root, self.phase_id)
        self.assertEqual(store.load_json(self.phase / 'status.json')['state'],
                         'comparing')
        phase_compare.ready_phase(self.root, self.phase_id)
        with patch.object(phase_compare, '_write_readiness_report',
                          side_effect=store.PhaseError('report failed')):
            with self.assertRaisesRegex(store.PhaseError, 'report failed'):
                phase_compare.record_review(
                    self.root, self.phase_id, 'accept', 'Reviewed evidence.')
        status = store.load_json(self.phase / 'status.json')
        self.assertEqual(status['state'], 'automated_ready')
        self.assertEqual(status['human_review']['status'], 'pending')


if __name__ == '__main__':
    unittest.main()
