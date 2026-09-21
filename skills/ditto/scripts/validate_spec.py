#!/usr/bin/env python3
"""Check evidence/index.json and spec/coverage.json for record integrity.

This is a record-integrity check, not a certification of parity. It verifies
that claims are structurally supported and that provenance links hold. It
cannot discover journeys you never inventoried, verify that the capture
environment was comparable, or authenticate user feedback.

Exit 0 clean, 1 on validation errors, 2 on a usage or I/O failure.
Standard library only.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

PLACEHOLDER_PREFIXES = ('REPLACE_WITH_', 'RECORD_ACTUAL_', 'TODO', 'FIXME', 'XXX_')
SHA256_RE = re.compile(r'^[0-9a-fA-F]{64}$')
VALIDATION_STATES = ('pass', 'fail', 'blocked', 'not_run', 'not_applicable')
DIMENSION_VERDICTS = ('pass', 'fail', 'blocked', 'not_run', 'not_applicable')
USER_TESTING_STATES = ('pending', 'accepted', 'changes_requested', 'waived')
ROLES = ('original', 'candidate')
DEFAULT_ERROR_CAP = 25


# --------------------------------------------------------------------------

def project_path(root, value, label='artifact path'):
    if not isinstance(value, str) or not value:
        raise ValueError(f'{label}: expected a project-relative path string')
    if Path(value).is_absolute():
        raise ValueError(f'{label}: must be project-relative, got an absolute path')
    resolved = (root / value).resolve()
    if not resolved.is_relative_to(root.resolve()):
        raise ValueError(f'{label}: escapes the project root')
    return resolved


def read_object(path):
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    if not isinstance(data, dict):
        raise ValueError('expected a JSON object at the top level')
    return data


def is_id_list(value):
    return isinstance(value, list) and all(isinstance(x, str) and x.strip() for x in value)


def find_placeholders(value, where):
    out = []
    if isinstance(value, str):
        if any(prefix in value for prefix in PLACEHOLDER_PREFIXES):
            out.append(f'{where}: unreplaced template placeholder {value!r}')
    elif isinstance(value, dict):
        for key, item in value.items():
            out.extend(find_placeholders(item, f'{where}.{key}'))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            out.extend(find_placeholders(item, f'{where}[{index}]'))
    return out


# --------------------------------------------------------------------------

def validate_evidence(path, root, check_files=False):
    """Always returns (errors, records_by_id). Callers never branch on the type."""
    errors, by_id = [], {}
    path = Path(path)
    if not path.is_file():
        return [f'evidence index missing: {path}'], by_id
    try:
        data = read_object(path)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        return [f'{path}: {error}'], by_id

    if data.get('schema_version') != 1:
        errors.append(f'{path}: schema_version must be 1')
    records = data.get('records')
    if not isinstance(records, list):
        return errors + [f'{path}: "records" must be a list'], by_id

    for index, record in enumerate(records):
        where = f'evidence[{index}]'
        if not isinstance(record, dict):
            errors.append(f'{where}: expected an object')
            continue
        record_id = record.get('id')
        if not isinstance(record_id, str) or not record_id.strip():
            errors.append(f'{where}: missing or invalid "id"')
            record_id = None
        elif record_id in by_id:
            errors.append(f'{where}: duplicate evidence id {record_id!r}')
            record_id = None
        where = f'evidence[{index}]' + (f' ({record_id})' if record_id else '')
        errors.extend(find_placeholders(record, where))

        # Validate provenance fields here so a typo is reported at its source
        # instead of surfacing as a confusing downstream coverage error.
        if record.get('role') not in ROLES:
            errors.append(f'{where}: "role" must be one of {ROLES}, got {record.get("role")!r}')
        if not isinstance(record.get('runtime'), bool):
            errors.append(f'{where}: "runtime" must be a boolean')
        for field in ('flow_id', 'state_id', 'platform', 'kind'):
            if not isinstance(record.get(field), str) or not record[field].strip():
                errors.append(f'{where}: missing or invalid "{field}"')
        for field in ('sha256', 'app_sha256'):
            if not isinstance(record.get(field), str) or not SHA256_RE.match(record[field]):
                errors.append(f'{where}: "{field}" must be a 64-character SHA-256 hex digest')
        identity = record.get('runtime_identity')
        if identity is not None:
            if not isinstance(identity, dict) or identity.get('mode') not in (
                    'installed', 'hot-reload', 'instrumented'):
                errors.append(f'{where}: invalid runtime_identity')
            elif identity['mode'] != 'installed':
                sources = identity.get('sources')
                if not identity.get('session') or not isinstance(sources, list) or not sources:
                    errors.append(f'{where}: modified runtime requires session and source hashes')
                elif any(not isinstance(s, dict) or not s.get('path')
                         or not isinstance(s.get('sha256'), str)
                         or not SHA256_RE.fullmatch(s['sha256']) for s in sources):
                    errors.append(f'{where}: invalid runtime source hashes')

        relative = record.get('path')
        try:
            on_disk = project_path(root, relative, f'{where}.path')
        except ValueError as error:
            errors.append(str(error))
            on_disk = None
        if on_disk is not None and check_files:
            if not on_disk.is_file():
                errors.append(f'{where}: referenced artifact {relative!r} is not on disk')
            else:
                expected = record.get('sha256')
                if isinstance(expected, str) and SHA256_RE.match(expected):
                    actual = hashlib.sha256(on_disk.read_bytes()).hexdigest()
                    if actual.lower() != expected.lower():
                        errors.append(
                            f'{where}: sha256 mismatch for {relative!r} '
                            f'(recorded {expected[:12]}…, file is {actual[:12]}…)')
        if record_id:
            by_id[record_id] = record
    return errors, by_id


# --------------------------------------------------------------------------

def _matches(record, case, role):
    return (isinstance(record, dict)
            and record.get('role') == role
            and record.get('runtime') is True
            and record.get('flow_id') == case.get('flow_id')
            and record.get('state_id') == case.get('state_id')
            and record.get('platform') == case.get('platform'))


def _check_comparison(case, case_id, where, root, records, evidence_ids):
    """Validate the comparison record a passing case points at."""
    errors = []
    try:
        comparison_file = project_path(root, case.get('comparison'), f'{where}.comparison')
        comparison = read_object(comparison_file)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        return [f'{where}: pass requires a readable comparison record ({error})']

    errors.extend(find_placeholders(comparison, f'{where}.comparison'))
    if comparison.get('case_id') != case_id:
        errors.append(f'{where}: comparison case_id does not match this case')
    if comparison.get('result') != 'pass':
        errors.append(f'{where}: comparison result is not "pass"')
    for field in ('method', 'fixture_id'):
        if not isinstance(comparison.get(field), str) or not comparison[field].strip():
            errors.append(f'{where}: comparison requires a nonempty "{field}"')
    if not is_id_list(comparison.get('steps')) or not comparison['steps']:
        errors.append(f'{where}: comparison requires replay steps')

    for role in ROLES:
        build_hash = case.get(f'{role}_app_sha256')
        if not isinstance(build_hash, str) or not SHA256_RE.match(build_hash):
            errors.append(f'{where}: pass requires "{role}_app_sha256"')
            build_hash = None
        role_ids = comparison.get(f'{role}_evidence_ids')
        if not is_id_list(role_ids) or not role_ids:
            errors.append(f'{where}: comparison requires {role} evidence ids')
            continue
        for eid in role_ids:
            record = records.get(eid)
            if eid not in evidence_ids:
                errors.append(f'{where}: comparison cites {eid!r}, '
                              f'which the case does not list in evidence_ids')
            elif not _matches(record, case, role):
                errors.append(f'{where}: {eid!r} is not {role} runtime evidence '
                              f'for this flow/state/platform')
            elif record.get('fixture_id') != comparison.get('fixture_id'):
                errors.append(f'{where}: {eid!r} was captured under fixture '
                              f'{record.get("fixture_id")!r}, comparison claims '
                              f'{comparison.get("fixture_id")!r}')
            elif build_hash and str(record.get('app_sha256', '')).lower() != build_hash.lower():
                errors.append(f'{where}: {eid!r} belongs to a different {role} build '
                              f'than the case records')
            if record and (record.get('runtime_identity') is not None
                           or case.get(f'{role}_runtime_sha256') is not None):
                digest = hashlib.sha256(json.dumps(
                    record.get('runtime_identity', {'mode': 'installed'}),
                    sort_keys=True, separators=(',', ':')).encode()).hexdigest()
                if digest != case.get(f'{role}_runtime_sha256'):
                    errors.append(f'{where}: {eid!r} belongs to a different {role} runtime revision')

    required = case.get('required_dimensions')
    dimensions = comparison.get('dimensions')
    if not is_id_list(required) or not required:
        errors.append(f'{where}: pass requires a nonempty "required_dimensions"')
        return errors
    if not isinstance(dimensions, dict) or not dimensions:
        errors.append(f'{where}: comparison requires a "dimensions" object')
        return errors

    reasons = comparison.get('dimension_reasons') or {}
    if not isinstance(reasons, dict):
        errors.append(f'{where}: dimension_reasons must be an object')
        reasons = {}
    for name, verdict in dimensions.items():
        if verdict not in DIMENSION_VERDICTS:
            errors.append(f'{where}: dimension {name!r} has invalid verdict {verdict!r}')
        elif verdict == 'not_applicable':
            # A dimension may be legitimately inapplicable, but it must be
            # justified. Silence and a lie must not be equally easy.
            if not str(reasons.get(name, '')).strip():
                errors.append(f'{where}: dimension {name!r} is not_applicable but '
                              f'comparison.dimension_reasons has no reason for it')
            if name in required:
                errors.append(f'{where}: {name!r} is listed in required_dimensions '
                              f'but recorded as not_applicable')
        elif verdict != 'pass':
            errors.append(f'{where}: dimension {name!r} did not pass ({verdict})')
    for name in required:
        if name not in dimensions:
            errors.append(f'{where}: required dimension {name!r} has no recorded verdict')
    return errors


def validate_coverage(path, records, root):
    errors, cases_seen = [], {}
    path = Path(path)
    if not path.is_file():
        return [f'coverage file missing: {path}'], cases_seen
    try:
        data = read_object(path)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        return [f'{path}: {error}'], cases_seen

    if data.get('schema_version') != 1:
        errors.append(f'{path}: schema_version must be 1')
    cases = data.get('cases')
    if not isinstance(cases, list):
        return errors + [f'{path}: "cases" must be a list'], cases_seen

    ledger_loaded = bool(records)
    for index, case in enumerate(cases):
        where = f'case[{index}]'
        if not isinstance(case, dict):
            errors.append(f'{where}: expected an object')
            continue
        case_id = case.get('id')
        if not isinstance(case_id, str) or not case_id.strip():
            errors.append(f'{where}: missing or invalid "id"')
            case_id = None
        elif case_id in cases_seen:
            errors.append(f'{where}: duplicate case id {case_id!r}')
            case_id = None
        where = f'case[{index}]' + (f' ({case_id})' if case_id else '')
        if case_id:
            cases_seen[case_id] = case
        errors.extend(find_placeholders(case, where))

        for field in ('observed', 'implemented', 'required', 'critical'):
            if field in case and not isinstance(case[field], bool):
                errors.append(f'{where}: "{field}" must be a boolean, got {case[field]!r}')
        for field in ('flow_id', 'platform', 'state_id'):
            if not isinstance(case.get(field), str) or not case[field].strip():
                errors.append(f'{where}: missing or invalid "{field}"')

        evidence_ids = case.get('evidence_ids', [])
        if not is_id_list(evidence_ids):
            errors.append(f'{where}: "evidence_ids" must be a list of ids')
            evidence_ids = []
        if ledger_loaded:
            for eid in evidence_ids:
                if eid not in records:
                    errors.append(f'{where}: evidence id {eid!r} is not in the evidence index')

        if case.get('observed') is True:
            if not evidence_ids:
                errors.append(f'{where}: claims observed but lists no evidence')
            elif ledger_loaded and not any(
                    _matches(records.get(e), case, 'original') for e in evidence_ids):
                errors.append(f'{where}: observed requires original runtime evidence '
                              f'matching this flow/state/platform')

        validation = case.get('validation')
        if validation not in VALIDATION_STATES:
            errors.append(f'{where}: "validation" must be one of {VALIDATION_STATES}, '
                          f'got {validation!r}')
        if validation == 'not_applicable' and not str(case.get('reason') or '').strip():
            errors.append(f'{where}: not_applicable requires a "reason"')
        if validation == 'blocked' and not str(case.get('blocker') or '').strip():
            errors.append(f'{where}: blocked requires a recorded "blocker"')
        if validation == 'pass':
            if case.get('observed') is not True or case.get('implemented') is not True:
                errors.append(f'{where}: pass requires observed and implemented to be true')
            if ledger_loaded and case_id:
                errors.extend(_check_comparison(case, case_id, where, root,
                                                records, evidence_ids))
            elif not ledger_loaded:
                errors.append(f'{where}: pass cannot be checked because the evidence '
                              f'index did not load')

        user_testing = case.get('user_testing', 'pending')
        if user_testing not in USER_TESTING_STATES:
            errors.append(f'{where}: "user_testing" must be one of {USER_TESTING_STATES}')
        if user_testing in ('accepted', 'waived'):
            try:
                decision = project_path(root, case.get('user_decision'), f'{where}.user_decision')
                if not decision.read_text(encoding='utf-8').strip():
                    errors.append(f'{where}: user decision record is empty')
            except (OSError, ValueError) as error:
                errors.append(f'{where}: {user_testing} requires a user_decision record ({error})')
    return errors, cases_seen


# --------------------------------------------------------------------------

def summarise(cases):
    required = [c for c in cases.values() if c.get('required', True)]
    critical = [c for c in cases.values() if c.get('critical')]
    counted = lambda group, state: sum(1 for c in group if c.get('validation') == state)
    return {
        'cases_total': len(cases),
        'required': len(required),
        'required_passing': counted(required, 'pass'),
        'required_failing': counted(required, 'fail'),
        'required_blocked': counted(required, 'blocked'),
        'required_not_run': counted(required, 'not_run'),
        'critical': len(critical),
        'critical_not_passing': [c.get('id') for c in critical
                                 if c.get('validation') != 'pass'],
        'observed': sum(1 for c in cases.values() if c.get('observed') is True),
        'implemented': sum(1 for c in cases.values() if c.get('implemented') is True),
        'user_accepted': sum(1 for c in cases.values()
                             if c.get('user_testing') == 'accepted'),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--evidence', type=Path, default=Path('evidence/index.json'))
    parser.add_argument('--coverage', type=Path, default=Path('spec/coverage.json'))
    parser.add_argument('--root', type=Path, default=None,
                        help='project root for relative paths (default: parent of evidence dir)')
    parser.add_argument('--check-files', action='store_true',
                        help='also confirm referenced artifacts exist and match their digests')
    parser.add_argument('--json', action='store_true', help='machine-readable report on stdout')
    parser.add_argument('--max-errors', type=int, default=DEFAULT_ERROR_CAP,
                        help=f'cap printed errors (default {DEFAULT_ERROR_CAP}; 0 for all)')
    args = parser.parse_args(argv)

    root = (args.root or args.evidence.parent.parent).resolve()
    evidence_errors, records = validate_evidence(args.evidence, root, args.check_files)
    coverage_errors, cases = validate_coverage(args.coverage, records, root)
    errors = evidence_errors + coverage_errors
    summary = summarise(cases)

    if args.json:
        shown = errors if args.max_errors == 0 else errors[:args.max_errors]
        print(json.dumps({
            'ok': not errors,
            'error_count': len(errors),
            'errors': shown,
            'errors_truncated': len(errors) - len(shown),
            'summary': summary,
            'scope_note': 'Record integrity only. Not proof of parity, and not a '
                          'measure of journeys that were never inventoried.',
        }, indent=2))
        return 1 if errors else 0

    if errors:
        shown = errors if args.max_errors == 0 else errors[:args.max_errors]
        print(f'validation failed: {len(errors)} error(s)', file=sys.stderr)
        for error in shown:
            print(f'  - {error}', file=sys.stderr)
        if len(errors) > len(shown):
            print(f'  … {len(errors) - len(shown)} more (use --max-errors 0)', file=sys.stderr)
        return 1

    print(f"records ok: {summary['required_passing']}/{summary['required']} required case(s) "
          f"passing, {summary['required_not_run']} not run, "
          f"{summary['required_blocked']} blocked")
    if summary['critical_not_passing']:
        print('critical cases not passing: '
              + ', '.join(summary['critical_not_passing']))
    print('Record integrity only. This does not establish parity, and it says '
          'nothing about journeys never inventoried.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
