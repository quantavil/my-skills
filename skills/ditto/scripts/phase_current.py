#!/usr/bin/env python3
"""The current, replaceable evidence set for human-selected Ditto checkpoints."""
from copy import deepcopy
from datetime import datetime, timezone
import os
from pathlib import Path
import shutil
import tempfile

import diff_screenshots
import phase_capture
import phase_store as store


def _now():
    return datetime.now(timezone.utc).isoformat()


def _checkpoint(contract, identifier):
    for checkpoint in contract['checkpoints']:
        if checkpoint['id'] == identifier:
            return checkpoint
    raise store.PhaseError(f'unknown checkpoint: {identifier}')


def _stem(checkpoint):
    return f"{checkpoint['number']:03d}_{checkpoint['id']}"


def _verified_file(path, digest, label):
    if not isinstance(path, str) or not isinstance(digest, str):
        raise store.PhaseError(f'{label} path and hash are required')
    source = Path(path)
    if not source.is_file() or source.is_symlink():
        raise store.PhaseError(f'{label} is missing or symbolic')
    if store.sha256_file(source) != digest:
        raise store.PhaseError(f'{label} hash differs from selection')
    return source


def _selection(path, phase_id, contract, package, kind):
    data = store.load_json(path)
    if (data.get('schema_version') != 1 or data.get('kind') != kind
            or data.get('phase_id') != phase_id or data.get('provenance') != 'mcp'):
        raise store.PhaseError('selection needs matching phase and MCP provenance')
    package_sha = store.sha256_file(package)
    if data.get('installed_package_sha256') != package_sha:
        raise store.PhaseError('selection installed package hash differs from APK')
    if data.get('target') != contract['runtime_target']:
        raise store.PhaseError('selection target differs from contract')
    receipt = data.get('mcp_receipt')
    if not isinstance(receipt, dict) or receipt.get('provenance') != 'mcp':
        raise store.PhaseError('selection needs an inline MCP receipt')
    for field in ('server', 'tool', 'session_id'):
        if (not isinstance(data.get(field), str) or not data[field]
                or receipt.get(field) != data[field]):
            raise store.PhaseError(f'selection MCP {field} differs from receipt')
    if receipt.get('target') != data['target'] or receipt.get('environment') != data.get('environment'):
        raise store.PhaseError('selection MCP target or environment differs from receipt')
    if (receipt.get('installed_package_sha256') is not None
            and receipt['installed_package_sha256'] != package_sha):
        raise store.PhaseError('selection MCP receipt has a different installed package')
    log = data.get('action_log')
    if not isinstance(log, dict):
        raise store.PhaseError('selection needs a recorded action log')
    _verified_file(log.get('path'), log.get('sha256'), 'action log')
    entries = data.get('selections')
    if not isinstance(entries, list) or not entries:
        raise store.PhaseError('selection needs at least one checkpoint')
    identifiers = []
    for entry in entries:
        if not isinstance(entry, dict):
            raise store.PhaseError('checkpoint selection must be an object')
        identifier = entry.get('checkpoint_id')
        _checkpoint(contract, identifier)
        if identifier in identifiers:
            raise store.PhaseError(f'duplicate selected checkpoint: {identifier}')
        identifiers.append(identifier)
        _verified_file(entry.get('png'), entry.get('png_sha256'), 'selected PNG')
        if entry.get('xml') is not None:
            _verified_file(entry['xml'], entry.get('xml_sha256'), 'selected XML')
        elif entry.get('xml_sha256') is not None:
            raise store.PhaseError('XML hash has no selected XML')
        try:
            timestamp = datetime.fromisoformat(entry['captured_at'].replace('Z', '+00:00'))
            if timestamp.tzinfo is None:
                raise ValueError
        except (KeyError, AttributeError, ValueError):
            raise store.PhaseError('selection needs a timezone-aware capture time') from None
        if not isinstance(entry.get('observed_actions'), list):
            raise store.PhaseError('selection needs recorded observed actions')
    return data


