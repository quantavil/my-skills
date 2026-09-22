"""Read-only workflow and graph regressions."""
import contextlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import ditto
import ledger


class WorkflowTests(unittest.TestCase):
    def test_standard_sdk_adb_discovery_without_sdk_env_or_path(self):
        with tempfile.TemporaryDirectory() as directory:
            for platform in ('linux', 'win32'):
                with self.subTest(platform=platform):
                    base = Path(directory) / platform
                    executable = base / 'Android' / 'Sdk' / 'platform-tools' / (
                        'adb.exe' if platform == 'win32' else 'adb')
                    executable.parent.mkdir(parents=True)
                    executable.write_bytes(b'fake executable')
                    with patch.dict(ledger.os.environ, {'LOCALAPPDATA': str(base)}, clear=True), \
                         patch.object(ledger.sys, 'platform', platform), \
                         patch.object(ledger.Path, 'home', return_value=base), \
                         patch.object(ledger.shutil, 'which', return_value=None):
                        self.assertEqual(ledger.adb_binary(), str(executable))

    def test_windows_sdk_adb_discovery(self):
        with tempfile.TemporaryDirectory() as directory:
            sdk = Path(directory) / 'SDK with spaces'
            executable = sdk / 'platform-tools' / 'adb.exe'
            executable.parent.mkdir(parents=True)
            executable.write_bytes(b'fake executable')
            with patch.dict(ledger.os.environ, {'ANDROID_HOME': str(sdk)}, clear=True), \
                 patch.object(ledger.sys, 'platform', 'win32'), \
                 patch.object(ledger.shutil, 'which', return_value=None):
                self.assertEqual(ledger.adb_binary(), str(executable))

    def load(self, data):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'coverage.json'
            path.write_text(json.dumps(data))
            return ditto.graph_data(path)

    def test_no_invented_edges_and_compact_status(self):
        cases, edges = self.load({'cases': [
            {'id': 'a', 'observed': True, 'implemented': False}, {'id': 'b'}]})
        rendered = ditto.mermaid(cases, edges)
        self.assertNotIn('-->', rendered)
        self.assertIn('a #124; not_run', rendered)
        self.assertNotIn('observed', rendered)
        self.assertNotIn('implemented', rendered)

    def test_graph_preserves_branch_and_back_edges(self):
        edges = [{'from': 'a', 'to': 'b', 'action': 'Next'},
                 {'from': 'a', 'to': 'c', 'action': 'Skip'},
                 {'from': 'b', 'to': 'a', 'action': 'Back'}]
        cases, edges = self.load({'cases': [{'id': i} for i in 'abc'], 'transitions': edges})
        output = ditto.mermaid(cases, edges)
        self.assertIn('n0 -->|"Next"| n1', output)
        self.assertIn('n0 -->|"Skip"| n2', output)
        self.assertIn('n1 -->|"Back"| n0', output)

    def test_unknown_endpoint_and_duplicate_ids_rejected(self):
        with self.assertRaises(ValueError):
            self.load({'cases': [{'id': 'a'}], 'transitions': [
                {'from': 'a', 'to': 'missing', 'action': 'Next'}]})
        with self.assertRaises(ValueError):
            self.load({'cases': [{'id': 'a'}, {'id': 'a'}]})

    def test_labels_cannot_inject_markup(self):
        output = ditto.mermaid([{'id': 'x"\nclick n0 "evil"<script>'}], [])
        self.assertNotIn('<script>', output)
        self.assertEqual(output.count('\n'), 2)
        self.assertIn('#34;', output)

    def test_only_check_hashes_artifacts_and_both_propagate_failure(self):
        with patch.object(ditto, 'graph_data', return_value=([], [])), \
             patch.object(ditto.validate_spec, 'validate_evidence',
                          return_value=(['bad evidence'], {})) as validate, \
             patch.object(ditto.validate_spec, 'validate_coverage', return_value=([], {})), \
             contextlib.redirect_stdout(io.StringIO()), \
             contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(ditto.main(['check']), 1)
            self.assertTrue(validate.call_args.args[2])
            self.assertEqual(ditto.main(['report']), 1)
            self.assertFalse(validate.call_args.args[2])

    def test_malformed_graph_does_not_hide_record_errors_or_statuses(self):
        with patch.object(ditto, 'graph_data', side_effect=ValueError('bad transition')), \
             patch.object(ditto.validate_spec, 'validate_evidence',
                          return_value=(['bad evidence'], {})), \
             patch.object(ditto.validate_spec, 'validate_coverage', return_value=(
                 ['bad coverage'], {'a': {'id': 'a', 'observed': True,
                    'implemented': False, 'validation': 'not_run', 'user_testing': 'pending'}})), \
             contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(ditto.main(['report']), 1)
            report = json.loads(output.getvalue())
            self.assertEqual(report['error_count'], 3)
            self.assertIn('bad evidence', report['errors'])
            self.assertIn('bad coverage', report['errors'])
            self.assertIn('bad transition', ' '.join(report['errors']))
            self.assertTrue(report['cases'][0]['observed'])
            self.assertFalse(report['cases'][0]['implemented'])
            with contextlib.redirect_stderr(io.StringIO()) as errors:
                self.assertEqual(ditto.main(['check']), 1)
            self.assertIn('bad evidence', errors.getvalue())
            self.assertIn('bad coverage', errors.getvalue())
            self.assertIn('bad transition', errors.getvalue())

    def test_graph_failure_remains_strict(self):
        with patch.object(ditto, 'graph_data', side_effect=ValueError('bad transition')), \
             contextlib.redirect_stdout(io.StringIO()) as output, \
             contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(ditto.main(['graph']), 2)
        self.assertEqual(output.getvalue(), '')

    def test_report_skips_missing_artifact_check_but_check_detects_it(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'spec').mkdir()
            (root / 'evidence').mkdir()
            (root / 'spec/coverage.json').write_text(json.dumps({
                'schema_version': 1, 'cases': []}), encoding='utf-8')
            (root / 'evidence/index.json').write_text(json.dumps({
                'schema_version': 1, 'records': [{
                    'id': 'capture', 'role': 'original', 'runtime': True,
                    'flow_id': 'entry', 'state_id': 'welcome', 'platform': 'android',
                    'kind': 'screenshot', 'path': 'evidence/missing.png',
                    'sha256': 'a' * 64, 'app_sha256': 'b' * 64,
                }]}), encoding='utf-8')
            command = [sys.executable, str(Path(ditto.__file__).resolve())]
            report = subprocess.run(command + ['report'], cwd=root,
                                    capture_output=True, text=True, timeout=10)
            self.assertEqual(report.returncode, 0, report.stderr + report.stdout)
            self.assertFalse(json.loads(report.stdout)['files_checked'])
            checked = subprocess.run(command + ['check'], cwd=root,
                                     capture_output=True, text=True, timeout=10)
            self.assertEqual(checked.returncode, 1)
            self.assertIn('not on disk', checked.stderr)


if __name__ == '__main__':
    unittest.main()
