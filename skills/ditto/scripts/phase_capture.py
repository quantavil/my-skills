#!/usr/bin/env python3
"""Phase workspace initialization, evidence collection, and compact reporting."""
from datetime import datetime, timezone
from copy import deepcopy
import os
from pathlib import Path
import shutil
import tempfile

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
        store.write_immutable_json(phase / 'phase.001.json', contract)
        store.atomic_write_json(phase / 'status.json', _initial_status(phase_id))
        (phase / 'notes.md').write_text(f'# {phase_id}\n', encoding='utf-8')
    except Exception:
        import shutil
        shutil.rmtree(phase, ignore_errors=True)
        raise
    return phase


def load_phase(project, phase_id):
    phase = phase_directory(project, phase_id)
    status = store.load_json(phase / 'status.json')
    revision = status.get('phase_revision')
    if not isinstance(revision, int):
        raise store.PhaseError('status has no valid phase revision')
    contract = store.load_json(store.versioned_path(phase, 'phase', revision, 'json'))
    store.validate_status(status, contract)
    return phase, contract, status


def require_collection_state(project, phase_id):
    phase, contract, status = load_phase(project, phase_id)
    if status['state'] != 'collecting_original' or status['preflight_revision'] is None:
        raise store.PhaseError('successful active preflight is required before collection')
    import phase_preflight
    phase_preflight.require_active_preflight(project, phase_id)
    return phase, contract, status


def _capture_expectations(contract, checkpoint_ids=None):
    expected = {}
    for checkpoint in contract['checkpoints']:
        if checkpoint_ids is not None and checkpoint['id'] not in checkpoint_ids:
            continue
        for kind in checkpoint['artifacts']:
            name = f"{checkpoint['number']:03d}_{checkpoint['id']}.{kind}"
            expected[name] = (checkpoint, kind)
    return expected


def _validate_controller_export(directory, contract, controller, build_sha,
                                checkpoint_ids=None):
    directory = Path(directory)
    if not directory.is_dir() or directory.is_symlink():
        raise store.PhaseError('controller export must be a real directory')
    directory = directory.resolve()
    capture_path = directory / 'capture.json'
    capture = store.load_json(capture_path)
    identity = {field: controller.get(field) for field in ('server', 'tool', 'session_id')}
    for field, value in identity.items():
        if capture.get(field) != value:
            raise store.PhaseError(f'controller capture uses a different {field}')
    if capture.get('schema_version') != 1 or capture.get('provenance') != 'mcp':
        raise store.PhaseError('controller capture must have MCP provenance')
    if capture.get('target') != controller.get('target'):
        raise store.PhaseError('controller capture uses a different device target')
    if not isinstance(capture.get('environment'), dict):
        raise store.PhaseError('controller capture needs environment facts')
    if not isinstance(capture.get('limitations'), list):
        raise store.PhaseError('controller capture limitations must be an array')
    if capture.get('installed_package_sha256') != build_sha:
        raise store.PhaseError('controller capture uses a different installed package')
    try:
        captured_at = datetime.fromisoformat(
            capture['captured_at'].replace('Z', '+00:00'))
        if captured_at.tzinfo is None:
            raise ValueError
        age = (datetime.now(timezone.utc) - captured_at.astimezone(timezone.utc)).total_seconds()
        if age < -300:
            raise ValueError
    except (KeyError, AttributeError, ValueError):
        raise store.PhaseError('controller capture needs a valid timestamp') from None

    expected = _capture_expectations(contract, checkpoint_ids)
    records = capture.get('artifacts')
    if not isinstance(records, list):
        raise store.PhaseError('controller artifacts must be an array')
    by_name = {}
    for record in records:
        if not isinstance(record, dict) or not isinstance(record.get('path'), str):
            raise store.PhaseError('controller artifact record is invalid')
        name = record['path']
        if name in by_name:
            raise store.PhaseError(f'duplicate controller artifact record: {name}')
        by_name[name] = record
    actual_files = set()
    for path in directory.iterdir():
        if path.name == 'capture.json':
            continue
        if path.is_symlink():
            raise store.PhaseError(f'controller export contains a symbolic link: {path.name}')
        if not path.is_file():
            raise store.PhaseError(f'controller export contains a non-file: {path.name}')
        actual_files.add(path.name)
    expected_names = set(expected)
    if set(by_name) != expected_names or actual_files != expected_names:
        missing = sorted(expected_names - (set(by_name) & actual_files))
        unexpected = sorted((set(by_name) | actual_files) - expected_names)
        detail = []
        if missing:
            detail.append('missing: ' + ', '.join(missing))
        if unexpected:
            detail.append('unexpected: ' + ', '.join(unexpected))
        raise store.PhaseError('controller artifact set differs from contract ('
                               + '; '.join(detail) + ')')

    checked = []
    for name in sorted(expected):
        checkpoint, kind = expected[name]
        record, path = by_name[name], directory / name
        required = {
            'checkpoint_id': checkpoint['id'], 'kind': kind,
            'server': identity['server'], 'tool': identity['tool'],
            'session_id': identity['session_id'], 'target': controller.get('target'),
            'action_result': 'success', 'provenance': 'mcp',
            'installed_package_sha256': build_sha,
            'fixture': checkpoint['fixture'],
            'setup_sha256': store.sha256_json(checkpoint['setup']),
            'actions_sha256': store.sha256_json(checkpoint['actions']),
        }
        if any(record.get(field) != value for field, value in required.items()):
            raise store.PhaseError(f'controller artifact provenance is invalid: {name}')
        digest = store.sha256_file(path)
        if record.get('sha256') != digest:
            raise store.PhaseError(f'controller artifact source hash is invalid: {name}')
        checked.append((name, path, checkpoint, kind, record, digest))
    return capture, checked


