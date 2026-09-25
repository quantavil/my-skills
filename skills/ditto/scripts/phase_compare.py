#!/usr/bin/env python3
"""Semantic verdicts and readiness for one current Ditto evidence set."""
from datetime import datetime, timezone
import fnmatch
from pathlib import Path

import phase_capture
import phase_current
import phase_store as store

EVIDENCE_KINDS = {
    'visual': {'visual_result', 'triptych', 'png'},
    'layout': {'layout_result', 'xml', 'triptych', 'png'},
    'behavior': {'trace'}, 'navigation': {'trace'},
    'persistence': {'state', 'trace'}, 'platform': {'state', 'trace'},
    'network': {'network'}, 'accessibility': {'semantics'},
}
FULL_PHASE_COMPONENTS = {'native_build', 'global_assets', 'dependency_upgrade'}


class ReadinessError(store.PhaseError):
    def __init__(self, errors):
        self.errors = errors
        super().__init__('automated readiness failed: ' + '; '.join(errors))


def _now():
    return datetime.now(timezone.utc).isoformat()


def _check_result(phase, checkpoint, current):
    name = current.get('active_result')
    if not isinstance(name, str):
        raise store.PhaseError(f"{checkpoint['id']} has no current result")
    path = store.safe_child(phase / 'diff', name)
    if store.sha256_file(path) != current.get('result_sha256'):
        raise store.PhaseError(f"{checkpoint['id']} current result hash differs")
    result = store.load_json(path)
    triptych = store.safe_child(phase / 'diff', result['triptych'])
    if store.sha256_file(triptych) != current.get('triptych_sha256'):
        raise store.PhaseError(f"{checkpoint['id']} triptych hash differs")
    return result


def record_verdict(project, phase_id, checkpoint_id, dimension, verdict_status,
                   rationale, evidence, authorization=None):
    phase, contract, status = phase_capture.load_phase(project, phase_id)
    checkpoint = phase_current._checkpoint(contract, checkpoint_id)
    if dimension not in checkpoint['required_dimensions']:
        raise store.PhaseError(f'{dimension} is not required for {checkpoint_id}')
    if verdict_status not in ('pass', 'fail', 'accepted_difference', 'proposed_difference'):
        raise store.PhaseError('verdict status is invalid')
    if not isinstance(rationale, str) or not rationale.strip():
        raise store.PhaseError('verdict rationale must be nonempty')
    if not isinstance(evidence, list) or not evidence:
        raise store.PhaseError('verdict needs evidence IDs')
    current = status['checkpoints'].get(checkpoint_id, {})
    if current.get('invalidated'):
        raise store.PhaseError('checkpoint comparison is invalidated')
    result = _check_result(phase, checkpoint, current)
    catalog = result.get('evidence_catalog', {})
    for identifier in evidence:
        if identifier not in catalog:
            raise store.PhaseError(f'unknown evidence ID: {identifier}')
        if catalog[identifier]['kind'] not in EVIDENCE_KINDS[dimension]:
            raise store.PhaseError(f'{identifier} cannot support {dimension}')
    if verdict_status == 'accepted_difference':
        authorized = {item['id'] for item in contract['authorized_differences']}
        if authorization not in authorized:
            raise store.PhaseError('accepted difference needs authorization')
    elif verdict_status == 'proposed_difference':
        if not isinstance(authorization, str) or not authorization.strip():
            raise store.PhaseError('proposed difference needs proposal metadata')
    elif authorization is not None:
        raise store.PhaseError('authorization only applies to differences')
    verdict = {
        'status': verdict_status, 'rationale': rationale.strip(),
        'evidence': evidence, 'authorization': authorization,
        'recorded_at': _now(),
        'changed_ratio': result.get('changed_ratio') if dimension == 'visual' else None,
    }
    with store.phase_lock(phase):
        _, same_contract, latest = phase_capture.load_phase(project, phase_id)
        if same_contract != contract or latest != status:
            raise store.PhaseError('phase changed while recording verdict')
        current = latest['checkpoints'][checkpoint_id]
        current['dimensions'][dimension] = verdict
        current['closed'] = all(item['status'] in ('pass', 'accepted_difference')
                                for item in current['dimensions'].values())
        if verdict_status == 'fail':
            latest['state'] = 'correcting'
        phase_current.write_report(phase, contract, latest)
        store.atomic_write_json(phase / 'status.json', latest)
    return verdict


