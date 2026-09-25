#!/usr/bin/env python3
"""Safe package inventory and verified MCP export import."""
from collections import Counter
import fnmatch
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import tempfile
import zipfile

import inventory
import phase_store as store

REQUIRED_REVERSE_MCPS = ('jadx', 'apktool', 'r2flutter')
MAX_SELECTED_BYTES = 512 * 1024 * 1024


def _unsafe(member):
    name = member.filename
    return (name.startswith('/') or '\\' in name or '..' in PurePosixPath(name).parts
            or stat.S_ISLNK(member.external_attr >> 16))


def _selected(name, patterns):
    return any(fnmatch.fnmatchcase(name, pattern) for pattern in patterns)


def _copy_mcp_export(capability, source, destination, expected_receipt, retained):
    source = Path(source)
    if not source.is_dir() or source.is_symlink():
        raise store.PhaseError(f'{capability} MCP export must be a real directory')
    source = source.resolve()
    receipt_path = source / 'receipt.json'
    receipt = store.load_json(receipt_path)
    if receipt != expected_receipt or receipt.get('provenance') != 'mcp':
        raise store.PhaseError(f'{capability} MCP export does not match active preflight')
    total = 0
    for name in ('receipt.json', 'result.json'):
        path = source / name
        if not path.is_file() or path.is_symlink():
            raise store.PhaseError(f'{capability} MCP export is missing {name}')
        relative = Path(name)
        target = store.safe_child(destination, Path('mcp') / capability / relative)
        total += path.stat().st_size
        if total > MAX_SELECTED_BYTES:
            raise store.PhaseError(f'{capability} MCP export exceeds the size limit')
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
        retained.append({
            'source': f'mcp:{capability}/{relative.as_posix()}',
            'path': target.relative_to(destination.parent).as_posix(),
            'sha256': store.sha256_file(target),
            'bytes': target.stat().st_size,
            'checkpoints': [],
        })


def analyze_package(package, destination, include_globs, checkpoint_links,
                    mcp_exports, preflight):
    package = Path(package).resolve()
    destination = Path(destination).resolve()
    if destination.exists():
        raise store.PhaseError(f'analysis destination already exists: {destination}')
    if not package.is_file():
        raise store.PhaseError(f'package does not exist: {package}')
    package_sha = store.sha256_file(package)
    if not isinstance(preflight, dict) or preflight.get('package_sha256') != package_sha:
        raise store.PhaseError('package does not match active preflight')
    if not isinstance(include_globs, list) or any(not isinstance(item, str) or not item
                                                  for item in include_globs):
        raise store.PhaseError('include_globs must contain nonempty strings')
    if not isinstance(checkpoint_links, dict):
        raise store.PhaseError('checkpoint_links must be an object')
    active_mcps = preflight.get('mcps')
    if not isinstance(active_mcps, dict):
        raise store.PhaseError('active preflight has no MCP records')
    expected_exports = set(REQUIRED_REVERSE_MCPS)
    missing = sorted(expected_exports - set(mcp_exports))
    extra = sorted(set(mcp_exports) - set(REQUIRED_REVERSE_MCPS))
    if missing:
        raise store.PhaseError('missing MCP export: ' + ', '.join(missing))
    if extra:
        raise store.PhaseError('unknown MCP export: ' + ', '.join(extra))

    framework_inventory = inventory.inventory(package)
    parent = destination.parent
    parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=f'.{destination.name}.', dir=parent))
    reverse_dir = stage / 'reverse'
    reverse_dir.mkdir()
    retained = []
    try:
        with zipfile.ZipFile(package) as archive:
            members = archive.infolist()
            duplicates = sorted(name for name, count in Counter(
                member.filename for member in members).items() if count > 1)
            if duplicates:
                raise store.PhaseError('package contains duplicate members: '
                                       + ', '.join(duplicates[:5]))
            unsafe = [member.filename for member in members if _unsafe(member)]
            if unsafe:
                raise store.PhaseError('package contains unsafe members: '
                                       + ', '.join(unsafe[:5]))
            encrypted = [member.filename for member in members if member.flag_bits & 1]
            if encrypted:
                raise store.PhaseError('package contains encrypted members: '
                                       + ', '.join(encrypted[:5]))
            selected = [member for member in members
                        if not member.is_dir() and _selected(member.filename, include_globs)]
            if sum(member.file_size for member in selected) > MAX_SELECTED_BYTES:
                raise store.PhaseError('selected package resources exceed the size limit')
            for member in selected:
                target = store.safe_child(reverse_dir, member.filename)
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(member) as source, target.open('xb') as output:
                    shutil.copyfileobj(source, output)
                retained.append({
                    'source': member.filename,
                    'path': target.relative_to(stage).as_posix(),
                    'sha256': store.sha256_file(target),
                    'bytes': target.stat().st_size,
                    'checkpoints': checkpoint_links.get(member.filename, []),
                })

        mcp_index = {}
        for capability in REQUIRED_REVERSE_MCPS:
            expected = active_mcps.get(capability)
            if not isinstance(expected, dict):
                raise store.PhaseError(f'active preflight has no {capability} MCP record')
            _copy_mcp_export(capability, mcp_exports[capability], reverse_dir,
                             expected, retained)
            mcp_index[capability] = {
                field: expected.get(field)
                for field in ('server', 'tool', 'tool_version', 'session_id', 'target')
            }

        result = {
            'schema_version': 1,
            'revision': 1,
            'package': str(package),
            'package_sha256': package_sha,
            'framework_inventory': framework_inventory,
            'mcps': mcp_index,
            'retained_files': sorted(retained, key=lambda item: item['path']),
            'checkpoint_links': checkpoint_links,
            'limitations': [
                'Decompiler output is inferred until confirmed by runtime evidence.',
                'Only contract-selected package members are retained in the phase workspace.',
            ],
        }
        store.atomic_write_json(stage / 'reverse.json', result)
        os.replace(stage, destination)
        return result
    except Exception:
        shutil.rmtree(stage, ignore_errors=True)
        raise
