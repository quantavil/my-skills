#!/usr/bin/env python3
"""Immutable storage and schema primitives for Ditto phase workspaces."""
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile

from pydantic import ValidationError
from phase_models import ContractModel, ID_PATTERN, StatusModel, validation_message

ID_RE = re.compile(ID_PATTERN)

class PhaseError(RuntimeError):
    """A phase record or workspace operation is invalid."""


def _object(value, label):
    if not isinstance(value, dict):
        raise PhaseError(f'{label} must be a JSON object')
    return value


def _id(value, label):
    if not isinstance(value, str) or not ID_RE.fullmatch(value):
        raise PhaseError(f'{label} must match [a-z0-9][a-z0-9_]*')
    return value


def sha256_file(path):
    digest = hashlib.sha256()
    try:
        with Path(path).open('rb') as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b''):
                digest.update(block)
    except OSError as error:
        raise PhaseError(f'cannot hash {path}: {error}') from None
    return digest.hexdigest()


def sha256_json(value):
    """Hash a JSON value using a stable, whitespace-independent encoding."""
    try:
        payload = json.dumps(value, sort_keys=True, separators=(',', ':'),
                             ensure_ascii=False).encode('utf-8')
    except (TypeError, ValueError) as error:
        raise PhaseError(f'value is not JSON serializable: {error}') from None
    return hashlib.sha256(payload).hexdigest()


def load_json(path):
    path = Path(path)
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except json.JSONDecodeError as error:
        raise PhaseError(f'{path} is not valid JSON: {error}') from None
    except OSError as error:
        raise PhaseError(f'cannot read {path}: {error}') from None
    return _object(data, str(path))


def atomic_write_json(path, data):
    _object(data, 'JSON value')
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=path.parent,
                                         prefix=f'.{path.name}.', suffix='.tmp',
                                         delete=False) as handle:
            temporary = Path(handle.name)
            json.dump(data, handle, indent=2, ensure_ascii=False)
            handle.write('\n')
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except OSError as error:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        raise PhaseError(f'cannot write {path}: {error}') from None


def write_immutable_json(path, data):
    path = Path(path)
    if path.exists():
        raise PhaseError(f'immutable file already exists: {path}')
    atomic_write_json(path, data)


def safe_child(root, value):
    root = Path(root).resolve()
    value = Path(value)
    if value.is_absolute():
        raise PhaseError(f'path must remain inside {root}: {value}')
    candidate = (root / value).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        raise PhaseError(f'path must remain inside {root}: {value}') from None
    return candidate


def checkpoint_stem(checkpoint, revision):
    if not isinstance(revision, int) or isinstance(revision, bool) or revision < 1:
        raise PhaseError('evidence revision must be a positive integer')
    number = checkpoint.get('number') if isinstance(checkpoint, dict) else None
    identifier = checkpoint.get('id') if isinstance(checkpoint, dict) else None
    if not isinstance(number, int) or isinstance(number, bool) or not 1 <= number <= 999:
        raise PhaseError('checkpoint number must be between 1 and 999')
    _id(identifier, 'checkpoint id')
    return f'{number:03d}_{identifier}.r{revision:03d}'


def versioned_path(directory, stem, revision, suffix):
    if not isinstance(stem, str) or not ID_RE.fullmatch(stem):
        raise PhaseError('versioned file stem must be a lowercase identifier')
    if not isinstance(revision, int) or isinstance(revision, bool) or revision < 1:
        raise PhaseError('revision must be a positive integer')
    suffix = str(suffix).lstrip('.')
    if not suffix or not re.fullmatch(r'[a-z0-9]+', suffix):
        raise PhaseError('versioned file suffix must be lowercase alphanumeric')
    return Path(directory) / f'{stem}.{revision:03d}.{suffix}'


def _validated(model, data):
    try:
        model.model_validate(data)
    except ValidationError as error:
        raise PhaseError(validation_message(error)) from None
    return data


def validate_contract(data, expected_phase_id=None):
    data = _validated(ContractModel, _object(data, 'phase contract'))
    if expected_phase_id is not None and data['phase_id'] != expected_phase_id:
        raise PhaseError(f"phase id {data['phase_id']!r} does not match {expected_phase_id!r}")
    return data


def validate_status(data, contract):
    data = _validated(StatusModel, _object(data, 'phase status'))
    contract = validate_contract(contract)
    if data['phase_id'] != contract['phase_id']:
        raise PhaseError('status phase id does not match contract')
    if data['phase_revision'] != contract['revision']:
        raise PhaseError('status phase revision does not match contract')
    unknown = sorted(set(data['checkpoints']) - {item['id'] for item in contract['checkpoints']})
    if unknown:
        raise PhaseError('status references unknown checkpoint: ' + ', '.join(unknown))
    return data


@contextmanager
def phase_lock(phase_dir):
    phase_dir = Path(phase_dir)
    phase_dir.mkdir(parents=True, exist_ok=True)
    lock_path = phase_dir / '.ditto.lock'
    payload = json.dumps({
        'pid': os.getpid(),
        'created_at': datetime.now(timezone.utc).isoformat(),
    }) + '\n'
    try:
        descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        detail = ''
        try:
            detail = f' ({lock_path.read_text(encoding="utf-8").strip()})'
        except OSError:
            pass
        raise PhaseError(f'phase is locked by another writer{detail}') from None
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8') as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        yield
    finally:
        lock_path.unlink(missing_ok=True)