def _affected(contract, paths):
    if not isinstance(paths, list) or not paths or any(
            not isinstance(path, str) or not path for path in paths):
        raise store.PhaseError('changed paths must be a nonempty list')
    graph = contract['dependency_graph']
    rules = graph['path_rules']
    uncovered = [path for path in paths if not any(
        fnmatch.fnmatchcase(path, rule['glob']) for rule in rules)]
    components = {component for path in paths for rule in rules
                  if fnmatch.fnmatchcase(path, rule['glob'])
                  for component in rule['components']}
    pending = list(components)
    while pending:
        component = pending.pop()
        for target in graph['component_edges'].get(component, []):
            if target not in components:
                components.add(target)
                pending.append(target)
    all_ids = {item['id'] for item in contract['checkpoints']}
    if uncovered or components & FULL_PHASE_COMPONENTS:
        return all_ids, sorted(components), uncovered
    affected = {item['id'] for item in contract['checkpoints']
                if components & set(item['dependencies'])}
    return affected, sorted(components), uncovered


def affected_checkpoints(contract, changed_paths):
    affected, components, _ = _affected(contract, changed_paths)
    return affected, components


def invalidate(project, phase_id, changed_paths):
    phase, contract, status = phase_capture.load_phase(project, phase_id)
    affected, components, uncovered = _affected(contract, changed_paths)
    record = {'timestamp': _now(), 'changed_paths': changed_paths,
              'resolved_components': components, 'uncovered_paths': uncovered,
              'reopened_checkpoints': sorted(affected),
              'reason': 'uncovered paths require full review' if uncovered
              else 'contract dependency impact'}
    with store.phase_lock(phase):
        _, same_contract, latest = phase_capture.load_phase(project, phase_id)
        if same_contract != contract or latest != status:
            raise store.PhaseError('phase changed during invalidation')
        for identifier in affected:
            current = latest['checkpoints'].get(identifier)
            if current:
                phase_current._reset_checkpoint(current)
                current['invalidated_at'] = _now()
        latest['invalidation_history'].append(record)
        if affected:
            latest['state'] = 'correcting'
            latest['human_review']['status'] = 'pending'
        phase_current.write_report(phase, contract, latest)
        store.atomic_write_json(phase / 'status.json', latest)
    return record


def _readiness_errors(phase, contract, status):
    errors = []
    try:
        original = phase_current._load_manifest(phase, 'original')
        clone = phase_current._load_manifest(phase, 'clone')
        phase_current._verify_manifest(phase, 'original', original)
        phase_current._verify_manifest(phase, 'clone', clone)
        if store.sha256_file(phase / 'original/manifest.json') != status.get('original_manifest_sha256'):
            errors.append('original manifest hash differs from status')
        if store.sha256_file(phase / 'clone/manifest.json') != status.get('active_clone_manifest_sha256'):
            errors.append('clone manifest hash differs from status')
    except store.PhaseError as error:
        return [str(error)]
    if contract['scope']['unknowns'] or not contract['checkpoints']:
        errors.append('phase scope or checkpoints are incomplete')
    for manifest in (original, clone):
        if manifest.get('phase_contract_sha256') != store.sha256_json(contract):
            errors.append('manifest contract changed')
    for checkpoint in contract['checkpoints']:
        identifier = checkpoint['id']
        current = status['checkpoints'].get(identifier, {})
        if current.get('invalidated'):
            errors.append(f'{identifier} is invalidated')
            continue
        try:
            result = _check_result(phase, checkpoint, current)
        except store.PhaseError as error:
            errors.append(str(error))
            continue
        for role, manifest, key in (
                ('original', original, 'original_png_sha256'),
                ('clone', clone, 'clone_png_sha256')):
            record = phase_current._artifact(manifest, identifier, 'png')
            if record is None or record['sha256'] != current.get(key):
                errors.append(f'{identifier} {role} PNG differs from comparison')
        if result.get('original_png_sha256') != current.get('original_png_sha256'):
            errors.append(f'{identifier} result original hash differs')
        if result.get('clone_png_sha256') != current.get('clone_png_sha256'):
            errors.append(f'{identifier} result clone hash differs')
        captured_build = (phase_current._artifact(clone, identifier, 'png') or {}).get('build_sha256')
        if not captured_build or (current.get('build_sha256') != captured_build
                or result.get('clone_build_sha256') != captured_build):
            errors.append(f'{identifier} evidence build identity differs')
        for dimension in checkpoint['required_dimensions']:
            verdict = current.get('dimensions', {}).get(dimension, {})
            if verdict.get('status') not in ('pass', 'accepted_difference'):
                errors.append(f'{identifier} {dimension} verdict is pending')
            elif any(item not in result.get('evidence_catalog', {})
                     for item in verdict.get('evidence', [])):
                errors.append(f'{identifier} {dimension} evidence reference is stale')
    return errors