def _verify_manifest_files(role_dir, manifest):
    records = list(manifest.get('artifacts', []))
    records.append(manifest.get('package', {}))
    reverse = manifest.get('reverse_index')
    if isinstance(reverse, dict):
        records.append(reverse)
    for record in records:
        if not isinstance(record, dict) or not isinstance(record.get('path'), str):
            raise store.PhaseError('manifest contains an invalid file record')
        path = store.safe_child(role_dir, record['path'])
        if not path.is_file() or path.is_symlink():
            raise store.PhaseError(f'manifest file is missing: {record["path"]}')
        if store.sha256_file(path) != record.get('sha256'):
            raise store.PhaseError(f'manifest file hash is invalid: {record["path"]}')
    if isinstance(reverse, dict):
        index = store.load_json(store.safe_child(role_dir, reverse['path']))
        if index.get('package_sha256') != manifest.get('package', {}).get('sha256'):
            raise store.PhaseError('reverse index package identity is invalid')
        retained = index.get('retained_files')
        if not isinstance(retained, list):
            raise store.PhaseError('reverse index has no retained evidence list')
        for record in retained:
            if not isinstance(record, dict) or not isinstance(record.get('path'), str):
                raise store.PhaseError('reverse evidence record is invalid')
            path = store.safe_child(role_dir, record['path'])
            if (not path.is_file() or path.is_symlink()
                    or store.sha256_file(path) != record.get('sha256')):
                raise store.PhaseError(f'reverse evidence is missing or changed: '
                                       f'{record["path"]}')


def _same_file_tree(source, target):
    if not source.is_dir() or not target.is_dir():
        return False
    source_files = {path.relative_to(source) for path in source.rglob('*') if path.is_file()}
    target_files = {path.relative_to(target) for path in target.rglob('*') if path.is_file()}
    if source_files != target_files:
        return False
    return all(not (source / relative).is_symlink()
               and not (target / relative).is_symlink()
               and store.sha256_file(source / relative) ==
               store.sha256_file(target / relative)
               for relative in source_files)


