#!/usr/bin/env python3
"""Compulsory MCP capability preflight for Ditto phases."""
from datetime import datetime, timezone
from pathlib import Path

import phase_store as store
from pydantic import ValidationError
from phase_models import ReceiptModel, validation_message

REQUIRED_ANDROID_FLUTTER_MCPS = (
    'jadx', 'apktool', 'r2flutter', 'mobile-control')
CONTROLLER_PROBES = ('launch', 'tap', 'type', 'swipe', 'back', 'screenshot', 'hierarchy')


def _validate_receipt(data, package_sha, runtime_target):
    if not isinstance(data, dict):
        raise store.PhaseError('MCP receipt must be a JSON object')
    try:
        receipt = ReceiptModel.model_validate(data)
    except ValidationError as error:
        first = error.errors()[0]
        if first['loc'] == ('capability',):
            raise store.PhaseError(f"unknown MCP capability: {data.get('capability')!r}") from None
        raise store.PhaseError(validation_message(error)) from None
    capability, target = receipt.capability, receipt.target
    if capability == 'mobile-control':
        if target != runtime_target:
            raise store.PhaseError('mobile-control target differs from phase contract')
        if receipt.probes is None or any(receipt.probes.get(name) is not True
                                          for name in CONTROLLER_PROBES):
            raise store.PhaseError('mobile-control MCP lacks a required capability')
        if receipt.environment is None:
            raise store.PhaseError('mobile-control MCP needs environment facts')
        if receipt.screenshot_sha256 is None:
            raise store.PhaseError('mobile-control MCP needs a screenshot hash')
    else:
        if target.get('package_sha256') != package_sha:
            raise store.PhaseError(f'{capability} MCP loaded the wrong package')
        if capability == 'r2flutter':
            if receipt.supported is not True:
                raise store.PhaseError(f'{capability} does not support this Flutter target')
            if not receipt.abi or not receipt.dart_profile:
                raise store.PhaseError(f'{capability} did not report an ABI or Dart profile')
    return data


def _block(phase, status, reasons):
    current = dict(status)
    current['state'] = 'blocked'
    current['blockers'] = list(reasons)
    store.atomic_write_json(phase / 'status.json', current)


def record_preflight(project, phase_id, package, mcp_receipts):
    import phase_capture
    phase, contract, status = phase_capture.load_phase(project, phase_id)
    errors = []
    package = Path(package).resolve()
    if not package.is_file():
        errors.append(f'package does not exist: {package}')
        package_sha = None
    else:
        package_sha = store.sha256_file(package)

    receipts = {}
    if not isinstance(mcp_receipts, list):
        errors.append('MCP receipts must be a list')
        mcp_receipts = []
    for receipt_path in mcp_receipts:
        try:
            data = store.load_json(receipt_path)
            capability = data.get('capability')
            if capability in receipts:
                raise store.PhaseError(f'duplicate MCP capability: {capability}')
            if package_sha is None:
                raise store.PhaseError('cannot validate MCP targets without the package')
            receipts[capability] = _validate_receipt(
                data, package_sha, contract.get('runtime_target'))
        except store.PhaseError as error:
            errors.append(str(error))
    missing_mcps = sorted(set(REQUIRED_ANDROID_FLUTTER_MCPS) - set(receipts))
    if missing_mcps:
        errors.append('missing required MCPs: ' + ', '.join(missing_mcps))

    with store.phase_lock(phase):
        if errors:
            _block(phase, status, errors)
            raise store.PhaseError('; '.join(errors))
        revision = len(list(phase.glob('preflight.[0-9][0-9][0-9].json'))) + 1
        record = {
            'schema_version': 1, 'phase_id': phase_id, 'revision': revision,
            'phase_revision': contract['revision'], 'package': str(package),
            'package_sha256': package_sha, 'mcps': receipts,
            'recorded_at': datetime.now(timezone.utc).isoformat(),
        }
        store.write_immutable_json(
            store.versioned_path(phase, 'preflight', revision, 'json'), record)
        status['preflight_revision'] = revision
        if status.get('original_manifest_revision') is None:
            status['state'] = 'collecting_original'
        elif status['state'] == 'blocked':
            status['state'] = ('correcting' if status.get('active_clone_manifest_revision')
                               is not None else 'oracle_frozen')
        status['blockers'] = []
        store.atomic_write_json(phase / 'status.json', status)
        return record


def require_active_preflight(project, phase_id):
    import phase_capture
    phase, contract, status = phase_capture.load_phase(project, phase_id)
    revision = status.get('preflight_revision')
    if revision is None:
        raise store.PhaseError('active preflight is missing')
    record = store.load_json(store.versioned_path(phase, 'preflight', revision, 'json'))
    errors = []
    package_sha, package_path = record.get('package_sha256'), Path(record.get('package', ''))
    if not package_path.is_file() or store.sha256_file(package_path) != package_sha:
        errors.append('preflight package changed or disappeared')
    recorded = record.get('mcps', {})
    for capability in REQUIRED_ANDROID_FLUTTER_MCPS:
        try:
            _validate_receipt(recorded.get(capability), package_sha,
                              contract.get('runtime_target'))
        except store.PhaseError as error:
            errors.append(str(error))
    if errors:
        with store.phase_lock(phase):
            _block(phase, status, errors)
        raise store.PhaseError('; '.join(errors))
    return record
