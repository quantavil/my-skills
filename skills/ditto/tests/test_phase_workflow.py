"""Phase CLI and workspace regressions."""
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent.parent / 'scripts'
sys.path.insert(0, str(HERE))

import ditto  # noqa: E402
import phase_capture  # noqa: E402
import phase_store as store  # noqa: E402


class PhaseWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='ditto-phase-workflow-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_init_creates_new_phase_workspace(self):
        self.assertEqual(ditto.main([
            'phase', 'init', 'daily_logging', '--project', str(self.root)]), 0)
        phase = self.root / 'phases/daily_logging'
        for relative in ('phase.json', 'status.json', 'notes.md',
                         'original', 'clone', 'diff'):
            self.assertTrue((phase / relative).exists(), relative)
        contract = store.validate_contract(store.load_json(phase / 'phase.json'))
        status = store.validate_status(store.load_json(phase / 'status.json'), contract)
        self.assertEqual(status['state'], 'preflight')

    def test_typer_exposes_phase_commands_without_changing_cli_shape(self):
        from typer.main import get_command
        root = get_command(ditto.app)
        self.assertIn('phase', root.commands)
        self.assertIn('select-original', root.commands['phase'].commands)
        self.assertIn('capture-clone', root.commands['phase'].commands)

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
                 contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(ditto.main([command]), 2)