def collect_pack(role, project, phase_id, build, controller_export,
                 build_metadata, preflight, mcp_exports=None, checkpoint_ids=None):
    if role not in ('original', 'clone'):
        raise store.PhaseError('pack role must be original or clone')
    if not isinstance(build_metadata, dict):
        raise store.PhaseError('build metadata must be an object')
    build = Path(build).resolve()
    suffix = build.suffix.lower().lstrip('.')
    if suffix not in ('apk', 'aab', 'ipa'):
        raise store.PhaseError('build must be an APK, AAB, or IPA')

    import phase_preflight
    active = phase_preflight.require_active_preflight(project, phase_id)
    if preflight != active:
        raise store.PhaseError('supplied preflight is not the active preflight')
    if role == 'original':
        phase, contract, status = load_phase(project, phase_id)
        previous_revision = status.get('original_manifest_revision')
        if previous_revision is None:
            phase, contract, status = require_collection_state(project, phase_id)
            if checkpoint_ids is not None:
                raise store.PhaseError('initial original collection must be complete')
            original_manifest = None
        elif status['state'] == 'collecting_original' and checkpoint_ids is None:
            original_manifest = None
        else:
            if status['state'] not in ('oracle_frozen', 'implementing',
                                       'comparing', 'correcting', 'automated_ready'):
                raise store.PhaseError('original revision requires a frozen oracle')
            valid_ids = {item['id'] for item in contract['checkpoints']}
            if (not isinstance(checkpoint_ids, list) or not checkpoint_ids
                    or len(set(checkpoint_ids)) != len(checkpoint_ids)
                    or set(checkpoint_ids) - valid_ids):
                raise store.PhaseError('original revision needs selected checkpoints')
            original_manifest = store.load_json(store.versioned_path(
                phase / 'original', 'manifest', previous_revision, 'json'))
    else:
        if checkpoint_ids is not None:
            raise store.PhaseError('clone checkpoint selection follows invalidation')
        phase, contract, status = load_phase(project, phase_id)
        if status['state'] not in ('oracle_frozen', 'implementing', 'comparing', 'correcting'):
            raise store.PhaseError('clone collection requires a frozen original oracle')
        original_revision = status.get('original_manifest_revision')
        if original_revision is None:
            raise store.PhaseError('clone collection requires an original manifest')
        original_manifest = store.load_json(store.versioned_path(
            phase / 'original', 'manifest', original_revision, 'json'))
    controller = active['mcps']['mobile-control']
    if role == 'clone':
        pending = {item['id'] for item in contract['checkpoints']
                   if status['checkpoints'].get(item['id'], {}).get('invalidated')
                   or not status['checkpoints'].get(item['id'], {}).get('active_result')}
        if pending:
            checkpoint_ids = pending
    package_sha = store.sha256_file(build)
    if role == 'original' and package_sha != active['package_sha256']:
        raise store.PhaseError('build does not match active preflight')
    capture, checked = _validate_controller_export(
        controller_export, contract, controller, package_sha, checkpoint_ids)
    if (original_manifest is not None
            and capture['environment'] != original_manifest['controller']['environment']):
        raise store.PhaseError('clone capture environment differs from the original oracle')
    role_dir = phase / role
    revision = len(list(role_dir.glob('manifest.[0-9][0-9][0-9].json'))) + 1
    stage = Path(tempfile.mkdtemp(prefix=f'.{role}-collection.', dir=phase))
    try:
        reverse = None
        if role == 'original':
            analysis_dir = stage / 'analysis'
            checkpoint_links = {}
            for checkpoint in contract['checkpoints']:
                for pattern in contract['reverse_engineering']['include_globs']:
                    checkpoint_links.setdefault(pattern, []).append(checkpoint['id'])
            import phase_package
            reverse = phase_package.analyze_package(
                build, analysis_dir, contract['reverse_engineering']['include_globs'],
                checkpoint_links, mcp_exports or {}, active)

        package_name = f'app.{package_sha[:8]}.{suffix}'
        shutil.copyfile(build, stage / package_name)
        artifacts = []
        if role == 'original' and original_manifest is not None:
            for retained in original_manifest['artifacts']:
                if retained['checkpoint_id'] in checkpoint_ids:
                    continue
                shutil.copyfile(role_dir / retained['path'], stage / retained['path'])
                artifacts.append(retained)
        for _, source, checkpoint, kind, record, digest in checked:
            canonical = f'{store.checkpoint_stem(checkpoint, revision)}.{kind}'
            shutil.copyfile(source, stage / canonical)
            artifacts.append({
                'checkpoint_id': checkpoint['id'], 'kind': kind,
                'path': canonical, 'sha256': digest,
                'source_sha256': record['sha256'], 'build_sha256': package_sha,
                'controller': {field: record[field] for field in (
                    'server', 'tool', 'session_id', 'target', 'action_result',
                    'provenance', 'installed_package_sha256', 'fixture',
                    'setup_sha256', 'actions_sha256')},
            })

        manifest = {
            'schema_version': 1, 'phase_id': phase_id, 'role': role,
            'revision': revision, 'phase_revision': contract['revision'],
            'phase_contract_sha256': store.sha256_file(
                store.versioned_path(phase, 'phase', contract['revision'], 'json')),
            'preflight_revision': active['revision'],
            'package': {'path': package_name, 'sha256': package_sha,
                        'metadata': build_metadata},
            'runtime_target': contract['runtime_target'],
            'fixtures': contract['fixtures'],
            'checkpoint_protocol': [{
                'id': item['id'], 'fixture': item['fixture'],
                'setup': item['setup'], 'setup_sha256': store.sha256_json(item['setup']),
                'actions': item['actions'], 'actions_sha256': store.sha256_json(item['actions']),
            } for item in contract['checkpoints']],
            'controller': {field: capture[field] for field in (
                'server', 'tool', 'session_id', 'target', 'environment',
                'limitations', 'provenance', 'installed_package_sha256',
                'captured_at')},
            'capture_sha256': store.sha256_file(Path(controller_export) / 'capture.json'),
            'artifacts': artifacts,
            'captured_at': capture['captured_at'],
        }
        if role == 'original':
            reverse_path = analysis_dir / 'reverse.001.json'
            manifest['reverse_index'] = {
                'path': 'reverse.001.json', 'sha256': store.sha256_file(reverse_path),
                'revision': reverse['revision'],
            }
            for source in sorted(analysis_dir.iterdir()):
                os.replace(source, stage / source.name)
            analysis_dir.rmdir()
        store.write_immutable_json(stage / f'manifest.{revision:03d}.json', manifest)
        manifest_sha = store.sha256_file(stage / f'manifest.{revision:03d}.json')
        _verify_manifest_files(stage, manifest)

        with store.phase_lock(phase):
            _, current_contract, current_status = load_phase(project, phase_id)
            if (current_status.get('preflight_revision') != active['revision']
                    or current_status.get('original_manifest_revision') !=
                    status.get('original_manifest_revision') or current_contract != contract
                    or (role == 'clone' and current_status.get(
                        'active_clone_manifest_revision') !=
                        status.get('active_clone_manifest_revision'))):
                raise store.PhaseError('phase changed during collection')
            destinations = []
            for source in sorted(stage.iterdir()):
                target = role_dir / source.name
                if target.exists():
                    if (source.is_file() and target.is_file()
                            and not source.name.startswith('manifest.')
                            and store.sha256_file(source) == store.sha256_file(target)):
                        source.unlink()
                        continue
                    if role == 'original' and source.name == 'reverse.001':
                        matching = _same_file_tree(source, target)
                        if not matching:
                            raise store.PhaseError('reverse evidence differs from retained index')
                        if source.is_dir():
                            shutil.rmtree(source)
                        else:
                            source.unlink()
                        continue
                    raise store.PhaseError(f'immutable evidence already exists: {target}')
                destinations.append((source, target))
            if role == 'original' and (role_dir / 'reverse.001.json').exists():
                existing = store.load_json(role_dir / 'reverse.001.json')
                if existing.get('package_sha256') != reverse.get('package_sha256'):
                    raise store.PhaseError('existing reverse index belongs to another package')
            for source, target in destinations:
                os.replace(source, target)
            if role == 'original':
                current_status['original_manifest_revision'] = revision
                current_status['original_manifest_sha256'] = manifest_sha
                if original_manifest is not None:
                    now = datetime.now(timezone.utc).isoformat()
                    for identifier in checkpoint_ids:
                        current = current_status['checkpoints'].get(identifier)
                        if not isinstance(current, dict):
                            continue
                        current['invalidated'] = True
                        current['invalidated_at'] = now
                        current['closed'] = False
                        for dimension in current.get('dimensions', {}).values():
                            prior = {key: value for key, value in dimension.items()
                                     if key != 'history'}
                            history = list(dimension.get('history', []))
                            if dimension.get('status') != 'pending':
                                history.append(prior)
                            dimension.update({
                                'status': 'pending', 'rationale': None,
                                'evidence': [], 'authorization': None,
                                'history': history,
                            })
                    current_status['invalidation_history'].append({
                        'timestamp': now, 'changed_paths': [],
                        'resolved_components': [],
                        'reopened_checkpoints': sorted(checkpoint_ids),
                        'superseded_results': {},
                        'reason': 'new original oracle evidence',
                    })
                    if current_status.get('active_clone_manifest_revision') is not None:
                        current_status['state'] = 'correcting'
                    current_status['human_review']['status'] = 'pending'
            else:
                current_status['clone_manifest_revisions'].append(revision)
                current_status['active_clone_manifest_revision'] = revision
                current_status['active_clone_manifest_sha256'] = manifest_sha
                current_status['state'] = 'comparing'
            store.atomic_write_json(phase / 'status.json', current_status)
        return manifest
    finally:
        shutil.rmtree(stage, ignore_errors=True)


