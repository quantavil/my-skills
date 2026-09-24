#!/usr/bin/env python3
"""Batch comparison and semantic verdict records for Ditto phases."""
from datetime import datetime, timezone
import fnmatch
import os
from pathlib import Path
import shutil
import tempfile

import diff_screenshots
import phase_capture
import phase_store as store
import pngtool
from PIL import Image

VERDICT_STATUSES = frozenset(
    ('pending', 'pass', 'fail', 'accepted_difference', 'proposed_difference'))
EVIDENCE_KINDS = {
    'visual': frozenset(('visual_result', 'triptych', 'png')),
    'layout': frozenset(('layout_result', 'xml', 'triptych', 'png')),
    'behavior': frozenset(('trace',)),
    'navigation': frozenset(('trace',)),
    'persistence': frozenset(('state', 'trace')),
    'platform': frozenset(('state', 'trace')),
    'network': frozenset(('network',)),
    'accessibility': frozenset(('semantics',)),
}
FULL_PHASE_COMPONENTS = frozenset(('native_build', 'global_assets', 'dependency_upgrade'))
STATE_TRANSITIONS = {
    'comparing': frozenset(('correcting', 'automated_ready')),
    'correcting': frozenset(('comparing', 'automated_ready')),
    'automated_ready': frozenset(('correcting', 'human_accepted')),
}


class ReadinessError(store.PhaseError):
    """The phase is valid but has not met the automated completion gate."""

    def __init__(self, errors):
        self.errors = list(errors)
        super().__init__('automated readiness failed: ' + '; '.join(self.errors))


def _transition(status, target):
    current = status.get('state')
    if target not in STATE_TRANSITIONS.get(current, frozenset()):
        raise store.PhaseError(f'invalid phase transition: {current} -> {target}')
    status['state'] = target


def _artifact(manifest, checkpoint_id, kind):
    matches = [item for item in manifest.get('artifacts', [])
               if item.get('checkpoint_id') == checkpoint_id and item.get('kind') == kind]
    if len(matches) > 1:
        raise store.PhaseError(f'duplicate {kind} artifact for {checkpoint_id}')
    return matches[0] if matches else None


def _catalog_record(role, role_dir, record):
    path = store.safe_child(role_dir, record['path'])
    if not path.is_file() or store.sha256_file(path) != record.get('sha256'):
        raise store.PhaseError(f'{role} evidence is missing or changed: {record["path"]}')
    identifier = f'{role}:{record["path"]}'
    return identifier, {
        'kind': record['kind'], 'path': record['path'],
        'sha256': record['sha256'], 'role': role,
    }


