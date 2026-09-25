#!/usr/bin/env python3
"""Current Ditto phase workspace and compact status."""
from pathlib import Path
import shutil

import phase_store as store


def phase_directory(project, phase_id):
    store._id(phase_id, 'phase id')
    return store.safe_child(Path(project), Path('phases') / phase_id)


def _initial_contract(phase_id):
    return {
        'schema_version': 1, 'phase_id': phase_id, 'revision': 1,
        'scope': {'summary': '', 'unknowns': ['scope_not_defined']},
        'platform': 'android_flutter',
        'runtime_target': {'kind': 'emulator', 'id': ''},
        'fixtures': {}, 'checkpoints': [],
        'reverse_engineering': {'include_globs': [], 'questions': []},
        'dependency_graph': {'components': [], 'path_rules': [], 'component_edges': {}},
        'ownership': {'files': {}, 'checkpoints': {}},
        'authorized_differences': [],
    }


def _initial_status(phase_id):
    return {
        'schema_version': 1, 'phase_id': phase_id, 'phase_revision': 1,
        'state': 'preflight', 'preflight_revision': None,
        'original_manifest_revision': None, 'clone_manifest_revisions': [],
        'active_clone_manifest_revision': None, 'checkpoints': {},
        'invalidation_history': [],
        'human_review': {'status': 'pending', 'history': []}, 'blockers': [],
    }


def init_phase(project, phase_id):
    phase = phase_directory(project, phase_id)
    if phase.exists():
        raise store.PhaseError(f'phase already exists: {phase}')
    phase.mkdir(parents=True)
    try:
        for role in ('original', 'clone', 'diff'):
            (phase / role).mkdir()
        contract = _initial_contract(phase_id)
        store.validate_contract(contract, phase_id)
        store.atomic_write_json(phase / 'phase.json', contract)
        store.atomic_write_json(phase / 'status.json', _initial_status(phase_id))
        (phase / 'notes.md').write_text(f'# {phase_id}\n', encoding='utf-8')
    except Exception:
        shutil.rmtree(phase, ignore_errors=True)
        raise
    return phase


def load_phase(project, phase_id):
    phase = phase_directory(project, phase_id)
    contract = store.load_json(phase / 'phase.json')
    status = store.load_json(phase / 'status.json')
    store.validate_status(status, contract)
    return phase, contract, status


def require_collection_state(project, phase_id):
    phase, contract, status = load_phase(project, phase_id)
    if status['state'] != 'collecting_original' or status['preflight_revision'] is None:
        raise store.PhaseError('successful active preflight is required before collection')
    return phase, contract, status


def freeze_original(project, phase_id):
    import phase_current
    return phase_current.freeze_original(project, phase_id)


def phase_report(project, phase_id):
    phase, contract, status = load_phase(project, phase_id)
    checkpoints = status.get('checkpoints', {})
    closed = sum(bool(item.get('closed')) for item in checkpoints.values())
    return {
        'phase_id': phase_id, 'state': status['state'],
        'checkpoint_counts': {'total': len(contract['checkpoints']), 'closed': closed,
                              'open': len(contract['checkpoints']) - closed},
        'invalidations': len(status.get('invalidation_history', [])),
        'human_review': status['human_review']['status'],
        'original_manifest': str(phase / 'original/manifest.json')
        if (phase / 'original/manifest.json').is_file() else None,
        'clone_manifest': str(phase / 'clone/manifest.json')
        if (phase / 'clone/manifest.json').is_file() else None,
        'report': str(phase / 'diff/report.json')
        if (phase / 'diff/report.json').is_file() else None,
    }