def _manifest_path(phase, role):
    return phase / role / 'manifest.json'


def _load_manifest(phase, role):
    path = _manifest_path(phase, role)
    return store.load_json(path) if path.exists() else None


def _artifact(manifest, checkpoint_id, kind):
    for item in (manifest or {}).get('artifacts', []):
        if item['checkpoint_id'] == checkpoint_id and item['kind'] == kind:
            return item
    return None


def _verify_manifest(phase, role, manifest):
    if not isinstance(manifest, dict):
        raise store.PhaseError(f'current {role} manifest is missing')
    for item in manifest.get('artifacts', []):
        _verified_file(str(store.safe_child(phase / role, item['path'])),
                       item['sha256'], f'{role} artifact')
    package = manifest.get('package', {})
    if package.get('path'):
        _verified_file(str(store.safe_child(phase / role, package['path'])),
                       package.get('sha256'), f'{role} package')
    reverse = manifest.get('reverse_index')
    if reverse:
        index_path = _verified_file(
            str(store.safe_child(phase / role, reverse['path'])),
            reverse['sha256'], 'reverse index')
        index = store.load_json(index_path)
        if index.get('package_sha256') != package.get('sha256'):
            raise store.PhaseError('reverse index belongs to another package')
        for retained in index.get('retained_files', []):
            _verified_file(str(store.safe_child(phase / role, retained['path'])),
                           retained['sha256'], 'reverse evidence')


def _reset_checkpoint(current):
    current['invalidated'] = True
    current['closed'] = False
    current['active_result'] = None
    current['result_sha256'] = None
    current['triptych_sha256'] = None
    for dimension in current.get('dimensions', {}).values():
        dimension.update({'status': 'pending', 'rationale': None,
                          'evidence': [], 'authorization': None})


def _base_manifest(phase_id, role, contract, data, package_sha, prior):
    manifest = deepcopy(prior) if prior else {
        'schema_version': 1, 'phase_id': phase_id, 'role': role,
        'artifacts': [],
    }
    manifest['phase_contract_sha256'] = store.sha256_json(contract)
    manifest['package'] = {'path': 'app.apk', 'sha256': package_sha}
    manifest['controller'] = {key: data[key] for key in (
        'server', 'tool', 'session_id', 'target', 'environment', 'provenance')}
    manifest['capture_sha256'] = store.sha256_json(data)
    manifest['captured_at'] = _now()
    return manifest


def _stage_selection(stage, data, contract, package_sha, manifest):
    selected = {entry['checkpoint_id'] for entry in data['selections']}
    manifest['artifacts'] = [item for item in manifest['artifacts']
                             if item['checkpoint_id'] not in selected]
    for entry in data['selections']:
        checkpoint = _checkpoint(contract, entry['checkpoint_id'])
        trace_name = f'{_stem(checkpoint)}.trace.json'
        store.atomic_write_json(stage / trace_name, {
            'observed_actions': entry['observed_actions'],
            'observed_state': entry.get('observed_state'),
            'notes': entry.get('notes'), 'captured_at': entry['captured_at'],
            'observation_source': entry.get('observation_source', 'selected_candidate'),
        })
        manifest['artifacts'].append({
            'checkpoint_id': checkpoint['id'], 'kind': 'trace', 'path': trace_name,
            'sha256': store.sha256_file(stage / trace_name), 'build_sha256': package_sha,
        })
        for kind in ('png', 'xml'):
            if entry.get(kind) is None:
                continue
            name = f'{_stem(checkpoint)}.{kind}'
            shutil.copyfile(entry[kind], stage / name)
            digest = store.sha256_file(stage / name)
            if digest != entry[f'{kind}_sha256']:
                raise store.PhaseError(f'{kind} changed while copying selection')
            manifest['artifacts'].append({
                'checkpoint_id': checkpoint['id'], 'kind': kind,
                'path': name, 'sha256': digest, 'build_sha256': package_sha,
                'source_sha256': digest, 'captured_at': entry['captured_at'],
                'observed_actions': entry['observed_actions'],
                'after_input': entry.get('after_input'),
                'observed_state': entry.get('observed_state'),
                'notes': entry.get('notes'),
                'environment': data['environment'],
                'action_log': data['action_log'],
                'controller': {key: data[key] for key in (
                    'server', 'tool', 'session_id', 'target', 'provenance')},
            })
    manifest['artifacts'].sort(key=lambda item: (item['checkpoint_id'], item['kind']))