def freeze_original(project, phase_id):
    phase, contract, status = require_collection_state(project, phase_id)
    if not contract['scope']['summary'].strip() or contract['scope']['unknowns']:
        raise store.PhaseError('phase scope must be complete before freezing')
    if not contract['checkpoints']:
        raise store.PhaseError('phase must contain at least one checkpoint')
    revision = status.get('original_manifest_revision')
    if revision is None:
        raise store.PhaseError('original manifest is missing')
    manifest_path = store.versioned_path(phase / 'original', 'manifest', revision, 'json')
    manifest = store.load_json(manifest_path)
    contract_path = store.versioned_path(phase, 'phase', contract['revision'], 'json')
    if manifest.get('phase_contract_sha256') != store.sha256_file(contract_path):
        raise store.PhaseError('phase contract hash differs from original manifest')
    _verify_manifest_files(phase / 'original', manifest)
    with store.phase_lock(phase):
        _, _, current = load_phase(project, phase_id)
        if current.get('original_manifest_revision') != revision:
            raise store.PhaseError('original manifest changed during freeze')
        try:
            contract_path.chmod(contract_path.stat().st_mode & ~0o222)
        except OSError as error:
            raise store.PhaseError(f'cannot make phase contract immutable: {error}') from None
        current['state'] = 'oracle_frozen'
        current['blockers'] = []
        store.atomic_write_json(phase / 'status.json', current)
        return current


