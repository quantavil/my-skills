"""Phase store and schema regressions."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent.parent / 'scripts'
sys.path.insert(0, str(HERE))

import phase_store as store  # noqa: E402


def contract():
    return {
        'schema_version': 1,
        'phase_id': 'daily_logging',
        'revision': 1,
        'scope': {'summary': 'Daily log', 'unknowns': []},
        'platform': 'android_flutter',
        'fixtures': {'default': {'revision': 1}},
        'checkpoints': [{
            'number': 1,
            'id': 'log_top',
            'fixture': 'default',
            'setup': 'Period recorded',
            'actions': ['Tap Log'],
            'artifacts': ['png', 'xml'],
            'required_dimensions': ['visual', 'layout'],
            'dependencies': ['theme'],
        }],
        'reverse_engineering': {'include_globs': ['res/drawable*/*'], 'questions': []},
        'dependency_graph': {
            'components': ['theme'],
            'path_rules': [{'glob': 'lib/theme/**', 'components': ['theme']}],
            'component_edges': {},
        },
        'ownership': {'files': {}, 'checkpoints': {}},
        'authorized_differences': [],
    }


def status():
    return {
        'schema_version': 1,
        'phase_id': 'daily_logging',
        'phase_revision': 1,
        'state': 'preflight',
        'preflight_revision': None,
        'original_manifest_revision': None,
        'clone_manifest_revisions': [],
        'active_clone_manifest_revision': None,
        'checkpoints': {},
        'invalidation_history': [],
        'human_review': {'status': 'pending', 'history': []},
        'blockers': [],
    }


class PhaseStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='ditto-phase-store-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_valid_contract_and_status_are_returned(self):
        value = contract()
        self.assertIs(store.validate_contract(value, 'daily_logging'), value)
        current = status()
        self.assertIs(store.validate_status(current, value), current)

    def test_records_have_json_schemas_and_reject_coerced_numbers(self):
        self.assertIn('properties', store.ContractModel.model_json_schema())
        self.assertIn('properties', store.StatusModel.model_json_schema())
        value = contract()
        value['revision'] = True
        with self.assertRaises(store.PhaseError):
            store.validate_contract(value)

    def test_contract_rejects_duplicate_checkpoint_identity(self):
        for field in ('number', 'id'):
            with self.subTest(field=field):
                value = contract()
                duplicate = dict(value['checkpoints'][0])
                duplicate['number' if field == 'id' else 'id'] = 2 if field == 'id' else 'other'
                value['checkpoints'].append(duplicate)
                with self.assertRaisesRegex(store.PhaseError, 'duplicate checkpoint'):
                    store.validate_contract(value)

    def test_contract_rejects_unsafe_ids_artifacts_and_dimensions(self):
        mutations = (
            ('phase id', lambda x: x.update(phase_id='../escape')),
            ('checkpoint id', lambda x: x['checkpoints'][0].update(id='Bad-ID')),
            ('artifact', lambda x: x['checkpoints'][0].update(artifacts=['mp4'])),
            ('dimension', lambda x: x['checkpoints'][0].update(required_dimensions=[])),
        )
        for label, mutate in mutations:
            with self.subTest(label=label):
                value = contract()
                mutate(value)
                with self.assertRaises(store.PhaseError):
                    store.validate_contract(value)

    def test_contract_rejects_unknown_dependencies_and_bad_path_rules(self):
        value = contract()
        value['checkpoints'][0]['dependencies'] = ['missing']
        with self.assertRaisesRegex(store.PhaseError, 'unknown dependency'):
            store.validate_contract(value)

        value = contract()
        value['dependency_graph']['path_rules'] = [{'glob': '../outside', 'components': ['theme']}]
        with self.assertRaisesRegex(store.PhaseError, 'path rule'):
            store.validate_contract(value)

    def test_status_rejects_unknown_checkpoint_and_bad_revision(self):
        current = status()
        current['checkpoints']['missing'] = {'invalidated': False}
        with self.assertRaisesRegex(store.PhaseError, 'unknown checkpoint'):
            store.validate_status(current, contract())

        current = status()
        current['phase_revision'] = 2
        with self.assertRaisesRegex(store.PhaseError, 'phase revision'):
            store.validate_status(current, contract())

    def test_atomic_json_round_trip_and_immutable_refusal(self):
        path = self.root / 'nested' / 'record.json'
        store.atomic_write_json(path, {'value': 1})
        self.assertEqual(store.load_json(path), {'value': 1})
        store.write_immutable_json(self.root / 'immutable.json', {'value': 2})
        with self.assertRaisesRegex(store.PhaseError, 'already exists'):
            store.write_immutable_json(self.root / 'immutable.json', {'value': 3})

    def test_load_json_rejects_non_object_and_invalid_json(self):
        path = self.root / 'bad.json'
        path.write_text('[]', encoding='utf-8')
        with self.assertRaisesRegex(store.PhaseError, 'JSON object'):
            store.load_json(path)
        path.write_text('{', encoding='utf-8')
        with self.assertRaisesRegex(store.PhaseError, 'valid JSON'):
            store.load_json(path)

    def test_safe_paths_and_names(self):
        self.assertEqual(store.safe_child(self.root, 'a/b'), self.root / 'a' / 'b')
        for value in ('../outside', '/tmp/outside'):
            with self.subTest(value=value), self.assertRaisesRegex(store.PhaseError, 'inside'):
                store.safe_child(self.root, value)
        self.assertEqual(store.checkpoint_stem(contract()['checkpoints'][0], 2),
                         '001_log_top.r002')
        self.assertEqual(store.versioned_path(self.root, 'manifest', 2, 'json'),
                         self.root / 'manifest.002.json')

    def test_sha256_file(self):
        path = self.root / 'bytes'
        path.write_bytes(b'abc')
        self.assertEqual(store.sha256_file(path),
                         'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad')

    def test_phase_lock_refuses_competing_writer_and_releases(self):
        phase = self.root / 'phase'
        phase.mkdir()
        with store.phase_lock(phase):
            with self.assertRaisesRegex(store.PhaseError, 'locked'):
                with store.phase_lock(phase):
                    pass
        with store.phase_lock(phase):
            lock_data = json.loads((phase / '.ditto.lock').read_text(encoding='utf-8'))
            self.assertIn('pid', lock_data)
            self.assertIn('created_at', lock_data)
        self.assertFalse((phase / '.ditto.lock').exists())


if __name__ == '__main__':
    unittest.main()