def _publish(stage, target_dir):
    """Replace stable files; callers first publish pending status under the phase lock."""
    for source in stage.iterdir():
        if source.is_file():
            os.replace(source, target_dir / source.name)


def _linked_tree(source, target):
    def link_or_copy(old, new):
        try:
            os.link(old, new)
        except OSError:
            shutil.copyfile(old, new)
    shutil.copytree(source, target, copy_function=link_or_copy)


def recover_pending(project, phase_id):
    """Restore the last complete current set after an interrupted publication."""
    phase = phase_capture.phase_directory(project, phase_id)
    status_path = phase / 'status.json'
    if not status_path.is_file():
        return
    status = store.load_json(status_path)
    txn_name = status.get('transaction')
    if not txn_name:
        return
    txn = store.safe_child(phase, txn_name)
    if not txn.is_dir():
        raise store.PhaseError('pending evidence transaction has no recovery files')
    with store.phase_lock(phase):
        status = store.load_json(status_path)
        if status.get('transaction') != txn_name:
            return
        previous = store.load_json(txn / 'status.json')
        for role in ('original', 'clone', 'diff'):
            backup = txn / f'backup-{role}'
            if backup.is_dir():
                target = phase / role
                if target.exists():
                    shutil.rmtree(target)
                _linked_tree(backup, target)
        store.atomic_write_json(status_path, previous)
    shutil.rmtree(txn, ignore_errors=True)


def _commit_current(phase, prior_status, pending_status, trees):
    """Swap role trees with recovery copies and publish status last."""
    txn = Path(tempfile.mkdtemp(prefix='.current-transaction.', dir=phase))
    try:
        store.atomic_write_json(txn / 'status.json', prior_status)
        for role in trees:
            _linked_tree(phase / role, txn / f'backup-{role}')
        pending_status['transaction'] = txn.name
        store.atomic_write_json(phase / 'status.json', pending_status)
        for role, prepared in trees.items():
            target = phase / role
            old = txn / f'old-{role}'
            os.replace(target, old)
            os.replace(prepared, target)
        pending_status.pop('transaction', None)
        return txn
    except Exception:
        for role in trees:
            backup = txn / f'backup-{role}'
            if backup.is_dir():
                target = phase / role
                if target.exists():
                    shutil.rmtree(target)
                os.replace(backup, target)
        store.atomic_write_json(phase / 'status.json', prior_status)
        shutil.rmtree(txn, ignore_errors=True)
        raise


