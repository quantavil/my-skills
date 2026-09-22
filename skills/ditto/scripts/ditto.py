#!/usr/bin/env python3
"""Read-only Ditto record checks, JSON reporting and Mermaid coverage view."""
import argparse
import json
from pathlib import Path
import sys

import validate_spec


def graph_data(path):
    data = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data, dict) or not isinstance(data.get('cases'), list):
        raise ValueError('coverage must contain a cases array')
    cases = data['cases']
    ids = [case.get('id') if isinstance(case, dict) else None for case in cases]
    if any(not isinstance(item, str) or not item for item in ids):
        raise ValueError('every case needs a nonempty string id')
    if len(set(ids)) != len(ids):
        raise ValueError('duplicate case id')
    edges = data.get('transitions', [])
    if not isinstance(edges, list):
        raise ValueError('transitions must be an array')
    for edge in edges:
        if (not isinstance(edge, dict)
                or not isinstance(edge.get('from'), str)
                or not isinstance(edge.get('to'), str)
                or edge['from'] not in ids or edge['to'] not in ids
                or not isinstance(edge.get('action'), str)
                or not edge['action'].strip()):
            raise ValueError('each transition needs existing from/to case IDs and an action')
    return cases, edges


def label(value):
    # Mermaid decimal entities prevent labels from injecting syntax or HTML.
    return ''.join(char if char.isascii() and (char.isalnum() or char in ' ._-')
                   else f'#{ord(char)};' for char in str(value))


def mermaid(cases, edges):
    ids = {case['id']: f'n{index}' for index, case in enumerate(cases)}
    lines = ['flowchart TD', '  %% Recorded coverage only; not proof of completeness or parity.']
    if not cases:
        lines.append('  empty["No inventoried cases"]')
    for case in cases:
        text = f"{case['id']} | {case.get('validation', 'not_run')}"
        lines.append(f'  {ids[case["id"]]}["{label(text)}"]')
    for edge in edges:
        lines.append(f'  {ids[edge["from"]]} -->|"{label(edge["action"])}"| {ids[edge["to"]]}')
    return '\n'.join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('check', 'report', 'graph'))
    args = parser.parse_args(argv)
    graph_errors = []
    try:
        cases, edges = graph_data(Path('spec/coverage.json'))
    except (OSError, ValueError) as error:
        if args.command == 'graph':
            print(f'Coverage unavailable: {error}', file=sys.stderr)
            return 2
        graph_errors.append(f'Coverage graph: {error}')
    if args.command == 'graph':
        print(mermaid(cases, edges))
        return 0

    # Graph metadata is optional; a broken edge must not hide record findings.
    root = Path.cwd()
    evidence_errors, records = validate_spec.validate_evidence(
        Path('evidence/index.json'), root, args.command == 'check')
    coverage_errors, records_by_case = validate_spec.validate_coverage(
        Path('spec/coverage.json'), records, root)
    errors = evidence_errors + coverage_errors + graph_errors
    summary = validate_spec.summarise(records_by_case)
    scope_note = ('Record integrity only. Not proof of parity, and not a measure '
                  'of journeys that were never inventoried.')
    if args.command == 'report':
        print(json.dumps({
            'ok': not errors, 'error_count': len(errors), 'errors': errors,
            'errors_truncated': 0, 'summary': summary,
            'files_checked': False, 'scope_note': scope_note,
            'cases': [{
                'id': case['id'], 'observed': case.get('observed', False),
                'implemented': case.get('implemented', False),
                'validation': case.get('validation', 'not_run'),
                'user_testing': case.get('user_testing', 'pending'),
            } for case in records_by_case.values()],
        }, indent=2))
    elif errors:
        print(f'validation failed: {len(errors)} error(s)', file=sys.stderr)
        for error in errors:
            print(f'  - {error}', file=sys.stderr)
    else:
        print(f"records ok: {summary['required_passing']}/{summary['required']} "
              f"required case(s) passing, {summary['required_not_run']} not run, "
              f"{summary['required_blocked']} blocked")
        if summary['critical_not_passing']:
            print('critical cases not passing: '
                  + ', '.join(summary['critical_not_passing']))
        print(scope_note)
    return 1 if errors else 0


if __name__ == '__main__':
    sys.exit(main())
