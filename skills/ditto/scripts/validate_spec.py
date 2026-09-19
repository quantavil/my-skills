#!/usr/bin/env python3
"""Validate Ditto evidence/index.json and spec/coverage.json against contracts.md rules.
Python standard library only.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

PLACEHOLDER_PREFIXES = ('REPLACE_WITH_', 'RECORD_ACTUAL_')


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
        data = json.loads(evidence_path.read_text(encoding='utf-8'))
    except Exception as e:
        return [f"Failed to parse JSON in {evidence_path}: {e}"]

    if data.get('schema_version') != 1:
        errors.append(f"{evidence_path}: schema_version must be 1")

    records = data.get('records')
    if not isinstance(records, list):
        return errors + [f"{evidence_path}: 'records' must be a list"]

    seen_ids = set()
    root = root_dir or evidence_path.parent.parent

    for idx, rec in enumerate(records):
        loc = f"record[{idx}]"
        rec_id = rec.get('id')
        if not rec_id or not isinstance(rec_id, str):
            errors.append(f"{loc}: missing or invalid 'id'")
        elif rec_id in seen_ids:
            errors.append(f"{loc}: duplicate record ID '{rec_id}'")
        else:
            seen_ids.add(rec_id)

        errors.extend(check_no_placeholders(rec, f"{loc}"))

        rel_path = rec.get('path')
        if not rel_path or not isinstance(rel_path, str):
            errors.append(f"{loc}: missing or invalid 'path'")
        elif check_files:
            file_on_disk = root / rel_path
            if not file_on_disk.is_file():
                errors.append(f"{loc}: referenced path '{rel_path}' does not exist on disk")
            else:
                expected_sha = rec.get('sha256')
                if expected_sha and not expected_sha.startswith('REPLACE_WITH_'):
                    file_sha = hashlib.sha256(file_on_disk.read_bytes()).hexdigest()
                    if file_sha.lower() != expected_sha.lower():
                        errors.append(f"{loc}: sha256 mismatch for '{rel_path}' (expected {expected_sha}, got {file_sha})")

    return errors, seen_ids


def validate_coverage(coverage_path, valid_evidence_ids):
    errors = []
    if not coverage_path.is_file():
        return [f"Coverage file missing: {coverage_path}"]

    try:
        data = json.loads(coverage_path.read_text(encoding='utf-8'))
    except Exception as e:
        return [f"Failed to parse JSON in {coverage_path}: {e}"]

    if data.get('schema_version') != 1:
        errors.append(f"{coverage_path}: schema_version must be 1")

    cases = data.get('cases')
    if not isinstance(cases, list):
        return errors + [f"{coverage_path}: 'cases' must be a list"]

    seen_case_ids = set()
    for idx, case in enumerate(cases):
        loc = f"case[{idx}]"
        case_id = case.get('id')
        if not case_id or not isinstance(case_id, str):
            errors.append(f"{loc}: missing or invalid 'id'")
        elif case_id in seen_case_ids:
            errors.append(f"{loc}: duplicate case ID '{case_id}'")
        else:
            seen_case_ids.add(case_id)

        errors.extend(check_no_placeholders(case, f"{loc}"))

        ev_ids = case.get('evidence_ids', [])
        if not isinstance(ev_ids, list):
            errors.append(f"{loc}: 'evidence_ids' must be a list")
            ev_ids = []

        if case.get('observed') is True and not ev_ids:
            errors.append(f"{loc} ('{case_id}'): claimed 'observed: true' but 'evidence_ids' is empty")

        for eid in ev_ids:
            if eid not in valid_evidence_ids:
                errors.append(f"{loc} ('{case_id}'): referenced evidence ID '{eid}' not found in evidence index")

        val_result = case.get('validation')
        allowed_val = ('pass', 'fail', 'blocked', 'not_run', 'not_applicable')
        if val_result not in allowed_val:
            errors.append(f"{loc} ('{case_id}'): invalid validation status '{val_result}' (must be one of {allowed_val})")

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

    if args.coverage.exists():
        cov_errors = validate_coverage(args.coverage, valid_ev_ids)
        all_errors.extend(cov_errors)

    if all_errors:
        print(f"Validation failed with {len(all_errors)} error(s):", file=sys.stderr)
        for err in all_errors:
            print(f"  - {err}", file=sys.stderr)
        return 1
    else:
        print("Contracts and evidence validation passed successfully.")
        return 0


if __name__ == '__main__':
    sys.exit(main())