def rebind_original(project, phase_id, revised_contract_path, reason):
    """Bind unchanged raw oracle files to revised wording without recapturing them."""
    phase, old_contract, status = load_phase(project, phase_id)
    if status['state'] != 'oracle_frozen' or status['active_clone_manifest_revision'] is not None:
        raise store.PhaseError('rebind requires a frozen original before clone collection')
    if not isinstance(reason, str) or not reason.strip():
        raise store.PhaseError('rebind needs an audit reason')
    next_phase_revision = old_contract['revision'] + 1
    expected_path = store.versioned_path(phase, 'phase', next_phase_revision, 'json')
    if Path(revised_contract_path).resolve() != expected_path.resolve():
        raise store.PhaseError(f'revised contract must be {expected_path}')
    revised = store.validate_contract(store.load_json(expected_path), phase_id)
    if revised['revision'] != next_phase_revision:
        raise store.PhaseError('revised contract has the wrong revision')
    for key in ('platform', 'runtime_target', 'fixtures'):
        if revised[key] != old_contract[key]:
            raise store.PhaseError(f'rebind cannot change {key}')
    if (revised['reverse_engineering']['include_globs'] !=
            old_contract['reverse_engineering']['include_globs']):
        raise store.PhaseError('rebind cannot change packaged original resources')
    old_checkpoints = {item['id']: item for item in old_contract['checkpoints']}
    new_checkpoints = {item['id']: item for item in revised['checkpoints']}
    if old_checkpoints.keys() != new_checkpoints.keys():
        raise store.PhaseError('rebind cannot add or remove checkpoints')
    old_path = store.versioned_path(phase / 'original', 'manifest',
                                    status['original_manifest_revision'], 'json')
    if store.sha256_file(old_path) != status.get('original_manifest_sha256'):
        raise store.PhaseError('original manifest hash differs from status')
    old_manifest = store.load_json(old_path)
    _verify_manifest_files(phase / 'original', old_manifest)
    changed = set()
    trace_hashes = {}
    for identifier, before in old_checkpoints.items():
        after = new_checkpoints[identifier]
        for key in ('number', 'id', 'fixture', 'artifacts'):
            if after[key] != before[key]:
                raise store.PhaseError(f'{identifier}: rebind cannot change {key}')
        prior_incidental = before.get('incidental_actions', [])
        incidental = after.get('incidental_actions', [])
        if (not isinstance(incidental, list) or len(incidental) != len(set(incidental))
                or incidental[:len(prior_incidental)] != prior_incidental
                or any(label not in before['actions'] for label in incidental[len(prior_incidental):])
                or after['actions'] != [label for label in before['actions']
                                        if label not in incidental[len(prior_incidental):]]):
            raise store.PhaseError(f'{identifier}: revised actions must only remove declared incidental actions')
        if after['setup'] != before['setup'] or after['actions'] != before['actions']:
            changed.add(identifier)
        if after['actions'] != before['actions']:
            trace = next((item for item in old_manifest['artifacts']
                          if item['checkpoint_id'] == identifier and item['kind'] == 'trace'), None)
            if trace is None:
                raise store.PhaseError(f'{identifier}: action rebind requires retained trace')
            trace_path = phase / 'original' / trace['path']
            recorded = store.load_json(trace_path).get('actions')
            if (not isinstance(recorded, list) or
                    [item.get('step') for item in recorded
                     if item.get('step') and item['step'] not in prior_incidental]
                    != before['actions']):
                raise store.PhaseError(f'{identifier}: source trace differs from old protocol')
            trace_hashes[identifier] = store.sha256_file(trace_path)
    manifest = deepcopy(old_manifest)
    revision = old_manifest['revision'] + 1
    manifest.update({
        'revision': revision, 'phase_revision': next_phase_revision,
        'phase_contract_sha256': store.sha256_file(expected_path),
        'checkpoint_protocol': [{
            'id': item['id'], 'fixture': item['fixture'], 'setup': item['setup'],
            'setup_sha256': store.sha256_json(item['setup']),
            'actions': item['actions'], 'actions_sha256': store.sha256_json(item['actions']),
        } for item in revised['checkpoints']],
        'rebound_from': {'manifest': old_path.name,
                         'sha256': store.sha256_file(old_path)},
        'rebind_reason': reason.strip(),
        'rebound_at': datetime.now(timezone.utc).isoformat(),
    })
    for artifact in manifest['artifacts']:
        identifier = artifact['checkpoint_id']
        if identifier not in changed:
            continue
        before, after = old_checkpoints[identifier], new_checkpoints[identifier]
        artifact['binding'] = {
            'setup_sha256': store.sha256_json(after['setup']),
            'actions_sha256': store.sha256_json(after['actions']),
            'source_setup_sha256': artifact['controller']['setup_sha256'],
            'source_actions_sha256': artifact['controller']['actions_sha256'],
            'source_trace_sha256': (trace_hashes.get(identifier)
                                    or artifact.get('binding', {}).get('source_trace_sha256')),
            'incidental_actions': after.get('incidental_actions', []),
            'reason': reason.strip(),
        }
    _verify_manifest_files(phase / 'original', manifest)
    manifest_path = store.versioned_path(phase / 'original', 'manifest', revision, 'json')
    with store.phase_lock(phase):
        _, current_contract, current_status = load_phase(project, phase_id)
        if current_contract != old_contract or current_status != status:
            raise store.PhaseError('phase changed during rebind')
        store.write_immutable_json(manifest_path, manifest)
        current_status['phase_revision'] = next_phase_revision
        current_status['original_manifest_revision'] = revision
        current_status['original_manifest_sha256'] = store.sha256_file(manifest_path)
        current_status['invalidation_history'].append({
            'timestamp': manifest['rebound_at'], 'changed_paths': [],
            'resolved_components': [], 'reopened_checkpoints': sorted(changed),
            'superseded_results': {}, 'reason': 'original contract rebind: ' + reason.strip(),
        })
        store.atomic_write_json(phase / 'status.json', current_status)
        expected_path.chmod(expected_path.stat().st_mode & ~0o222)
    return manifest


def phase_report(project, phase_id):
    _, contract, status = load_phase(project, phase_id)
    total = len(contract['checkpoints'])
    closed = sum(1 for value in status['checkpoints'].values()
                 if isinstance(value, dict) and value.get('closed') is True)
    return {
        'schema_version': 1, 'phase_id': phase_id, 'state': status['state'],
        'revisions': {'phase': status['phase_revision'],
                      'preflight': status['preflight_revision'],
                      'original': status['original_manifest_revision'],
                      'clone': status['active_clone_manifest_revision']},
        'checkpoint_counts': {'total': total, 'closed': closed, 'open': total - closed},
        'invalidations': len(status['invalidation_history']),
        'human_review': status['human_review']['status'], 'blockers': status['blockers'],
    }
