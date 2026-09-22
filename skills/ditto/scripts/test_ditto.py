"""Hermetic regression tests. No device, SDK, Node, or external image tools required.

Run: python3 -m unittest discover -s scripts -p 'test_*.py'
"""
import hashlib
import json
import os
from pathlib import Path
import random
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import diff_screenshots as diff  # noqa: E402
import inventory  # noqa: E402
import ledger  # noqa: E402
import pngtool  # noqa: E402
import theme_extract  # noqa: E402
import validate_spec  # noqa: E402


def solid(width, height, rgb):
    return bytes(rgb) * (width * height)


class Temp(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='ditto-test-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)


# --------------------------------------------------------------------------

class PngTests(Temp):
    def test_round_trip_is_exact(self):
        random.seed(3)
        width, height = 37, 23
        pixels = bytes(random.randrange(256) for _ in range(width * height * 3))
        path = self.root / 'a.png'
        pngtool.encode(path, width, height, pixels)
        self.assertEqual(pngtool.decode(path), (width, height, pixels))
        self.assertEqual(pngtool.read_header(path), (width, height))

    def test_non_png_is_rejected(self):
        path = self.root / 'fake.png'
        path.write_bytes(b'not a png at all')
        with self.assertRaises(pngtool.PngError):
            pngtool.read_header(path)
        with self.assertRaises(pngtool.PngError):
            pngtool.decode(path)

    def test_buffer_length_must_match_dimensions(self):
        with self.assertRaises(pngtool.PngError):
            pngtool.encode(self.root / 'b.png', 4, 4, b'\x00' * 10)


# --------------------------------------------------------------------------

class DiffTests(Temp):
    def setUp(self):
        super().setUp()
        self.width, self.height = 40, 60
        self.a = self.root / 'a.png'
        self.b = self.root / 'b.png'
        pngtool.encode(self.a, self.width, self.height, solid(self.width, self.height, (10, 20, 30)))
        pixels = bytearray(solid(self.width, self.height, (10, 20, 30)))
        for y in range(0, 10):            # 10 rows of noise at the top
            for x in range(self.width):
                o = (y * self.width + x) * 3
                pixels[o:o + 3] = b'\xff\xff\xff'
        for y in range(30, 32):           # a real 2x5 defect in the body
            for x in range(5, 10):
                o = (y * self.width + x) * 3
                pixels[o:o + 3] = b'\xff\x00\x00'
        pngtool.encode(self.b, self.width, self.height, bytes(pixels))

    def test_exclusion_leaves_the_denominator(self):
        _, result = diff.diff_screenshots(self.a, self.b, self.root / 'o',
                                          top_mask=10, max_diff_ratio=1.0)
        self.assertEqual(result['changed_pixels'], 10)
        self.assertEqual(result['compared_pixels'], self.width * (self.height - 10))
        self.assertEqual(result['excluded_pixels'], self.width * 10)

    def test_montage_is_only_written_when_requested(self):
        out = self.root / 'compact'
        diff.diff_screenshots(self.a, self.a, out)
        self.assertEqual({p.name for p in out.iterdir()}, {'diff.png', 'result.json'})
        diff.diff_screenshots(self.a, self.a, out, montage=True)
        self.assertTrue((out / 'composite_side_by_side.png').exists())

    def test_pure_python_and_numpy_agree(self):
        _, with_numpy = diff.diff_screenshots(self.a, self.b, self.root / 'n', max_diff_ratio=1.0)
        original = diff._load_numpy
        diff._load_numpy = lambda: None
        try:
            _, pure = diff.diff_screenshots(self.a, self.b, self.root / 'p', max_diff_ratio=1.0)
        finally:
            diff._load_numpy = original
        self.assertEqual(with_numpy['changed_pixels'], pure['changed_pixels'])
        self.assertEqual(with_numpy['compared_pixels'], pure['compared_pixels'])

    def test_threshold_matches_pixelmatch_semantics(self):
        """maxDelta = 35215 * t^2; a uniform +25 step sits just under t=0.1."""
        near = self.root / 'near.png'
        pngtool.encode(near, self.width, self.height, solid(self.width, self.height, (35, 45, 55)))
        _, loose = diff.diff_screenshots(self.a, near, self.root / 'l',
                                         threshold=0.1, max_diff_ratio=1.0)
        _, tight = diff.diff_screenshots(self.a, near, self.root / 't',
                                         threshold=0.05, max_diff_ratio=1.0)
        self.assertEqual(loose['changed_pixels'], 0)
        self.assertEqual(tight['changed_pixels'], self.width * self.height)

    def test_mismatched_dimensions_are_refused(self):
        other = self.root / 'other.png'
        pngtool.encode(other, self.width + 1, self.height, solid(self.width + 1, self.height, (0, 0, 0)))
        with self.assertRaisesRegex(ValueError, 'dimensions differ'):
            diff.diff_screenshots(self.a, other, self.root / 'd')

    def test_full_exclusion_is_refused(self):
        with self.assertRaisesRegex(ValueError, 'whole image'):
            diff.diff_screenshots(self.a, self.b, self.root / 'x',
                                  top_mask=30, bottom_mask=30)

    def test_failed_rerun_does_not_leave_a_stale_pass(self):
        out = self.root / 'rerun'
        diff.diff_screenshots(self.a, self.a, out)
        self.assertTrue((out / 'result.json').is_file())
        self.b.unlink()
        with self.assertRaises(FileNotFoundError):
            diff.diff_screenshots(self.a, self.b, out)
        self.assertFalse((out / 'result.json').exists())

    def test_output_may_not_overwrite_input(self):
        out = self.root / 'collide'
        out.mkdir()
        shutil.copy(self.a, out / 'diff.png')
        with self.assertRaisesRegex(ValueError, 'overwrite input'):
            diff.diff_screenshots(out / 'diff.png', self.b, out)

    def test_cli_reports_unavailable_rather_than_a_verdict(self):
        proc = subprocess.run(
            [sys.executable, str(HERE / 'diff_screenshots.py'),
             str(self.a), str(self.root / 'missing.png'), '--output-dir', str(self.root / 'z')],
            capture_output=True, text=True)
        self.assertEqual(proc.returncode, 2)
        self.assertIn('not a pass and not a mismatch', proc.stderr)

    def test_repeated_hierarchy_labels_are_not_matched(self):
        original = self.root / 'o.xml'
        candidate = self.root / 'c.xml'
        original.write_text('<hierarchy>'
                            '<node text="Item" bounds="[0,0][10,10]"/>'
                            '<node text="Item" bounds="[0,20][10,30]"/>'
                            '<node text="Only" bounds="[0,40][10,50]"/>'
                            '</hierarchy>')
        candidate.write_text('<hierarchy>'
                             '<node text="Item" bounds="[0,5][10,15]"/>'
                             '<node text="Item" bounds="[0,25][10,35]"/>'
                             '<node text="Only" bounds="[0,48][10,58]"/>'
                             '</hierarchy>')
        result = diff.compare_hierarchies(original, candidate)
        self.assertEqual([d['identifier'] for d in result['deltas']], ['Only'])
        self.assertIn('Item', result['ambiguous_identifiers'])


# --------------------------------------------------------------------------

class InventoryTests(Temp):
    def archive(self, name, members):
        path = self.root / name
        with zipfile.ZipFile(path, 'w') as handle:
            for member in members:
                handle.writestr(member, b'x')
        return path

    def test_member_list_is_not_dumped_by_default(self):
        path = self.archive('big.apk', [f'res/drawable/a{i}.png' for i in range(500)])
        report = inventory.inventory(path)
        self.assertNotIn('members', report['archive'])
        self.assertEqual(report['archive']['member_count'], 500)
        self.assertEqual(report['archive']['top_level'], {'res': 500})
        rendered = json.dumps(report)
        self.assertLess(len(rendered), 20000, 'summary output must stay small')

    def test_members_flag_writes_a_separate_file(self):
        path = self.archive('app.apk', ['classes.dex', 'AndroidManifest.xml'])
        target = self.root / 'members.txt'
        code = inventory.main([str(path), '--output', str(self.root / 'r.json'),
                               '--members', str(target)])
        self.assertEqual(code, 0)
        self.assertEqual(sorted(target.read_text().split()),
                         ['AndroidManifest.xml', 'classes.dex'])

    def test_flutter_wrapper_dex_is_explained(self):
        path = self.archive('f.apk', ['classes.dex', 'lib/arm64-v8a/libapp.so',
                                      'lib/arm64-v8a/libflutter.so',
                                      'assets/flutter_assets/FontManifest.json'])
        report = inventory.inventory(path)
        self.assertEqual(report['android_abis'], ['arm64-v8a'])
        self.assertTrue(any('wrapper' in note for note in report['framework_guess']))
        self.assertEqual(report['assets']['flutter_font_manifest']['count'], 1)

    def test_unsafe_members_reported_not_extracted(self):
        link = zipfile.ZipInfo('link')
        link.create_system = 3
        link.external_attr = 0o120777 << 16
        path = self.root / 'unsafe.apk'
        with zipfile.ZipFile(path, 'w') as handle:
            handle.writestr('../escape', b'x')
            handle.writestr('C:\\escape', b'x')
            handle.writestr(link, b'/etc/passwd')
        report = inventory.inventory(path)
        self.assertEqual(len(report['archive']['unsafe_members']), 3)
        self.assertEqual(sorted(p.name for p in self.root.iterdir()), ['unsafe.apk'])

    def test_refuses_overwrite_without_force(self):
        path = self.archive('a.apk', ['classes.dex'])
        out = self.root / 'r.json'
        self.assertEqual(inventory.main([str(path), '--output', str(out)]), 0)
        self.assertEqual(inventory.main([str(path), '--output', str(out)]), 2)
        self.assertEqual(inventory.main([str(path), '--output', str(out), '--force']), 0)

    def test_bad_input_exits_cleanly(self):
        bad = self.root / 'not-a-zip.apk'
        bad.write_text('nope')
        for target in (bad, self.root / 'missing.apk', self.root):
            self.assertEqual(inventory.main([str(target)]), 2)


# --------------------------------------------------------------------------

class LedgerAndValidatorTests(Temp):
    def setUp(self):
        super().setUp()
        (self.root / 'evidence').mkdir()
        (self.root / 'spec').mkdir()
        self.records = []
        self.hashes = {}
        for role in ('original', 'candidate'):
            path = self.root / 'evidence' / f'{role}.png'
            pngtool.encode(path, 4, 4, solid(4, 4, (1, 2, 3)))
            self.hashes[role] = hashlib.sha256(role.encode()).hexdigest()
            self.records.append({
                'id': role, 'kind': 'screenshot', 'role': role, 'runtime': True,
                'path': f'evidence/{role}.png',
                'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                'app_sha256': self.hashes[role], 'platform': 'android',
                'flow_id': 'log', 'state_id': 'saved', 'fixture_id': 'empty'})
        self.case = {
            'id': 'log.saved.android', 'flow_id': 'log', 'platform': 'android',
            'state_id': 'saved', 'required': True, 'critical': True,
            'observed': True, 'implemented': True, 'validation': 'pass',
            'evidence_ids': ['original', 'candidate'], 'comparison': 'comparison.json',
            'required_dimensions': ['behavior', 'persistence'], 'user_testing': 'pending',
            'original_app_sha256': self.hashes['original'],
            'candidate_app_sha256': self.hashes['candidate']}
        self.comparison = {
            'case_id': 'log.saved.android', 'result': 'pass',
            'original_evidence_ids': ['original'], 'candidate_evidence_ids': ['candidate'],
            'fixture_id': 'empty', 'method': 'paired replay',
            'steps': ['Open log', 'Save', 'Restart', 'Reopen'],
            'dimensions': {'behavior': 'pass', 'persistence': 'pass'}}

    def write(self):
        (self.root / 'evidence/index.json').write_text(
            json.dumps({'schema_version': 1, 'records': self.records}))
        (self.root / 'spec/coverage.json').write_text(
            json.dumps({'schema_version': 1, 'cases': [self.case]}))
        (self.root / 'comparison.json').write_text(json.dumps(self.comparison))

    def run_validator(self, *extra):
        self.write()
        return subprocess.run(
            [sys.executable, str(HERE / 'validate_spec.py'), '--check-files', *extra],
            cwd=self.root, capture_output=True, text=True)

    def assert_rejected(self, fragment=None):
        result = self.run_validator()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertNotIn('Traceback', result.stderr)
        if fragment:
            self.assertIn(fragment, result.stderr)

    # -- regressions against defects found in the audited version ----------

    def test_valid_paired_comparison_passes(self):
        result = self.run_validator()
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_comparison_cannot_drop_predeclared_requirements(self):
        self.write()
        before = (self.root / 'spec/coverage.json').read_bytes()
        code = ledger.main([
            '--project', str(self.root), 'comparison', '--case-id', self.case['id'],
            '--original-evidence', 'original', '--candidate-evidence', 'candidate',
            '--dimension', 'visual=pass', '--step', 'Look', '--method', 'visual'])
        self.assertEqual(code, 2)
        self.assertEqual((self.root / 'spec/coverage.json').read_bytes(), before)
        self.assertFalse((self.root / 'validation').exists())

    def test_comparison_requires_reason_before_writing(self):
        self.write()
        code = ledger.main([
            '--project', str(self.root), 'comparison', '--case-id', 'new',
            '--original-evidence', 'original', '--candidate-evidence', 'candidate',
            '--dimension', 'visual=pass', '--dimension', 'network=not_applicable',
            '--step', 'Look', '--method', 'visual'])
        self.assertEqual(code, 2)
        self.assertFalse((self.root / 'validation').exists())

    def test_not_applicable_dimension_is_allowed_with_a_reason(self):
        self.comparison['dimensions']['network'] = 'not_applicable'
        self.assert_rejected('no reason for it')
        self.comparison['dimension_reasons'] = {'network': 'feature is offline-only'}
        self.assertEqual(self.run_validator().returncode, 0)

    def test_required_dimension_cannot_be_declared_not_applicable(self):
        self.comparison['dimensions']['persistence'] = 'not_applicable'
        self.comparison['dimension_reasons'] = {'persistence': 'skipped'}
        self.assert_rejected('listed in required_dimensions')

    def test_blocked_requires_a_blocker(self):
        self.case.update(validation='blocked')
        self.case.pop('comparison')
        self.assert_rejected('blocked requires a recorded "blocker"')
        self.case['blocker'] = 'no iOS device available'
        self.assertEqual(self.run_validator().returncode, 0)

    def test_role_typo_is_reported_on_the_evidence_record(self):
        self.records[0]['role'] = 'orignal'
        result = self.run_validator()
        self.assertEqual(result.returncode, 1)
        self.assertIn('evidence[0] (original): "role" must be one of', result.stderr)

    def test_missing_evidence_index_does_not_change_the_return_shape(self):
        errors, records = validate_spec.validate_evidence(
            self.root / 'nope.json', self.root)
        self.assertIsInstance(errors, list)
        self.assertIsInstance(records, dict)

    def test_errors_are_capped_by_default(self):
        self.records = [{'id': f'r{i}'} for i in range(40)]
        self.case.update(validation='not_run', observed=False, evidence_ids=[])
        result = self.run_validator()
        self.assertEqual(result.returncode, 1)
        self.assertIn('more (use --max-errors 0)', result.stderr)
        self.assertLessEqual(result.stderr.count('\n  - '), 25)

    def test_json_report_carries_scope_counts(self):
        result = self.run_validator('--json')
        payload = json.loads(result.stdout)
        self.assertTrue(payload['ok'])
        self.assertEqual(payload['summary']['required'], 1)
        self.assertEqual(payload['summary']['required_passing'], 1)
        self.assertEqual(payload['summary']['critical_not_passing'], [])

    def test_critical_failure_is_surfaced_not_averaged(self):
        self.case.update(validation='blocked', blocker='device unavailable')
        self.case.pop('comparison')
        result = self.run_validator('--json')
        payload = json.loads(result.stdout)
        self.assertEqual(payload['summary']['critical_not_passing'], ['log.saved.android'])

    # -- claims that must still be refused ---------------------------------

    def test_candidate_alone_cannot_prove_observation(self):
        self.case.update(validation='not_run', evidence_ids=['candidate'])
        self.assert_rejected()

    def test_static_evidence_cannot_prove_runtime(self):
        self.records[0]['runtime'] = False
        self.assert_rejected()

    def test_stale_build_hash_cannot_pass(self):
        self.case['candidate_app_sha256'] = 'b' * 64
        self.assert_rejected()

    def test_fixture_mismatch_cannot_pass(self):
        self.records[1]['fixture_id'] = 'other-account'
        self.assert_rejected()

    def test_role_swap_cannot_pass(self):
        self.comparison['original_evidence_ids'] = ['candidate']
        self.assert_rejected()

    def test_placeholder_digest_cannot_pass(self):
        self.records[0]['sha256'] = 'REPLACE_WITH_SHA256_OF_SANITIZED_FILE'
        self.assert_rejected('unreplaced template placeholder')

    def test_tampered_artifact_is_detected(self):
        self.write()
        (self.root / 'evidence/original.png').write_bytes(b'tampered')
        result = subprocess.run(
            [sys.executable, str(HERE / 'validate_spec.py'), '--check-files'],
            cwd=self.root, capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn('sha256 mismatch', result.stderr)

    def test_acceptance_requires_a_decision_record(self):
        self.case['user_testing'] = 'accepted'
        self.assert_rejected()
        decision = self.root / 'spec' / 'decision.md'
        decision.write_text('User accepted 2026-09-21 on build abc.')
        self.case['user_decision'] = 'spec/decision.md'
        self.assertEqual(self.run_validator().returncode, 0)

    def test_path_escape_is_refused(self):
        self.records[0]['path'] = '../outside.png'
        self.assert_rejected('escapes the project root')

    # -- ledger writer ------------------------------------------------------

    def test_ledger_init_then_adopt_then_compare_validates(self):
        root = self.root / 'fresh'
        root.mkdir()
        (root / 'shots').mkdir()
        for role in ('original', 'candidate'):
            pngtool.encode(root / 'shots' / f'{role}.png', 4, 4, solid(4, 4, (9, 9, 9)))

        self.assertEqual(ledger.main(['--project', str(root), 'init']), 0)
        for role in ('original', 'candidate'):
            self.assertEqual(ledger.main([
                '--project', str(root), 'adopt', str(root / 'shots' / f'{role}.png'),
                '--role', role, '--flow', 'log', '--state', 'saved',
                '--platform', 'android', '--app-sha256', hashlib.sha256(role.encode()).hexdigest(),
                '--fixture', 'empty', '--label', f'log.saved.{role}']), 0)

        code = ledger.main([
            '--project', str(root), 'comparison', '--case-id', 'log.saved.android',
            '--original-evidence', 'ev-log.saved.original',
            '--candidate-evidence', 'ev-log.saved.candidate',
            '--dimension', 'visual=pass', '--dimension', 'behavior=pass',
            '--step', 'Open log', '--step', 'Save', '--method', 'paired replay'])
        self.assertEqual(code, 0)

        result = subprocess.run(
            [sys.executable, str(HERE / 'validate_spec.py'), '--check-files', '--json'],
            cwd=root, capture_output=True, text=True)
        payload = json.loads(result.stdout)
        self.assertTrue(payload['ok'], payload['errors'])
        self.assertEqual(payload['summary']['required_passing'], 1)

    def test_ledger_computes_digests_so_none_are_typed(self):
        root = self.root / 'digest'
        root.mkdir()
        shot = root / 'x.png'
        pngtool.encode(shot, 3, 3, solid(3, 3, (7, 7, 7)))
        ledger.main(['--project', str(root), 'init'])
        ledger.main(['--project', str(root), 'adopt', str(shot), '--role', 'original',
                     '--flow', 'f', '--state', 's', '--platform', 'android',
                     '--app-sha256', 'a' * 64, '--fixture', 'fx'])
        record = json.loads((root / 'evidence/index.json').read_text())['records'][0]
        self.assertEqual(record['sha256'], hashlib.sha256(shot.read_bytes()).hexdigest())
        self.assertEqual(record['viewport_px'], '3x3')

    def test_ledger_refuses_to_clobber_a_record(self):
        root = self.root / 'clobber'
        root.mkdir()
        shot = root / 'x.png'
        pngtool.encode(shot, 3, 3, solid(3, 3, (7, 7, 7)))
        args = ['--project', str(root), 'adopt', str(shot), '--role', 'original',
                '--flow', 'f', '--state', 's', '--platform', 'android',
                '--app-sha256', 'a' * 64, '--fixture', 'fx']
        self.assertEqual(ledger.main(args), 0)
        self.assertEqual(ledger.main(args), 2)
        self.assertEqual(ledger.main(args + ['--force']), 0)

    def test_ledger_static_adoption_is_labelled(self):
        root = self.root / 'static'
        root.mkdir()
        note = root / 'n.txt'
        note.write_text('decompiled constant')
        ledger.main(['--project', str(root), 'adopt', str(note), '--role', 'original',
                     '--flow', 'f', '--state', 's', '--platform', 'android',
                     '--app-sha256', 'a' * 64, '--fixture', 'fx', '--static'])
        record = json.loads((root / 'evidence/index.json').read_text())['records'][0]
        self.assertFalse(record['runtime'])
        self.assertTrue(any('UNVERIFIED_STATIC_ONLY' in l for l in record['limitations']))

    def test_ledger_refuses_a_pass_with_a_failing_dimension(self):
        root = self.root / 'refuse'
        root.mkdir()
        for role in ('original', 'candidate'):
            shot = root / f'{role}.png'
            pngtool.encode(shot, 3, 3, solid(3, 3, (7, 7, 7)))
            ledger.main(['--project', str(root), 'adopt', str(shot), '--role', role,
                         '--flow', 'f', '--state', 's', '--platform', 'android',
                         '--app-sha256', 'a' * 64, '--fixture', 'fx', '--label', role])
        code = ledger.main([
            '--project', str(root), 'comparison', '--case-id', 'f.android',
            '--original-evidence', 'ev-original', '--candidate-evidence', 'ev-candidate',
            '--dimension', 'visual=fail', '--step', 'open', '--method', 'replay',
            '--result', 'pass'])
        self.assertEqual(code, 2)

    def test_ledger_rejects_unknown_evidence_reference(self):
        root = self.root / 'unknown'
        root.mkdir()
        ledger.main(['--project', str(root), 'init'])
        code = ledger.main([
            '--project', str(root), 'comparison', '--case-id', 'f.android',
            '--original-evidence', 'nope', '--candidate-evidence', 'nope2',
            '--dimension', 'visual=pass', '--step', 'open', '--method', 'replay'])
        self.assertEqual(code, 2)


# --------------------------------------------------------------------------

class CaptureTests(Temp):
    def setUp(self):
        super().setUp()
        self.counter = 0
        self.args = ['--project', str(self.root), 'capture', '--serial', 'emulator-5554',
                     '--package', 'example.app', '--role', 'original', '--flow', 'f',
                     '--state', 's', '--fixture', 'empty', '--no-hierarchy', '--link-case']
        def shot(serial, path, binary):
            self.counter += 1
            pngtool.encode(path, 1, 1, bytes([self.counter, 0, 0]))
            return 'mock'
        for name, kwargs in (
            ('adb_binary', {'return_value': 'mock'}),
            ('device_environment', {'return_value': {'is_emulator': True,
               'density_dpi': 160, 'device_pixel_ratio': 1}}),
            ('package_build_hash', {'return_value': ('a' * 64, {})}),
            ('grab_screenshot', {'side_effect': shot}),
            ('adb_text', {'return_value': 'mock'}),
        ):
            patcher = patch.object(ledger, name, **kwargs)
            patcher.start()
            self.addCleanup(patcher.stop)

    def records(self):
        return json.loads((self.root / 'evidence/index.json').read_text())['records']

    def test_rejected_capture_preserves_original_bytes(self):
        self.assertEqual(ledger.main(self.args), 0)
        record = self.records()[0]
        before = (self.root / record['path']).read_bytes()
        self.assertEqual(ledger.main(self.args), 2)
        self.assertEqual((self.root / record['path']).read_bytes(), before)

    def test_labels_get_independent_artifacts(self):
        ledger.main(self.args)
        ledger.main(self.args + ['--label', 'second'])
        records = self.records()
        self.assertEqual(len({r['path'] for r in records}), 2)
        for record in records:
            self.assertEqual(ledger.sha256_file(self.root / record['path']), record['sha256'])

    def test_states_get_independent_cases(self):
        ledger.main(self.args)
        ledger.main(self.args + ['--state', 'second'])
        cases = json.loads((self.root / 'spec/coverage.json').read_text())['cases']
        self.assertEqual({c['state_id'] for c in cases}, {'s', 'second'})

    def test_explicit_case_rejects_another_state_before_capture(self):
        ledger.main(self.args + ['--case-id', 'explicit'])
        self.assertEqual(ledger.main(self.args + ['--case-id', 'explicit', '--state', 'other']), 2)
        self.assertEqual(len(self.records()), 1)

    def test_hot_reload_records_source_and_invalidates_previous_pass(self):
        source = self.root / 'main.dart'
        source.write_text('first')
        args = self.args + ['--role', 'candidate', '--runtime-mode', 'hot-reload',
                           '--runtime-source', str(source), '--runtime-session', 'session-1']
        self.assertEqual(ledger.main(args), 0)
        first = self.records()[0]
        coverage_path = self.root / 'spec/coverage.json'
        coverage = json.loads(coverage_path.read_text())
        coverage['cases'][0].update(validation='pass', user_testing='accepted')
        coverage_path.write_text(json.dumps(coverage))
        source.write_text('second')
        self.assertEqual(ledger.main(args + ['--label', 'revision-two']), 0)
        second = self.records()[1]
        self.assertNotEqual(first['runtime_identity'], second['runtime_identity'])
        current = json.loads(coverage_path.read_text())['cases'][0]
        self.assertEqual(current['validation'], 'not_run')
        self.assertEqual(current['user_testing'], 'pending')


class BuildIdentityTests(Temp):
    def test_split_change_changes_build_identity_without_pulling(self):
        split_hash = ['b' * 64]
        def adb_text(serial, *args, **kwargs):
            if args[:3] == ('shell', 'pm', 'path'):
                return 'package:/app/base.apk\npackage:/app/split.apk'
            if 'sha256sum' in args:
                return 'a' * 64 + '  /app/base.apk\n' + split_hash[0] + '  /app/split.apk'
            return 'versionName=1 versionCode=1'
        with patch.object(ledger, 'adb_text', side_effect=adb_text), \
             patch.object(ledger, 'adb', side_effect=AssertionError('unnecessary APK pull')):
            first, _ = ledger.package_build_hash('serial', 'example.app', 'adb', self.root)
            split_hash[0] = 'c' * 64
            second, _ = ledger.package_build_hash('serial', 'example.app', 'adb', self.root)
        self.assertNotEqual(first, second)


class ThemeTests(Temp):
    def test_exact_flat_colours_survive_clustering(self):
        for rgb in ((0, 0, 0), (255, 255, 255), (30, 136, 229)):
            path = self.root / 'flat.png'
            pngtool.encode(path, 2, 2, solid(2, 2, rgb))
            colours, _ = theme_extract.extract_colours([path])
            self.assertEqual(colours[0]['rgb'], list(rgb))
    def test_colours_are_ranked_by_coverage(self):
        width, height = 40, 40
        pixels = bytearray(solid(width, height, (255, 255, 255)))
        for y in range(0, 10):
            for x in range(width):
                o = (y * width + x) * 3
                pixels[o:o + 3] = bytes((0x1E, 0x88, 0xE5))
        path = self.root / 's.png'
        pngtool.encode(path, width, height, bytes(pixels))
        colours, total = theme_extract.extract_colours([path])
        self.assertEqual(total, width * height)
        self.assertGreater(colours[0]['coverage'], 0.7)
        roles = theme_extract.classify(colours)
        self.assertEqual(len({c['hex'] for c in roles.values()}), len(roles),
                         'a colour must not be assigned to two roles')

    def test_spacing_uses_nearest_neighbours_only(self):
        """Three stacked items 16px apart are a 16px rhythm, not 16 and 32."""
        path = self.root / 'h.xml'
        path.write_text('<hierarchy>'
                        '<node bounds="[0,0][100,20]"/>'
                        '<node bounds="[0,36][100,56]"/>'
                        '<node bounds="[0,72][100,92]"/>'
                        '</hierarchy>')
        spacing = theme_extract.extract_spacing([path], dpr=2.0)
        self.assertEqual([g['dp'] for g in spacing['gaps_dp']], [8])
        self.assertEqual(spacing['inferred_base_unit_dp'], 8)

    def test_contrast_ratio_matches_wcag(self):
        self.assertEqual(theme_extract.contrast_ratio((0, 0, 0), (255, 255, 255)), 21.0)

    def test_dp_conversion_requires_density(self):
        shot = self.root / 's.png'
        pngtool.encode(shot, 4, 4, solid(4, 4, (1, 1, 1)))
        hier = self.root / 'h.xml'
        hier.write_text('<hierarchy><node bounds="[0,0][10,10]"/></hierarchy>')
        self.assertEqual(theme_extract.main([str(shot), '--hierarchy', str(hier)]), 2)


# --------------------------------------------------------------------------

class DartExampleTests(Temp):
    @unittest.skipUnless(shutil.which('dart'), 'Dart SDK is not installed')
    def test_documented_refresh_is_bounded_and_shared(self):
        doc = (HERE.parent / 'references/flutter-build.md').read_text()
        example = doc.split('```dart\n', 1)[1].split('```', 1)[0]
        program = self.root / 'refresh_test.dart'
        program.write_text("import 'dart:async';\n" + example + r'''
void check(bool condition, String message) {
  if (!condition) throw StateError(message);
}
Future<void> main() async {
  var calls = 0;
  var refreshes = 0;
  final failing = SessionReader<int>(token: 'old',
    read: (token) async { calls++; throw Unauthorized(); },
    refresh: () async { refreshes++; return 'new'; });
  try { await failing.read(); throw StateError('expected Unauthorized'); }
  on Unauthorized { }
  check(calls == 2 && refreshes == 1, '401 retry must be bounded');

  final gate = Completer<String>();
  refreshes = 0;
  final sent = <String>[];
  final shared = SessionReader<int>(token: 'old',
    read: (token) async {
      sent.add(token);
      if (token == 'old') throw Unauthorized();
      return 7;
    },
    refresh: () { refreshes++; return gate.future; });
  final results = Future.wait([shared.read(), shared.read()]);
  await Future<void>.delayed(Duration.zero);
  check(refreshes == 1, 'concurrent refresh must be shared');
  gate.complete('new');
  check((await results).every((v) => v == 7), 'both reads must finish');
  check(sent.where((v) => v == 'new').length == 2, 'new token must be applied');

  final brokenGate = Completer<String>();
  refreshes = 0;
  final broken = SessionReader<int>(token: 'old',
    read: (_) async => throw Unauthorized(),
    refresh: () { refreshes++; return brokenGate.future; });
  Future<bool> fails() async {
    try { await broken.read(); return false; }
    on StateError { return true; }
  }
  final failures = Future.wait([fails(), fails()]);
  await Future<void>.delayed(Duration.zero);
  brokenGate.completeError(StateError('refresh failed'));
  check((await failures).every((v) => v), 'refresh error must reach every waiter');
  check(refreshes == 1, 'failed refresh must also be shared');
}
''')
        result = subprocess.run(['dart', 'run', str(program)],
                                capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


@unittest.skipIf(os.name == 'nt' or not shutil.which('bash'), 'Bash compatibility tests require POSIX and Bash')
class EmulatorScriptTests(Temp):
    SCRIPT = HERE / 'emulator_manager.sh'

    def fake(self, name, body):
        path = self.root / name
        path.write_text(body)
        path.chmod(0o755)
        return path

    def run_script(self, verb, *args, **env):
        return subprocess.run(['bash', str(self.SCRIPT), verb, *args], capture_output=True, text=True,
                              env={**os.environ, **env})

    def test_install_checks_identity_and_does_not_grant_permissions(self):
        adb = self.fake('adb', '#!/bin/sh\ncase "$*" in\n'
                        'devices) printf "List\\nemulator-5554\\tdevice\\n";;\n'
                        '*"avd name"*) echo "$ACTUAL_AVD";;\n'
                        '*install*) printf "%s" "$*" > "$INSTALL_MARKER";;\nesac\n')
        apk = self.root / 'app.apk'
        apk.write_bytes(b'apk')
        marker = self.root / 'installed'
        env = dict(DITTO_ADB=str(adb), DITTO_AVD='wanted',
                   DITTO_EMULATOR_PORT='5554', INSTALL_MARKER=str(marker))
        result = self.run_script('install', str(apk), ACTUAL_AVD='other', **env)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(marker.exists())
        result = self.run_script('install', str(apk), ACTUAL_AVD='wanted', **env)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn('-g', marker.read_text().split())

    def test_refuses_to_stop_a_different_avd(self):
        adb = self.fake('adb', '#!/bin/sh\ncase "$*" in\n'
                               'devices) printf "List\\nemulator-5554\\tdevice\\n";;\n'
                               '*"avd name"*) echo other;;\n'
                               '*kill*) touch "$KILL_MARKER";;\nesac\n')
        marker = self.root / 'killed'
        result = self.run_script('stop', DITTO_ADB=str(adb), DITTO_AVD='wanted',
                          DITTO_EMULATOR_PORT='5554', KILL_MARKER=str(marker))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("expected 'wanted'", result.stderr)
        self.assertFalse(marker.exists())

    def test_requires_an_explicit_avd(self):
        adb = self.fake('adb', '#!/bin/sh\nexit 0\n')
        result = self.run_script('stop', DITTO_ADB=str(adb), DITTO_AVD='')
        self.assertEqual(result.returncode, 1)
        self.assertIn('Set DITTO_AVD', result.stderr)

    def test_running_emulator_is_reused_not_relaunched(self):
        adb = self.fake('adb', '#!/bin/sh\ncase "$*" in\n'
                               'devices) printf "List\\nemulator-5554\\tdevice\\n";;\n'
                               '*"avd name"*) echo wanted;;\n'
                               '*sys.boot_completed*) echo 1;;\n'
                               '*"wm size"*) echo "Physical size: 1080x2400";;\n'
                               '*"wm density"*) echo "Physical density: 420";;\n'
                               'esac\n')
        emulator = self.fake('emulator', '#!/bin/sh\ntouch "$LAUNCH_MARKER"\n')
        marker = self.root / 'launched'
        result = self.run_script('start-headless', DITTO_ADB=str(adb), DITTO_EMULATOR=str(emulator),
                          DITTO_AVD='wanted', DITTO_EMULATOR_PORT='5554',
                          LAUNCH_MARKER=str(marker))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('Reusing emulator-5554', result.stdout)
        self.assertIn('420', result.stdout)
        self.assertFalse(marker.exists())


if __name__ == '__main__':
    unittest.main()