def _overview(path, triptychs):
    if not triptychs:
        raise store.PhaseError('cannot create an empty phase overview')
    thumbnails = []
    for item in triptychs:
        image = pngtool.open_rgb(item)
        image.thumbnail((480, image.height), Image.Resampling.LANCZOS)
        thumbnails.append(image)
    gap = 12
    width = max(image.width for image in thumbnails) + gap * 2
    height = sum(image.height for image in thumbnails) + gap * (len(thumbnails) + 1)
    canvas = Image.new('RGB', (width, height), diff_screenshots.CANVAS_INK)
    y = gap
    for image in thumbnails:
        canvas.paste(image, ((width - image.width) // 2, y))
        y += image.height + gap
    canvas.save(path, format='PNG')


def _active_result(phase, checkpoint_status):
    name = checkpoint_status.get('active_result')
    if not isinstance(name, str):
        raise store.PhaseError('checkpoint has no active comparison result')
    return store.load_json(store.safe_child(phase / 'diff', name))


def _pending_dimension(previous):
    prior = previous if isinstance(previous, dict) else {}
    history = list(prior.get('history', []))
    if prior.get('status') not in (None, 'pending'):
        history.append({key: value for key, value in prior.items()
                        if key != 'history'})
    return {'status': 'pending', 'rationale': None, 'evidence': [],
            'authorization': None, 'history': history}


def _build_report(phase, contract, status):
    checkpoints = []
    for checkpoint in contract['checkpoints']:
        current = status['checkpoints'].get(checkpoint['id'])
        if not isinstance(current, dict) or not current.get('active_result'):
            checkpoints.append({'checkpoint_id': checkpoint['id'], 'comparison': 'missing'})
            continue
        result = _active_result(phase, current)
        checkpoints.append({
            'checkpoint_id': checkpoint['id'],
            'result': current['active_result'],
            'triptych': result['triptych'],
            'changed_ratio': result['changed_ratio'],
            'visual_metric_status': result['visual_metric_status'],
            'layout_comparison_status': result['layout_comparison_status'],
            'dimensions': current['dimensions'],
            'invalidated': current.get('invalidated', False),
            'evidence_build_sha256': current['build_sha256'],
        })
    return {
        'schema_version': 1, 'phase_id': contract['phase_id'],
        'phase_revision': contract['revision'],
        'original_manifest_revision': status['original_manifest_revision'],
        'clone_manifest_revision': status['active_clone_manifest_revision'],
        'checkpoint_count': len(contract['checkpoints']),
        'checkpoints': checkpoints,
        'overview': 'phase_overview.png',
        'overview_limitation': (
            'Full-resolution triptychs govern acceptance; phase_overview.png is an index.'),
        'human_review': status['human_review'],
        'generated_at': datetime.now(timezone.utc).isoformat(),
    }


def _write_report(phase, contract, status):
    report = _build_report(phase, contract, status)
    store.atomic_write_json(phase / 'diff/report.json', report)
    return report


def compare_phase(project, phase_id):
    phase, contract, status = phase_capture.load_phase(project, phase_id)
    if status['state'] not in ('comparing', 'correcting'):
        raise store.PhaseError('phase comparison requires an active clone pack')
    original_revision = status.get('original_manifest_revision')
    clone_revision = status.get('active_clone_manifest_revision')
    if original_revision is None or clone_revision is None:
        raise store.PhaseError('phase comparison requires original and clone manifests')
    original = store.load_json(store.versioned_path(
        phase / 'original', 'manifest', original_revision, 'json'))
    clone = store.load_json(store.versioned_path(
        phase / 'clone', 'manifest', clone_revision, 'json'))
    original_manifest_sha = store.sha256_file(store.versioned_path(
        phase / 'original', 'manifest', original_revision, 'json'))
    clone_manifest_sha = store.sha256_file(store.versioned_path(
        phase / 'clone', 'manifest', clone_revision, 'json'))
    if (original_manifest_sha != status.get('original_manifest_sha256')
            or clone_manifest_sha != status.get('active_clone_manifest_sha256')):
        raise store.PhaseError('active manifest hash differs from status')
    phase_capture._verify_manifest_files(phase / 'original', original)
    phase_capture._verify_manifest_files(phase / 'clone', clone)

    stage = Path(tempfile.mkdtemp(prefix='.comparison.', dir=phase))
    prepared = []
    try:
        for checkpoint in contract['checkpoints']:
            identifier = checkpoint['id']
            if _artifact(clone, identifier, 'png') is None:
                current = status['checkpoints'].get(identifier, {})
                if (not current.get('active_result') or current.get('invalidated')):
                    raise store.PhaseError(
                        f'active clone pack lacks affected checkpoint {identifier}')
                continue
            current = status['checkpoints'].get(identifier, {})
            if current.get('invalidated'):
                if clone_revision <= current.get('clone_manifest_revision', 0):
                    raise store.PhaseError(
                        f'{identifier} needs a new clone capture after invalidation')
                captured_at = datetime.fromisoformat(
                    clone['captured_at'].replace('Z', '+00:00')).astimezone(timezone.utc)
                invalidated_at = datetime.fromisoformat(
                    current['invalidated_at'].replace('Z', '+00:00')).astimezone(timezone.utc)
                if captured_at <= invalidated_at:
                    raise store.PhaseError(
                        f'{identifier} needs a new clone capture after invalidation')
            original_png = _artifact(original, identifier, 'png')
            clone_png = _artifact(clone, identifier, 'png')
            if original_png is None or clone_png is None:
                raise store.PhaseError(f'missing PNG pair for {identifier}')
            original_xml = _artifact(original, identifier, 'xml')
            clone_xml = _artifact(clone, identifier, 'xml')
            if bool(original_xml) != bool(clone_xml):
                original_xml = clone_xml = None
            revision = len(list((phase / 'diff').glob(
                f"{checkpoint['number']:03d}_{identifier}.r*.result.json"))) + 1
            stem = store.checkpoint_stem(checkpoint, revision)
            work = stage / stem
            passed, metric = diff_screenshots.diff_screenshots(
                phase / 'original' / original_png['path'],
                phase / 'clone' / clone_png['path'], work,
                xml_original=(phase / 'original' / original_xml['path'])
                if original_xml else None,
                xml_candidate=(phase / 'clone' / clone_xml['path'])
                if clone_xml else None,
                case_id=identifier)
            triptych_name = f'{stem}.triptych.png'
            result_name = f'{stem}.result.json'
            diff_name = f'{stem}.diff.png'
            shutil.copyfile(work / 'triptych.png', stage / triptych_name)
            shutil.copyfile(work / 'diff.png', stage / diff_name)
            catalog = {}
            for role, role_dir, manifest in (
                    ('original', phase / 'original', original),
                    ('clone', phase / 'clone', clone)):
                for artifact in manifest['artifacts']:
                    if artifact['checkpoint_id'] == identifier:
                        key, value = _catalog_record(role, role_dir, artifact)
                        catalog[key] = value
            catalog[f'diff:{triptych_name}'] = {
                'kind': 'triptych', 'path': triptych_name,
                'sha256': store.sha256_file(stage / triptych_name), 'role': 'diff'}
            catalog[f'diff:{result_name}'] = {
                'kind': 'visual_result', 'path': result_name,
                'sha256': None, 'role': 'diff'}
            if metric['layout_comparison_status'] == 'compared':
                catalog[f'diff:{result_name}:layout'] = {
                    'kind': 'layout_result', 'path': result_name,
                    'sha256': None, 'role': 'diff'}
            result = {
                **metric, 'schema_version': 1, 'checkpoint_id': identifier,
                'revision': revision, 'triptych': triptych_name,
                'triptych_image': triptych_name, 'diff_image': diff_name,
                'original_manifest_revision': original_revision,
                'clone_manifest_revision': clone_revision,
                'original_package_sha256': original['package']['sha256'],
                'clone_package_sha256': clone['package']['sha256'],
                'metric_passed': passed, 'invalidation_state': 'current',
                'dimension_verdicts_at_comparison': {
                    dimension: {'status': 'pending'}
                    for dimension in checkpoint['required_dimensions']},
                'semantic_history_at_comparison': [], 'evidence_catalog': catalog,
            }
            # Self-referential result evidence is identified by immutable filename; its
            # digest is intentionally omitted from the file's own catalog.
            store.write_immutable_json(stage / result_name, result)
            prepared.append((checkpoint, revision, result_name, triptych_name,
                             clone['package']['sha256'],
                             store.sha256_file(stage / result_name),
                             store.sha256_file(stage / triptych_name)))
        if not prepared:
            raise store.PhaseError('active clone pack has no checkpoints to compare')
        new_triptychs = {item[0]['id']: stage / item[3] for item in prepared}
        overview_triptychs = []
        for checkpoint in contract['checkpoints']:
            identifier = checkpoint['id']
            if identifier in new_triptychs:
                overview_triptychs.append(new_triptychs[identifier])
            else:
                prior = status['checkpoints'][identifier]
                result = _active_result(phase, prior)
                overview_triptychs.append(phase / 'diff' / result['triptych'])
        _overview(stage / 'phase_overview.png', overview_triptychs)

        with store.phase_lock(phase):
            _, current_contract, current_status = phase_capture.load_phase(project, phase_id)
            if current_contract != contract or current_status != status:
                raise store.PhaseError('phase changed during comparison')
            for source in sorted(stage.iterdir()):
                if source.is_dir():
                    continue
                if source.name == 'phase_overview.png':
                    continue
                target = phase / 'diff' / source.name
                if target.exists():
                    raise store.PhaseError(f'immutable comparison already exists: {target}')
                os.replace(source, target)
            os.replace(stage / 'phase_overview.png', phase / 'diff/phase_overview.png')
            for (checkpoint, revision, result_name, _, build_sha,
                 result_sha, triptych_sha) in prepared:
                previous = current_status['checkpoints'].get(checkpoint['id'], {})
                current_status['checkpoints'][checkpoint['id']] = {
                    'active_result': result_name, 'result_revision': revision,
                    'original_manifest_revision': original_revision,
                    'original_manifest_sha256': original_manifest_sha,
                    'clone_manifest_revision': clone_revision,
                    'clone_manifest_sha256': clone_manifest_sha,
                    'build_sha256': build_sha, 'result_sha256': result_sha,
                    'triptych_sha256': triptych_sha, 'invalidated': False,
                    'dimensions': {
                        dimension: _pending_dimension(
                            previous.get('dimensions', {}).get(dimension))
                        for dimension in checkpoint['required_dimensions']},
                }
            current_status['state'] = 'comparing'
            report = _write_report(phase, contract, current_status)
            store.atomic_write_json(phase / 'status.json', current_status)
            return report
    finally:
        shutil.rmtree(stage, ignore_errors=True)


def _authorized_ids(contract):
    values = set()
    for item in contract.get('authorized_differences', []):
        if isinstance(item, str):
            values.add(item)
        elif isinstance(item, dict) and isinstance(item.get('id'), str):
            values.add(item['id'])
    return values


def record_verdict(project, phase_id, checkpoint_id, dimension, status,
                   rationale, evidence, authorization=None):
    phase, contract, phase_status = phase_capture.load_phase(project, phase_id)
    checkpoint = next((item for item in contract['checkpoints']
                       if item['id'] == checkpoint_id), None)
    if checkpoint is None:
        raise store.PhaseError(f'unknown checkpoint: {checkpoint_id}')
    if dimension not in checkpoint['required_dimensions']:
        raise store.PhaseError(f'{dimension} is not required for {checkpoint_id}')
    if status not in VERDICT_STATUSES - {'pending'}:
        raise store.PhaseError('verdict status is invalid')
    if not isinstance(rationale, str) or not rationale.strip():
        raise store.PhaseError('verdict rationale must be nonempty')
    if not isinstance(evidence, list) or not evidence or any(
            not isinstance(item, str) or not item for item in evidence):
        raise store.PhaseError('verdict evidence must contain evidence IDs')
    current = phase_status['checkpoints'].get(checkpoint_id)
    if not isinstance(current, dict) or current.get('invalidated'):
        raise store.PhaseError('checkpoint has no current comparison')
    result = _active_result(phase, current)
    catalog = result.get('evidence_catalog', {})
    missing = sorted(set(evidence) - set(catalog))
    if missing:
        raise store.PhaseError('unknown evidence IDs: ' + ', '.join(missing))
    unsuitable = sorted(identifier for identifier in evidence
                        if catalog[identifier].get('kind') not in EVIDENCE_KINDS[dimension])
    if unsuitable:
        raise store.PhaseError(f'evidence kind cannot support {dimension}: '
                               + ', '.join(unsuitable))
    if status == 'accepted_difference':
        if not authorization or authorization not in _authorized_ids(contract):
            raise store.PhaseError('accepted difference requires valid authorization')
    elif status == 'proposed_difference':
        if not isinstance(authorization, str) or not authorization.strip():
            raise store.PhaseError('proposed difference requires proposal metadata')
    elif authorization is not None:
        raise store.PhaseError('authorization is only valid for a difference verdict')

    verdict = {
        'status': status, 'rationale': rationale.strip(), 'evidence': list(evidence),
        'authorization': authorization, 'recorded_at': datetime.now(timezone.utc).isoformat(),
        'changed_ratio': result.get('changed_ratio') if dimension == 'visual' else None,
    }
    with store.phase_lock(phase):
        _, locked_contract, locked_status = phase_capture.load_phase(project, phase_id)
        locked_current = locked_status['checkpoints'].get(checkpoint_id)
        if locked_contract != contract or locked_current.get('active_result') != current['active_result']:
            raise store.PhaseError('checkpoint changed while recording verdict')
        dimension_record = locked_current['dimensions'][dimension]
        history = list(dimension_record.get('history', []))
        if dimension_record.get('status') != 'pending':
            history.append({key: value for key, value in dimension_record.items()
                            if key != 'history'})
        locked_current['dimensions'][dimension] = {**verdict, 'history': history}
        required = locked_current['dimensions'].values()
        locked_current['closed'] = all(
            item['status'] in ('pass', 'accepted_difference', 'proposed_difference')
            for item in required)
        if status == 'fail':
            locked_status['state'] = 'correcting'
        _write_report(phase, contract, locked_status)
        store.atomic_write_json(phase / 'status.json', locked_status)
        return verdict


def _graph_is_malformed(graph):
    components = set(graph.get('components', []))
    edges = graph.get('component_edges', {})
    if set(edges) - components:
        return True
    if any(not isinstance(targets, list) or set(targets) - components
           for targets in edges.values()):
        return True
    visiting, visited = set(), set()

    def visit(component):
        if component in visiting:
            return True
        if component in visited:
            return False
        visiting.add(component)
        if any(visit(target) for target in edges.get(component, [])):
            return True
        visiting.remove(component)
        visited.add(component)
        return False

    return any(visit(component) for component in components)


def affected_checkpoints(contract, changed_paths):
    checkpoints = contract.get('checkpoints', [])
    all_checkpoints = {item['id'] for item in checkpoints}
    if (not isinstance(changed_paths, list) or not changed_paths
            or any(not isinstance(path, str) or not path for path in changed_paths)):
        raise store.PhaseError('changed paths must be a nonempty list')
    graph = contract.get('dependency_graph', {})
    if _graph_is_malformed(graph):
        return all_checkpoints, sorted(set(graph.get('components', [])))
    rules = graph.get('path_rules', [])
    roots = set()
    for path in changed_paths:
        matched = [rule for rule in rules if fnmatch.fnmatchcase(path, rule['glob'])]
        if not matched:
            return all_checkpoints, sorted(roots)
        for rule in matched:
            roots.update(rule['components'])
    resolved, pending = set(), list(roots)
    edges = graph.get('component_edges', {})
    while pending:
        component = pending.pop()
        if component in resolved:
            continue
        resolved.add(component)
        pending.extend(edges.get(component, []))
    if resolved & FULL_PHASE_COMPONENTS:
        return all_checkpoints, sorted(resolved)
    affected = {item['id'] for item in checkpoints
                if set(item.get('dependencies', [])) & resolved}
    return affected, sorted(resolved)


def invalidate(project, phase_id, changed_paths):
    phase, contract, status = phase_capture.load_phase(project, phase_id)
    affected, components = affected_checkpoints(contract, changed_paths)
    all_ids = {item['id'] for item in contract['checkpoints']}
    full = affected == all_ids
    superseded = {}
    with store.phase_lock(phase):
        _, locked_contract, locked_status = phase_capture.load_phase(project, phase_id)
        if locked_contract != contract:
            raise store.PhaseError('phase contract changed during invalidation')
        for checkpoint_id in sorted(affected):
            current = locked_status['checkpoints'].get(checkpoint_id)
            if not isinstance(current, dict):
                continue
            if isinstance(current.get('result_revision'), int):
                superseded[checkpoint_id] = current['result_revision']
            current['invalidated'] = True
            current['invalidated_at'] = datetime.now(timezone.utc).isoformat()
            current['closed'] = False
            for dimension in current.get('dimensions', {}).values():
                prior = {key: value for key, value in dimension.items() if key != 'history'}
                history = list(dimension.get('history', []))
                if dimension.get('status') != 'pending':
                    history.append(prior)
                dimension.update({
                    'status': 'pending', 'rationale': None, 'evidence': [],
                    'authorization': None, 'history': history,
                })
        record = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'changed_paths': list(changed_paths),
            'resolved_components': components,
            'reopened_checkpoints': sorted(affected),
            'superseded_results': superseded,
            'reason': ('conservative full-phase invalidation'
                       if full else 'contract dependency impact'),
        }
        locked_status['invalidation_history'].append(record)
        if affected:
            locked_status['state'] = 'correcting'
        if (phase / 'diff/report.json').exists():
            _write_report(phase, contract, locked_status)
        store.atomic_write_json(phase / 'status.json', locked_status)
        return record


def _write_readiness_report(phase, contract, status, readiness, errors):
    report = _build_report(phase, contract, status)
    report['readiness'] = {
        'status': readiness, 'errors': list(errors),
        'checked_at': datetime.now(timezone.utc).isoformat(),
    }
    proposed = []
    for checkpoint_id, current in status['checkpoints'].items():
        for dimension, verdict in current.get('dimensions', {}).items():
            if verdict.get('status') == 'proposed_difference':
                proposed.append({
                    'checkpoint_id': checkpoint_id, 'dimension': dimension,
                    'rationale': verdict.get('rationale'),
                    'proposal_metadata': verdict.get('authorization'),
                    'evidence': verdict.get('evidence', []),
                })
    report['decision_packet'] = {
        'proposed_differences': proposed,
        'proposed_exclusions': contract.get('scope', {}).get('proposed_exclusions', []),
    }
    store.atomic_write_json(phase / 'diff/report.json', report)
    return report


def _check_file_record(directory, record, label, errors):
    if not isinstance(record, dict) or not isinstance(record.get('path'), str):
        errors.append(f'{label} has an invalid file record')
        return
    try:
        path = store.safe_child(directory, record['path'])
        if not path.is_file() or path.is_symlink():
            errors.append(f'{label} file is missing: {record["path"]}')
        elif record.get('sha256') and store.sha256_file(path) != record['sha256']:
            errors.append(f'{label} file hash is invalid: {record["path"]}')
    except store.PhaseError as error:
        errors.append(str(error))


def _check_manifest_provenance(manifest, preflight, contract, role, errors):
    controller = manifest.get('controller', {})
    expected = preflight['mcps']['mobile-control']
    if controller.get('provenance') != 'mcp':
        errors.append(f'{role} controller evidence lacks MCP provenance')
    for field in ('server', 'tool', 'target'):
        if controller.get(field) != expected.get(field):
            errors.append(f'{role} controller {field} differs from active preflight')
    build_sha = manifest.get('package', {}).get('sha256')
    if controller.get('installed_package_sha256') != build_sha:
        errors.append(f'{role} controller installed package is unbound')
    checkpoints = {item['id']: item for item in contract['checkpoints']}
    for artifact in manifest.get('artifacts', []):
        checkpoint = checkpoints.get(artifact.get('checkpoint_id'))
        evidence = artifact.get('controller', {})
        if (checkpoint is None or artifact.get('build_sha256') != build_sha
                or artifact.get('kind') not in checkpoint['artifacts']):
            errors.append(f'{role} artifact lacks checkpoint or build binding')
            continue
        required = {
            'server': expected['server'], 'tool': expected['tool'],
            'target': expected['target'],
            'provenance': 'mcp', 'action_result': 'success',
            'installed_package_sha256': build_sha,
            'fixture': checkpoint['fixture'],
        }
        binding = artifact.get('binding')
        if binding is None:
            required.update({
                'setup_sha256': store.sha256_json(checkpoint['setup']),
                'actions_sha256': store.sha256_json(checkpoint['actions']),
            })
        else:
            trace = next((item for item in manifest['artifacts']
                          if item.get('checkpoint_id') == checkpoint['id']
                          and item.get('kind') == 'trace'), None)
            if (not (role == 'original' or role.endswith(' original'))
                    or not manifest.get('rebound_from')
                    or not manifest.get('rebind_reason')
                    or not binding.get('reason')
                    or binding.get('source_setup_sha256') != evidence.get('setup_sha256')
                    or binding.get('source_actions_sha256') != evidence.get('actions_sha256')
                    or binding.get('setup_sha256') != store.sha256_json(checkpoint['setup'])
                    or binding.get('actions_sha256') != store.sha256_json(checkpoint['actions'])
                    or binding.get('incidental_actions') != checkpoint.get('incidental_actions', [])
                    or (binding.get('source_trace_sha256') is not None
                        and (trace is None or binding['source_trace_sha256'] != trace['sha256']))):
                errors.append(f'{role} artifact has invalid contract rebind')
        # Each retained artifact keeps its historical session, including partial recaptures.
        if (not evidence.get('session_id') or
                any(evidence.get(field) != value for field, value in required.items())):
            errors.append(f'{role} artifact has invalid MCP or protocol provenance')


def _readiness_errors(project, phase, contract, status):
    errors = []
    try:
        import phase_preflight
        preflight = phase_preflight.require_active_preflight(project, contract['phase_id'])
    except store.PhaseError as error:
        errors.append(str(error))
        preflight = None

    original_revision = status.get('original_manifest_revision')
    active_clone_revision = status.get('active_clone_manifest_revision')
    manifests = {}
    for role, revision in (('original', original_revision), ('clone', active_clone_revision)):
        if revision is None:
            errors.append(f'active {role} manifest is missing')
            continue
        try:
            manifest_path = store.versioned_path(
                phase / role, 'manifest', revision, 'json')
            manifest = store.load_json(manifest_path)
            phase_capture._verify_manifest_files(phase / role, manifest)
            expected_hash = status.get('original_manifest_sha256' if role == 'original'
                                       else 'active_clone_manifest_sha256')
            if store.sha256_file(manifest_path) != expected_hash:
                errors.append(f'active {role} manifest hash is invalid')
            manifests[role] = manifest
        except store.PhaseError as error:
            errors.append(str(error))
    if preflight:
        for role, manifest in manifests.items():
            _check_manifest_provenance(manifest, preflight, contract, role, errors)

    report_path = phase / 'diff/report.json'
    try:
        report = store.load_json(report_path)
        if (report.get('phase_revision') != contract['revision']
                or report.get('original_manifest_revision') != original_revision
                or report.get('clone_manifest_revision') != active_clone_revision):
            errors.append('active report has stale phase or manifest pointers')
        report_entries = {item.get('checkpoint_id'): item
                          for item in report.get('checkpoints', []) if isinstance(item, dict)}
    except store.PhaseError as error:
        errors.append(str(error))
        report_entries = {}
    if not (phase / 'diff/phase_overview.png').is_file():
        errors.append('phase overview is missing')

    authorized = _authorized_ids(contract)
    for checkpoint in contract['checkpoints']:
        identifier = checkpoint['id']
        current = status['checkpoints'].get(identifier)
        if not isinstance(current, dict):
            errors.append(f'{identifier} has no active comparison')
            continue
        result_name = current.get('active_result')
        if report_entries.get(identifier, {}).get('result') != result_name:
            errors.append(f'{identifier} report entry is stale')
        elif (report_entries[identifier].get('dimensions') != current.get('dimensions')
              or report_entries[identifier].get('invalidated') !=
              current.get('invalidated', False)
              or report_entries[identifier].get('evidence_build_sha256') !=
              current.get('build_sha256')):
            errors.append(f'{identifier} report verdict or build data is stale')
        try:
            result = _active_result(phase, current)
        except store.PhaseError as error:
            errors.append(str(error))
            continue
        result_path = phase / 'diff' / result_name
        if store.sha256_file(result_path) != current.get('result_sha256'):
            errors.append(f'{identifier} result hash is invalid')
        if (result.get('original_manifest_revision') != current.get(
                'original_manifest_revision')
                or result.get('clone_manifest_revision') != current.get(
                'clone_manifest_revision')):
            errors.append(f'{identifier} result manifest pointers are stale')
        if current.get('invalidated'):
            errors.append(f'{identifier} is invalidated')
        triptych = result.get('evidence_catalog', {}).get(
            f"diff:{result.get('triptych')}")
        _check_file_record(phase / 'diff', triptych, f'{identifier} triptych', errors)
        if (isinstance(triptych, dict)
                and triptych.get('sha256') != current.get('triptych_sha256')):
            errors.append(f'{identifier} triptych status hash is stale')
        clone_revision = current.get('clone_manifest_revision')
        try:
            evidence_path = store.versioned_path(
                phase / 'clone', 'manifest', clone_revision, 'json')
            evidence_manifest = store.load_json(evidence_path)
            phase_capture._verify_manifest_files(phase / 'clone', evidence_manifest)
            if store.sha256_file(evidence_path) != current.get('clone_manifest_sha256'):
                errors.append(f'{identifier} clone manifest hash is invalid')
            if preflight:
                _check_manifest_provenance(
                    evidence_manifest, preflight, contract,
                    f'{identifier} clone', errors)
            if current.get('build_sha256') != evidence_manifest['package']['sha256']:
                errors.append(f'{identifier} build identity is not traceable')
            original_evidence_path = store.versioned_path(
                phase / 'original', 'manifest',
                current.get('original_manifest_revision'), 'json')
            original_manifest = store.load_json(original_evidence_path)
            phase_capture._verify_manifest_files(phase / 'original', original_manifest)
            if store.sha256_file(original_evidence_path) != current.get(
                    'original_manifest_sha256'):
                errors.append(f'{identifier} original manifest hash is invalid')
            if preflight:
                _check_manifest_provenance(
                    original_manifest, preflight, contract,
                    f'{identifier} original', errors)
            for kind in checkpoint['artifacts']:
                if (_artifact(original_manifest, identifier, kind) is None
                        or _artifact(evidence_manifest, identifier, kind) is None):
                    errors.append(f'{identifier} missing required {kind} artifact pair')
        except (store.PhaseError, TypeError) as error:
            errors.append(f'{identifier} evidence build is unavailable: {error}')

        dimensions = current.get('dimensions', {})
        for dimension in checkpoint['required_dimensions']:
            verdict = dimensions.get(dimension, {})
            verdict_status = verdict.get('status')
            if verdict_status not in ('pass', 'accepted_difference', 'proposed_difference'):
                errors.append(f'{identifier}.{dimension} is {verdict_status or "missing"}')
                continue
            if not isinstance(verdict.get('rationale'), str) or not verdict['rationale'].strip():
                errors.append(f'{identifier}.{dimension} has no rationale')
            references = verdict.get('evidence')
            if not isinstance(references, list) or not references:
                errors.append(f'{identifier}.{dimension} has no evidence')
                continue
            catalog = result.get('evidence_catalog', {})
            for reference in references:
                entry = catalog.get(reference)
                if not isinstance(entry, dict):
                    errors.append(f'{identifier}.{dimension} has missing evidence ID {reference}')
                    continue
                if entry.get('kind') not in EVIDENCE_KINDS[dimension]:
                    errors.append(f'{identifier}.{dimension} has unsupported evidence kind')
                role = entry.get('role')
                directory = phase / role if role in ('original', 'clone', 'diff') else phase
                _check_file_record(directory, entry,
                                   f'{identifier}.{dimension} evidence', errors)
            if (verdict_status == 'accepted_difference'
                    and verdict.get('authorization') not in authorized):
                errors.append(f'{identifier}.{dimension} lacks valid authorization')
            if (verdict_status == 'proposed_difference'
                    and not verdict.get('authorization')):
                errors.append(f'{identifier}.{dimension} lacks proposal metadata')
    exclusions = contract.get('scope', {}).get('proposed_exclusions', [])
    if not isinstance(exclusions, list) or any(
            not isinstance(item, dict) or not item.get('rationale') or not item.get('evidence')
            for item in exclusions):
        errors.append('proposed exclusion is outside the final decision packet')
    return errors


def ready_phase(project, phase_id):
    phase, contract, status = phase_capture.load_phase(project, phase_id)
    errors = _readiness_errors(project, phase, contract, status)
    # Active preflight validation can block status; reload its authoritative result.
    _, contract, status = phase_capture.load_phase(project, phase_id)
    if errors:
        with store.phase_lock(phase):
            _, locked_contract, locked_status = phase_capture.load_phase(
                project, phase_id)
            if locked_contract != contract or locked_status != status:
                raise store.PhaseError('phase changed during readiness check')
            _write_readiness_report(phase, contract, status, 'blocked', errors)
        raise ReadinessError(errors)
    with store.phase_lock(phase):
        _, locked_contract, locked_status = phase_capture.load_phase(project, phase_id)
        if locked_contract != contract or locked_status != status:
            raise store.PhaseError('phase changed during readiness check')
        _transition(locked_status, 'automated_ready')
        locked_status['human_review']['status'] = 'pending'
        _write_readiness_report(phase, contract, locked_status, 'ready', [])
        store.atomic_write_json(phase / 'status.json', locked_status)
        return locked_status


def record_review(project, phase_id, decision, note, checkpoints=()):
    phase, contract, status = phase_capture.load_phase(project, phase_id)
    if status['state'] != 'automated_ready':
        raise store.PhaseError('human review requires automated readiness')
    if not isinstance(note, str) or not note.strip():
        raise store.PhaseError('human review note must be nonempty')
    if decision not in ('accept', 'request_changes'):
        raise store.PhaseError('human review decision is invalid')
    checkpoints = list(checkpoints)
    valid_ids = {item['id'] for item in contract['checkpoints']}
    if decision == 'request_changes':
        if not checkpoints or len(checkpoints) != len(set(checkpoints)):
            raise store.PhaseError('requested changes need unique checkpoints')
        unknown = sorted(set(checkpoints) - valid_ids)
        if unknown:
            raise store.PhaseError('unknown review checkpoints: ' + ', '.join(unknown))
    elif checkpoints:
        raise store.PhaseError('acceptance does not take checkpoint changes')
    entry = {
        'decision': decision, 'note': note.strip(), 'checkpoints': checkpoints,
        'recorded_at': datetime.now(timezone.utc).isoformat(),
    }
    with store.phase_lock(phase):
        _, locked_contract, locked_status = phase_capture.load_phase(project, phase_id)
        if locked_contract != contract or locked_status != status:
            raise store.PhaseError('phase changed during human review')
        locked_status['human_review']['history'].append(entry)
        if decision == 'accept':
            _transition(locked_status, 'human_accepted')
            locked_status['human_review']['status'] = 'accepted'
        else:
            _transition(locked_status, 'correcting')
            locked_status['human_review']['status'] = 'changes_requested'
            for checkpoint_id in checkpoints:
                current = locked_status['checkpoints'][checkpoint_id]
                current['invalidated'] = True
                current['invalidated_at'] = datetime.now(timezone.utc).isoformat()
                current['closed'] = False
                for dimension in current['dimensions'].values():
                    prior = {key: value for key, value in dimension.items()
                             if key != 'history'}
                    history = list(dimension.get('history', []))
                    history.append(prior)
                    dimension.update({
                        'status': 'pending', 'rationale': None, 'evidence': [],
                        'authorization': None, 'history': history,
                    })
        if decision == 'accept':
            _write_readiness_report(phase, contract, locked_status, 'ready', [])
        else:
            _write_report(phase, contract, locked_status)
        store.atomic_write_json(phase / 'status.json', locked_status)
        return locked_status
