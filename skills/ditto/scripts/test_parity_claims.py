"""Regression tests for unsupported parity claims; exercises the real CLI."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).with_name('validate_spec.py')


class ParityClaimsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='ditto-claims-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'evidence').mkdir()
        (self.root / 'spec').mkdir()
        self.records = []
        for role in ('original', 'candidate'):
            payload = role.encode()
            (self.root / 'evidence' / role).write_bytes(payload)
            self.records.append(dict(id=role, role=role, runtime=True,
                path=f'evidence/{role}', sha256=hashlib.sha256(payload).hexdigest(),
                app_sha256=hashlib.sha256(payload).hexdigest(), platform='android',
                flow_id='log', state_id='saved', fixture_id='empty'))
        self.case = dict(id='log.save.android', flow_id='log', platform='android',
            state_id='saved', original_app_sha256=self.records[0]['app_sha256'],
            candidate_app_sha256=self.records[1]['app_sha256'],
            observed=True, implemented=True, validation='pass',
            evidence_ids=['original', 'candidate'], comparison='comparison.json',
            required_dimensions=['behavior', 'persistence'], user_testing='pending')
        self.comparison = dict(case_id=self.case['id'], result='pass',
            original_evidence_ids=['original'], candidate_evidence_ids=['candidate'],
            fixture_id='empty', method='paired manual replay',
            steps=['Open log', 'Save', 'Restart', 'Reopen'],
            dimensions={'behavior': 'pass', 'persistence': 'pass'})

    def run_validator(self):
        (self.root / 'evidence/index.json').write_text(json.dumps(dict(schema_version=1, records=self.records)))
        (self.root / 'spec/coverage.json').write_text(json.dumps(dict(schema_version=1, cases=[self.case])))
        (self.root / 'comparison.json').write_text(json.dumps(self.comparison))
        return subprocess.run([sys.executable, str(SCRIPT), '--check-files'],
            cwd=self.root, capture_output=True, text=True)

    def assert_rejected(self):
        result = self.run_validator()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertNotIn('Traceback', result.stderr)

    def test_valid_paired_comparison(self):
        result = self.run_validator()
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_pass_requires_comparison(self):
        del self.case['comparison']
        self.assert_rejected()

    def test_candidate_alone_cannot_prove_observation(self):
        self.case.update(validation='not_run', evidence_ids=['candidate'])
        self.assert_rejected()

    def test_static_original_cannot_prove_runtime(self):
        self.records[0]['runtime'] = False
        self.assert_rejected()

    def test_failed_dimension_cannot_pass(self):
        self.comparison['dimensions']['persistence'] = 'fail'
        self.assert_rejected()

    def test_missing_required_dimension_cannot_pass(self):
        del self.comparison['dimensions']['persistence']
        self.assert_rejected()

    def test_wrong_case_comparison_cannot_pass(self):
        self.comparison['case_id'] = 'another-case'
        self.assert_rejected()

    def test_role_swapped_comparison_cannot_pass(self):
        self.comparison['original_evidence_ids'] = ['candidate']
        self.assert_rejected()

    def test_missing_hash_cannot_pass(self):
        del self.records[0]['sha256']
        self.assert_rejected()

    def test_user_acceptance_requires_record(self):
        self.case['user_testing'] = 'accepted'
        self.assert_rejected()

    def test_malformed_record_reports_error(self):
        self.records.append(None)
        self.assert_rejected()

    def test_missing_coverage_fails(self):
        self.run_validator()
        (self.root / 'spec/coverage.json').unlink()
        result = subprocess.run([sys.executable, str(SCRIPT)], cwd=self.root,
            capture_output=True, text=True)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)

    def test_stale_candidate_build_cannot_pass(self):
        self.case['candidate_app_sha256'] = 'b' * 64
        self.assert_rejected()

    def test_wrong_checkpoint_cannot_pass(self):
        self.records[0]['state_id'] = 'opened-not-saved'
        self.assert_rejected()

    def test_missing_flow_cannot_pass(self):
        del self.case['flow_id']
        for record in self.records:
            del record['flow_id']
        self.assert_rejected()

    def test_string_observed_rejected(self):
        self.case.update(observed='true', validation='not_run')
        self.assert_rejected()

    def test_exclusion_requires_reason(self):
        self.case['validation'] = 'not_applicable'
        self.assert_rejected()

    def test_malformed_build_hash_reports_error(self):
        self.records[0]['app_sha256'] = 123
        self.assert_rejected()


if __name__ == '__main__':
    unittest.main()