def ready_phase(project, phase_id):
    import phase_preflight
    phase_current.recover_pending(project, phase_id)
    phase_preflight.require_active_preflight(project, phase_id)
    phase, contract, status = phase_capture.load_phase(project, phase_id)
    errors = _readiness_errors(phase, contract, status)
    if errors:
        report = phase_current.write_report(phase, contract, status)
        report['readiness'] = {'status': 'blocked', 'errors': errors}
        store.atomic_write_json(phase / 'diff/report.json', report)
        raise ReadinessError(errors)
    with store.phase_lock(phase):
        _, same_contract, latest = phase_capture.load_phase(project, phase_id)
        if same_contract != contract or latest != status:
            raise store.PhaseError('phase changed during readiness')
        latest['state'] = 'automated_ready'
        report = phase_current.write_report(phase, contract, latest)
        report['readiness'] = {'status': 'ready', 'errors': []}
        store.atomic_write_json(phase / 'diff/report.json', report)
        store.atomic_write_json(phase / 'status.json', latest)
    return latest


def record_review(project, phase_id, decision, note, checkpoint_ids=None):
    phase, contract, status = phase_capture.load_phase(project, phase_id)
    if not isinstance(note, str) or not note.strip():
        raise store.PhaseError('review note must be nonempty')
    if decision == 'accept':
        if status['state'] != 'automated_ready':
            raise store.PhaseError('acceptance requires automated readiness')
        errors = _readiness_errors(phase, contract, status)
        if errors:
            raise ReadinessError(errors)
    elif decision == 'request_changes':
        if status['state'] not in ('automated_ready', 'human_accepted'):
            raise store.PhaseError('change request requires completed review')
        checkpoint_ids = checkpoint_ids or []
        for identifier in checkpoint_ids:
            phase_current._checkpoint(contract, identifier)
    else:
        raise store.PhaseError('review decision is invalid')
    with store.phase_lock(phase):
        _, same_contract, latest = phase_capture.load_phase(project, phase_id)
        if same_contract != contract or latest != status:
            raise store.PhaseError('phase changed during review')
        latest['human_review']['history'].append({
            'decision': decision, 'note': note.strip(), 'timestamp': _now(),
            'checkpoints': checkpoint_ids or [],
        })
        if decision == 'accept':
            latest['human_review']['status'] = 'accepted'
            latest['state'] = 'human_accepted'
        else:
            latest['human_review']['status'] = 'changes_requested'
            latest['state'] = 'correcting'
            for identifier in checkpoint_ids:
                current = latest['checkpoints'].get(identifier)
                if current:
                    phase_current._reset_checkpoint(current)
        phase_current.write_report(phase, contract, latest)
        store.atomic_write_json(phase / 'status.json', latest)
    return latest
