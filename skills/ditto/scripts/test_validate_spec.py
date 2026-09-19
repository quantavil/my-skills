"""Unit tests for validate_spec.py."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).with_name('validate_spec.py')


class ValidateSpecTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='ditto-val-test-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.evidence_dir = self.root / 'evidence'
        self.spec_dir = self.root / 'spec'
        self.evidence_dir.mkdir()
        self.spec_dir.mkdir()

    def run_val(self, *args):
        cmd = [sys.executable, str(SCRIPT),
               '--evidence', str(self.evidence_dir / 'index.json'),
               '--coverage', str(self.spec_dir / 'coverage.json'),
               '--root', str(self.root),
               *args]
        return subprocess.run(cmd, capture_output=True, text=True)

    def test_valid_contracts_pass(self):
        # Create an artifact
        shot = self.evidence_dir / 'screen.png'
        shot.write_bytes(b'dummy-png-data')
        import hashlib
        sha = hashlib.sha256(b'dummy-png-data').hexdigest()

        evidence_data = {
            "schema_version": 1,
            "records": [{
                "id": "ev-001",
                "kind": "screenshot",
                "path": "evidence/screen.png",
                "sha256": sha,
                "app_sha256": "abcdef1234567890",
                "platform": "android",
                "state_id": "home.ready",
                "flow_id": "open-app",
                "capture": {"tool": "adb", "version": "1.0.41"}
            }]
        }
        coverage_data = {
            "schema_version": 1,
            "cases": [{
                "id": "open-app.android",
                "flow_id": "open-app",
                "platform": "android",
                "required": True,
                "observed": True,
                "implemented": False,
                "validation": "not_run",
                "evidence_ids": ["ev-001"],
                "blocker": None
            }]
        }
        (self.evidence_dir / 'index.json').write_text(json.dumps(evidence_data))
        (self.spec_dir / 'coverage.json').write_text(json.dumps(coverage_data))

        res = self.run_val('--check-files')
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("passed successfully", res.stdout)

    def test_catches_unreplaced_placeholders(self):
        evidence_data = {
            "schema_version": 1,
            "records": [{
                "id": "ev-001",
                "path": "evidence/screen.png",
                "sha256": "REPLACE_WITH_SHA256_OF_SANITIZED_FILE"
            }]
        }
        (self.evidence_dir / 'index.json').write_text(json.dumps(evidence_data))
        res = self.run_val()
        self.assertEqual(res.returncode, 1)
        self.assertIn("Unreplaced template placeholder", res.stderr)

    def test_catches_observed_without_evidence(self):
        evidence_data = {"schema_version": 1, "records": []}
        coverage_data = {
            "schema_version": 1,
            "cases": [{
                "id": "flow-001",
                "observed": True,
                "validation": "not_run",
                "evidence_ids": []
            }]
        }
        (self.evidence_dir / 'index.json').write_text(json.dumps(evidence_data))
        (self.spec_dir / 'coverage.json').write_text(json.dumps(coverage_data))
        res = self.run_val()
        self.assertEqual(res.returncode, 1)
        self.assertIn("claimed 'observed: true' but 'evidence_ids' is empty", res.stderr)

    def test_catches_nonexistent_evidence_reference(self):
        evidence_data = {"schema_version": 1, "records": []}
        coverage_data = {
            "schema_version": 1,
            "cases": [{
                "id": "flow-001",
                "observed": False,
                "validation": "not_run",
                "evidence_ids": ["ev-missing"]
            }]
        }
        (self.evidence_dir / 'index.json').write_text(json.dumps(evidence_data))
        (self.spec_dir / 'coverage.json').write_text(json.dumps(coverage_data))
        res = self.run_val()
        self.assertEqual(res.returncode, 1)
        self.assertIn("referenced evidence ID 'ev-missing' not found in evidence index", res.stderr)


if __name__ == '__main__':
    unittest.main()