def select_original(project, phase_id, selection, package, replace_frozen=False,
                    mcp_exports=None):
    recover_pending(project, phase_id)
    phase, contract, status = phase_capture.load_phase(project, phase_id)
    package = Path(package).resolve()
    data = _selection(selection, phase_id, contract, package,
                      'ditto_selected_original')
    if status['state'] != 'collecting_original' and not replace_frozen:
        raise store.PhaseError('frozen original requires --replace-frozen')
    if replace_frozen and status['state'] not in (
            'oracle_frozen', 'implementing', 'comparing', 'correcting',
            'automated_ready', 'human_accepted'):
        raise store.PhaseError('--replace-frozen requires a frozen original')
    import phase_preflight
    preflight = phase_preflight.require_active_preflight(project, phase_id)
    package_sha = store.sha256_file(package)
    if preflight.get('package_sha256') != package_sha:
        raise store.PhaseError('selected original differs from preflight package')
    previous = _load_manifest(phase, 'original')
    if previous:
        _verify_manifest(phase, 'original', previous)
    manifest = _base_manifest(phase_id, 'original', contract, data, package_sha,
                              previous)
    stage = Path(tempfile.mkdtemp(prefix='.selected-original.', dir=phase))
    try:
        _stage_selection(stage, data, contract, package_sha, manifest)
        if previous is None:
            shutil.copyfile(package, stage / 'app.apk')
        elif previous['package']['sha256'] != package_sha:
            raise store.PhaseError('frozen original package differs from preflight')
        if mcp_exports:
            if previous and previous.get('reverse_index'):
                raise store.PhaseError('reverse evidence already exists; reuse current analysis')
            import phase_package
            links = {pattern: [item['id'] for item in contract['checkpoints']]
                     for pattern in contract['reverse_engineering']['include_globs']}
            phase_package.analyze_package(
                package, stage / 'analysis',
                contract['reverse_engineering']['include_globs'], links,
                mcp_exports, preflight)
        reverse = stage / 'analysis/reverse.json'
        if reverse.is_file():
            manifest['reverse_index'] = {'path': 'reverse.json',
                                         'sha256': store.sha256_file(reverse)}
        elif previous and previous.get('reverse_index'):
            manifest['reverse_index'] = previous['reverse_index']
        store.atomic_write_json(stage / 'manifest.json', manifest)
        assembled = stage / 'assembled-original'
        _linked_tree(phase / 'original', assembled)
        _publish(stage, assembled)
        analysis = stage / 'analysis'
        if analysis.is_dir():
            for source in analysis.iterdir():
                target = assembled / source.name
                if target.exists():
                    if target.is_dir():
                        shutil.rmtree(target)
                    else:
                        target.unlink()
                os.replace(source, target)
        for entry in data['selections']:
            if entry.get('xml') is None:
                (assembled / f"{_stem(_checkpoint(contract, entry['checkpoint_id']))}.xml").unlink(missing_ok=True)
        with store.phase_lock(phase):
            _, locked_contract, locked_status = phase_capture.load_phase(project, phase_id)
            if locked_contract != contract or locked_status != status:
                raise store.PhaseError('phase changed during original selection')
            pending = deepcopy(status)
            affected = [entry['checkpoint_id'] for entry in data['selections']]
            for identifier in affected:
                if identifier in pending['checkpoints']:
                    _reset_checkpoint(pending['checkpoints'][identifier])
            pending['human_review']['status'] = 'pending'
            if replace_frozen:
                pending['state'] = 'correcting'
            pending['original_manifest_revision'] = 1
            pending['original_manifest_sha256'] = store.sha256_file(assembled / 'manifest.json')
            assembled_diff = stage / 'diff'
            _linked_tree(phase / 'diff', assembled_diff)
            write_report(stage, contract, pending)
            txn = _commit_current(phase, status, pending,
                                  {'original': assembled, 'diff': assembled_diff})
            store.atomic_write_json(phase / 'status.json', pending)
        shutil.rmtree(txn, ignore_errors=True)
        return manifest
    finally:
        shutil.rmtree(stage, ignore_errors=True)


def freeze_original(project, phase_id):
    recover_pending(project, phase_id)
    phase, contract, status = phase_capture.load_phase(project, phase_id)
    if status['state'] != 'collecting_original':
        raise store.PhaseError('original can only be frozen after collection')
    import phase_preflight
    phase_preflight.require_active_preflight(project, phase_id)
    if contract['scope']['unknowns'] or not contract['checkpoints']:
        raise store.PhaseError('resolve phase scope and define checkpoints before freezing')
    manifest = _load_manifest(phase, 'original')
    _verify_manifest(phase, 'original', manifest)
    missing = [item['id'] for item in contract['checkpoints']
               if _artifact(manifest, item['id'], 'png') is None]
    if missing:
        raise store.PhaseError('original PNG missing for: ' + ', '.join(missing))
    if contract['reverse_engineering']['include_globs'] and not manifest.get('reverse_index'):
        raise store.PhaseError('required reverse evidence is missing')
    if manifest['phase_contract_sha256'] != store.sha256_json(contract):
        raise store.PhaseError('original manifest contract changed')
    with store.phase_lock(phase):
        _, _, current = phase_capture.load_phase(project, phase_id)
        if current != status:
            raise store.PhaseError('phase changed during original freeze')
        status['state'] = 'oracle_frozen'
        store.atomic_write_json(phase / 'status.json', status)
    return status


