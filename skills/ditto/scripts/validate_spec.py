#!/usr/bin/env python3
"""Validate Ditto evidence/index.json and spec/coverage.json against contracts.md rules.
Python standard library only.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path
import sys

PLACEHOLDER_PREFIXES = ('REPLACE_WITH_', 'RECORD_ACTUAL_')


def project_path(root, value):
    if not isinstance(value, str) or not value or Path(value).is_absolute():
        raise ValueError('expected project-relative artifact path')
    path = (root / value).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError('artifact path escapes project root')
    return path


def read_object(path):
    data = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data, dict):
        raise ValueError('expected JSON object')
    return data


def id_list(value):
    return isinstance(value, list) and all(isinstance(x, str) and x for x in value)


def check_no_placeholders(val, path_str):
    errors = []
    if isinstance(val, str):
        for p in PLACEHOLDER_PREFIXES:
            if p in val:
                errors.append(f"Unreplaced template placeholder '{val}' in {path_str}")
    elif isinstance(val, dict):
        for k, v in val.items():
            errors.extend(check_no_placeholders(v, f"{path_str}.{k}"))
    elif isinstance(val, list):
        for i, item in enumerate(val):
            errors.extend(check_no_placeholders(item, f"{path_str}[{i}]"))
    return errors


def validate_evidence(evidence_path, root_dir=None, check_files=False):
    errors = []
    if not evidence_path.is_file():
        return [f"Evidence file missing: {evidence_path}"]

    try:
        data = read_object(evidence_path)
    except Exception as e:
        return [f"Failed to parse JSON in {evidence_path}: {e}"]

    if data.get('schema_version') != 1:
        errors.append(f"{evidence_path}: schema_version must be 1")

    records = data.get('records')
    if not isinstance(records, list):
        return errors + [f"{evidence_path}: 'records' must be a list"]

    seen_ids = {}
    root = root_dir or evidence_path.parent.parent

    for idx, rec in enumerate(records):
        loc = f"record[{idx}]"
        if not isinstance(rec, dict):
            errors.append(f'{loc}: expected object')
            continue
        rec_id = rec.get('id')
        if not rec_id or not isinstance(rec_id, str):
            errors.append(f"{loc}: missing or invalid 'id'")
        elif rec_id in seen_ids:
            errors.append(f"{loc}: duplicate record ID '{rec_id}'")
        else:
            seen_ids[rec_id] = rec

        errors.extend(check_no_placeholders(rec, f"{loc}"))

        for field in ('sha256', 'app_sha256'):
            if not isinstance(rec.get(field), str) or not re.fullmatch(r'[0-9a-fA-F]{64}', rec[field]):
                errors.append(f'{loc}: {field} must be a SHA-256 hex digest')
        rel_path = rec.get('path')
        if not rel_path or not isinstance(rel_path, str):
            errors.append(f"{loc}: missing or invalid 'path'")
        else:
            try:
                file_on_disk = project_path(root, rel_path)
            except ValueError as exc:
                errors.append(f'{loc}: {exc}')
                continue
            if not check_files:
                continue
            if not file_on_disk.is_file():
                errors.append(f"{loc}: referenced path '{rel_path}' does not exist on disk")
            else:
                expected_sha = rec.get('sha256')
                if isinstance(expected_sha, str) and re.fullmatch(r'[0-9a-fA-F]{64}', expected_sha):
                    file_sha = hashlib.sha256(file_on_disk.read_bytes()).hexdigest()
                    if file_sha.lower() != expected_sha.lower():
                        errors.append(f"{loc}: sha256 mismatch for '{rel_path}' (expected {expected_sha}, got {file_sha})")

    return errors, seen_ids


def validate_coverage(coverage_path, valid_evidence_ids, root=None):
    errors = []
    if not coverage_path.is_file():
        return [f"Coverage file missing: {coverage_path}"]

    try:
        data = read_object(coverage_path)
    except Exception as e:
        return [f"Failed to parse JSON in {coverage_path}: {e}"]

    if data.get('schema_version') != 1:
        errors.append(f"{coverage_path}: schema_version must be 1")

    cases = data.get('cases')
    if not isinstance(cases, list):
        return errors + [f"{coverage_path}: 'cases' must be a list"]

    seen_case_ids = set()
    root = root or coverage_path.parent.parent
    for idx, case in enumerate(cases):
        loc = f"case[{idx}]"
        if not isinstance(case, dict):
            errors.append(f'{loc}: expected object')
            continue
        case_id = case.get('id')
        if not case_id or not isinstance(case_id, str):
            errors.append(f"{loc}: missing or invalid 'id'")
        elif case_id in seen_case_ids:
            errors.append(f"{loc}: duplicate case ID '{case_id}'")
        else:
            seen_case_ids.add(case_id)

        errors.extend(check_no_placeholders(case, f"{loc}"))
        for field in ('observed', 'implemented', 'required', 'critical'):
            if field in case and not isinstance(case[field], bool):
                errors.append(f'{loc}: {field} must be boolean')
        for field in ('flow_id', 'platform', 'state_id'):
            if not isinstance(case.get(field), str) or not case[field].strip():
                errors.append(f'{loc}: missing or invalid {field}')

        ev_ids = case.get('evidence_ids', [])
        if not id_list(ev_ids):
            errors.append(f"{loc}: 'evidence_ids' must be a list")
            ev_ids = []

        if case.get('observed') is True and not ev_ids:
            errors.append(f"{loc} ('{case_id}'): claimed 'observed: true' but 'evidence_ids' is empty")

        for eid in ev_ids:
            if eid not in valid_evidence_ids:
                errors.append(f"{loc} ('{case_id}'): referenced evidence ID '{eid}' not found in evidence index")

        records = valid_evidence_ids if isinstance(valid_evidence_ids, dict) else {}
        def matching(eid, role):
            rec = records.get(eid, {})
            return (rec.get('role') == role and rec.get('runtime') is True
                    and rec.get('flow_id') == case.get('flow_id')
                    and rec.get('state_id') == case.get('state_id')
                    and rec.get('platform') == case.get('platform'))

        if case.get('observed') is True and not any(matching(eid, 'original') for eid in ev_ids):
            errors.append(f'{loc}: observed requires original runtime evidence for this flow/platform')

        val_result = case.get('validation')
        allowed_val = ('pass', 'fail', 'blocked', 'not_run', 'not_applicable')
        if val_result not in allowed_val:
            errors.append(f"{loc} ('{case_id}'): invalid validation status '{val_result}' (must be one of {allowed_val})")
        if val_result == 'not_applicable' and not str(case.get('reason') or '').strip():
            errors.append(f'{loc}: not_applicable requires reason')

        if val_result == 'pass':
            if case.get('observed') is not True or case.get('implemented') is not True:
                errors.append(f'{loc}: pass requires observed and implemented')
            try:
                comparison = read_object(project_path(root, case.get('comparison')))
                errors.extend(check_no_placeholders(comparison, f'{loc}.comparison'))
                if comparison.get('case_id') != case_id or comparison.get('result') != 'pass':
                    errors.append(f'{loc}: comparison must pass and match case_id')
                for field in ('method', 'fixture_id'):
                    if not isinstance(comparison.get(field), str) or not comparison[field].strip():
                        errors.append(f'{loc}: comparison requires {field}')
                if not id_list(comparison.get('steps')) or not comparison['steps']:
                    errors.append(f'{loc}: comparison requires replay steps')
                for role in ('original', 'candidate'):
                    build_hash = case.get(f'{role}_app_sha256')
                    if not isinstance(build_hash, str) or not re.fullmatch(r'[0-9a-fA-F]{64}', build_hash):
                        errors.append(f'{loc}: pass requires {role}_app_sha256')
                    ids = comparison.get(f'{role}_evidence_ids')
                    if not id_list(ids) or not ids:
                        errors.append(f'{loc}: comparison requires {role} evidence IDs')
                        continue
                    for eid in ids:
                        if eid not in ev_ids or not matching(eid, role):
                            errors.append(f'{loc}: invalid {role} runtime evidence {eid}')
                        elif records[eid].get('fixture_id') != comparison.get('fixture_id'):
                            errors.append(f'{loc}: fixture mismatch for {eid}')
                        elif str(records[eid].get('app_sha256', '')).lower() != str(build_hash).lower():
                            errors.append(f'{loc}: stale or mismatched {role} build for {eid}')
                required = case.get('required_dimensions')
                dimensions = comparison.get('dimensions')
                if not id_list(required) or not required or not isinstance(dimensions, dict):
                    errors.append(f'{loc}: pass requires required_dimensions and comparison dimensions')
                elif any(dimensions.get(d) != 'pass' for d in required) or any(v != 'pass' for v in dimensions.values()):
                    errors.append(f'{loc}: comparison has missing or non-passing dimensions')
            except (OSError, ValueError) as exc:
                errors.append(f'{loc}: invalid or missing comparison: {exc}')

        user_testing = case.get('user_testing', 'pending')
        if user_testing not in ('pending', 'accepted', 'changes_requested', 'waived'):
            errors.append(f'{loc}: invalid user_testing status')
        if user_testing in ('accepted', 'waived'):
            try:
                decision = project_path(root, case.get('user_decision'))
                if not decision.read_text(encoding='utf-8').strip():
                    errors.append(f'{loc}: empty user decision record')
            except (OSError, ValueError) as exc:
                errors.append(f'{loc}: user_testing requires user_decision artifact: {exc}')

    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence', type=Path, default=Path('evidence/index.json'),
                        help='Path to evidence/index.json (default: evidence/index.json)')
    parser.add_argument('--coverage', type=Path, default=Path('spec/coverage.json'),
                        help='Path to spec/coverage.json (default: spec/coverage.json)')
    parser.add_argument('--check-files', action='store_true',
                        help='Verify that paths in evidence index exist on disk and check SHA-256')
    parser.add_argument('--root', type=Path, default=None,
                        help='Root directory for relative paths (default: parent of evidence directory)')

    args = parser.parse_args()

    all_errors = []
    evidence_res = validate_evidence(args.evidence, root_dir=args.root, check_files=args.check_files)
    if isinstance(evidence_res, tuple):
        ev_errors, valid_ev_ids = evidence_res
        all_errors.extend(ev_errors)
    else:
        all_errors.extend(evidence_res)
        valid_ev_ids = set()

    cov_errors = validate_coverage(args.coverage, valid_ev_ids, args.root or args.evidence.parent.parent)
    all_errors.extend(cov_errors)

    if all_errors:
        print(f"Validation failed with {len(all_errors)} error(s):", file=sys.stderr)
        for err in all_errors:
            print(f"  - {err}", file=sys.stderr)
        return 1
    else:
        print("Contracts and evidence validation passed successfully. This checks record integrity, not behavioral truth or full app parity.")
        return 0


if __name__ == '__main__':
    sys.exit(main())