def capture_clone(project, phase_id, selection, apk):
    recover_pending(project, phase_id)
    phase, contract, status = phase_capture.load_phase(project, phase_id)
    if status['state'] not in ('oracle_frozen', 'implementing', 'comparing',
                               'correcting', 'automated_ready', 'human_accepted'):
        raise store.PhaseError('clone capture requires a frozen original')
    apk = Path(apk).resolve()
    data = _selection(selection, phase_id, contract, apk,
                      'ditto_selected_clone')
    if len(data['selections']) != 1:
        raise store.PhaseError('clone comparison request needs one checkpoint')
    entry = data['selections'][0]
    checkpoint = _checkpoint(contract, entry['checkpoint_id'])
    original = _load_manifest(phase, 'original')
    _verify_manifest(phase, 'original', original)
    original_png = _artifact(original, checkpoint['id'], 'png')
    if data['environment'] != (original_png or {}).get('environment', original['controller']['environment']):
        raise store.PhaseError('clone capture environment differs from original')
    if original.get('phase_contract_sha256') != store.sha256_json(contract):
        raise store.PhaseError('original manifest contract changed')
    if original_png is None:
        raise store.PhaseError('original checkpoint PNG is missing')
    if entry.get('original_png_sha256') != original_png['sha256']:
        raise store.PhaseError('clone request references a stale original PNG hash')
    prior = _load_manifest(phase, 'clone')
    if prior:
        _verify_manifest(phase, 'clone', prior)
    package_sha = store.sha256_file(apk)
    manifest = _base_manifest(phase_id, 'clone', contract, data, package_sha, prior)
    stage = Path(tempfile.mkdtemp(prefix='.selected-clone.', dir=phase))
    try:
        _stage_selection(stage, data, contract, package_sha, manifest)
        if not prior or prior['package']['sha256'] != package_sha:
            shutil.copyfile(apk, stage / 'app.apk')
        work = stage / 'comparison'
        stem = _stem(checkpoint)
        original_xml = _artifact(original, checkpoint['id'], 'xml')
        clone_xml = _artifact(manifest, checkpoint['id'], 'xml')
        _, result = diff_screenshots.diff_screenshots(
            phase / 'original' / original_png['path'], stage / f'{stem}.png',
            work, xml_original=(phase / 'original' / original_xml['path'])
            if original_xml and clone_xml else None,
            xml_candidate=(stage / f'{stem}.xml')
            if original_xml and clone_xml else None,
            case_id=checkpoint['id'])
        result_name = f'{stem}.result.json'
        triptych_name = f'{stem}.triptych.png'
        diff_name = f'{stem}.diff.png'
        result.update({
            'original': str(phase / 'original' / original_png['path']),
            'clone': str(phase / 'clone' / f'{stem}.png'),
            'diff_image': str(phase / 'diff' / diff_name),
            'triptych_image': str(phase / 'diff' / triptych_name),
            'triptych': triptych_name,
            'original_png_sha256': original_png['sha256'],
            'clone_png_sha256': entry['png_sha256'],
            'clone_build_sha256': package_sha,
            'evidence_catalog': {
                f'diff:{result_name}': {'kind': 'visual_result',
                                        'path': result_name},
                f'diff:{triptych_name}': {'kind': 'triptych',
                                          'path': triptych_name},
                f'original:{original_png["path"]}': {'kind': 'png',
                                                       'path': original_png['path']},
                f'clone:{stem}.png': {'kind': 'png', 'path': f'{stem}.png'},
            },
        })
        for role, evidence_manifest in (('original', original), ('clone', manifest)):
            trace = _artifact(evidence_manifest, checkpoint['id'], 'trace')
            if trace:
                result['evidence_catalog'][f'{role}:{trace["path"]}'] = {
                    'kind': 'trace', 'path': trace['path']}
        if original_xml and clone_xml:
            result['evidence_catalog'][f'diff:{result_name}:layout'] = {
                'kind': 'layout_result', 'path': result_name}
        shutil.copyfile(work / 'triptych.png', stage / triptych_name)
        shutil.copyfile(work / 'diff.png', stage / diff_name)
        store.atomic_write_json(stage / result_name, result)
        store.atomic_write_json(stage / 'manifest.json', manifest)
        assembled_clone = stage / 'assembled-clone'
        assembled_diff = stage / 'diff'
        _linked_tree(phase / 'clone', assembled_clone)
        _linked_tree(phase / 'diff', assembled_diff)
        for source in list(stage.iterdir()):
            if source.is_file() and source.name in (
                    'app.apk', 'manifest.json', f'{stem}.png', f'{stem}.xml', f'{stem}.trace.json'):
                os.replace(source, assembled_clone / source.name)
            elif source.is_file():
                os.replace(source, assembled_diff / source.name)
        if clone_xml is None:
            (assembled_clone / f'{stem}.xml').unlink(missing_ok=True)
        with store.phase_lock(phase):
            _, locked_contract, locked_status = phase_capture.load_phase(project, phase_id)
            if locked_contract != contract or locked_status != status:
                raise store.PhaseError('phase changed during clone capture')
            pending = deepcopy(status)
            current = pending['checkpoints'].get(checkpoint['id'], {})
            _reset_checkpoint(current)
            pending['checkpoints'][checkpoint['id']] = current
            pending['state'] = 'comparing'
            pending['human_review']['status'] = 'pending'
            current.update({
                'active_result': result_name,
                'result_sha256': store.sha256_file(assembled_diff / result_name),
                'triptych_sha256': store.sha256_file(assembled_diff / triptych_name),
                'build_sha256': package_sha,
                'original_png_sha256': original_png['sha256'],
                'clone_png_sha256': entry['png_sha256'],
                'invalidated': False,
                'dimensions': {dimension: {'status': 'pending', 'rationale': None,
                                           'evidence': [], 'authorization': None,
                                           'history': []}
                               for dimension in checkpoint['required_dimensions']},
            })
            pending['active_clone_manifest_revision'] = 1
            pending['clone_manifest_revisions'] = [1]
            pending['active_clone_manifest_sha256'] = store.sha256_file(
                assembled_clone / 'manifest.json')
            write_report(stage, contract, pending)
            txn = _commit_current(phase, status, pending,
                                  {'clone': assembled_clone, 'diff': assembled_diff})
            store.atomic_write_json(phase / 'status.json', pending)
        shutil.rmtree(txn, ignore_errors=True)
        return {'ok': True, 'checkpoint_id': checkpoint['id'],
                'status': pending['state'],
                'result': str(phase / 'diff' / result_name),
                'triptych': str(phase / 'diff' / triptych_name),
                'report': str(phase / 'diff/report.json')}
    finally:
        shutil.rmtree(stage, ignore_errors=True)


def write_report(phase, contract, status):
    checkpoints = []
    for checkpoint in contract['checkpoints']:
        current = status['checkpoints'].get(checkpoint['id'], {})
        checkpoints.append({
            'checkpoint_id': checkpoint['id'],
            'result': current.get('active_result'),
            'dimensions': current.get('dimensions', {}),
            'invalidated': current.get('invalidated', False),
            'evidence_build_sha256': current.get('build_sha256'),
        })
    report = {'schema_version': 1, 'phase_id': contract['phase_id'],
              'state': status['state'], 'checkpoints': checkpoints,
              'human_review': status['human_review'], 'generated_at': _now()}
    store.atomic_write_json(phase / 'diff/report.json', report)
    return report
