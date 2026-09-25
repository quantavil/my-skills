#!/usr/bin/env python3
"""Ditto current-evidence phase command line interface."""
import json
from pathlib import Path
import sys
from typing import Annotated

import typer
from typer._click.exceptions import ClickException

sys.path.insert(0, str(Path(__file__).resolve().parent))
import phase_capture
import phase_compare
import phase_current
import phase_preflight
import phase_store

app = typer.Typer(add_completion=False, no_args_is_help=True)
phase = typer.Typer(add_completion=False, no_args_is_help=True)
app.add_typer(phase, name='phase', help='Manage a parity phase')
Project = Annotated[Path, typer.Option('--project')]


def emit(value):
    print(json.dumps(value, indent=2))


def path_pair(value):
    name, separator, path = value.partition('=')
    if not separator or not name or not path:
        raise phase_store.PhaseError('value must use NAME=PATH')
    return name, Path(path)


@phase.command('init')
def init(phase_id: str, project: Project = Path.cwd()):
    print(phase_capture.init_phase(project, phase_id))


@phase.command('report')
def report(phase_id: str, project: Project = Path.cwd()):
    emit(phase_capture.phase_report(project, phase_id))


@phase.command('preflight')
def preflight(phase_id: str, package: Annotated[Path, typer.Option('--package')],
              receipt: Annotated[list[Path], typer.Option('--receipt')],
              project: Project = Path.cwd()):
    record = phase_preflight.record_preflight(project, phase_id, package, receipt)
    emit({'ok': True, 'status': 'collecting_original',
          'preflight': str(phase_capture.phase_directory(project, phase_id) / 'preflight.json')})


@phase.command('select-original')
def select_original(
    phase_id: str,
    selection: Annotated[Path, typer.Option('--selection')],
    package: Annotated[Path, typer.Option('--package')],
    mcp_export: Annotated[list[str] | None, typer.Option('--mcp-export')] = None,
    replace_frozen: Annotated[bool, typer.Option('--replace-frozen')] = False,
    project: Project = Path.cwd(),
):
    pairs = [path_pair(value) for value in (mcp_export or [])]
    exports = dict(pairs)
    if len(exports) != len(pairs):
        raise phase_store.PhaseError('duplicate --mcp-export name')
    manifest = phase_current.select_original(project, phase_id, selection, package,
                                              replace_frozen, exports)
    emit({'ok': True, 'status': phase_capture.load_phase(project, phase_id)[2]['state'],
          'selected': sorted({item['checkpoint_id'] for item in manifest['artifacts']}),
          'manifest': str(phase_capture.phase_directory(project, phase_id) /
                          'original/manifest.json')})


@phase.command('freeze-original')
def freeze_original(phase_id: str, project: Project = Path.cwd()):
    status = phase_current.freeze_original(project, phase_id)
    emit({'ok': True, 'state': status['state']})


@phase.command('capture-clone')
def capture_clone(phase_id: str,
                  selection: Annotated[Path, typer.Option('--selection')],
                  apk: Annotated[Path, typer.Option('--apk')],
                  project: Project = Path.cwd()):
    emit(phase_current.capture_clone(project, phase_id, selection, apk))


@phase.command('verdict')
def verdict(
    phase_id: str, checkpoint_id: str,
    dimension: Annotated[str, typer.Option('--dimension')],
    status: Annotated[str, typer.Option('--status')],
    rationale: Annotated[str, typer.Option('--rationale')],
    evidence: Annotated[list[str], typer.Option('--evidence')],
    authorization: Annotated[str | None, typer.Option('--authorization')] = None,
    project: Project = Path.cwd(),
):
    result = phase_compare.record_verdict(
        project, phase_id, checkpoint_id, dimension, status, rationale,
        evidence, authorization)
    emit({'ok': True, 'verdict': result})


@phase.command('invalidate')
def invalidate(phase_id: str,
               changed: Annotated[list[str], typer.Option('--changed')],
               project: Project = Path.cwd()):
    emit(phase_compare.invalidate(project, phase_id, changed))


@phase.command('ready')
def ready(phase_id: str, project: Project = Path.cwd()):
    status = phase_compare.ready_phase(project, phase_id)
    emit({'ok': True, 'state': status['state']})


@phase.command('review')
def review(phase_id: str, note: Annotated[str, typer.Option('--note')],
           accept: Annotated[bool, typer.Option('--accept')] = False,
           request_changes: Annotated[list[str] | None, typer.Option('--request-changes')] = None,
           project: Project = Path.cwd()):
    if accept == bool(request_changes):
        raise phase_store.PhaseError('provide either --accept or --request-changes')
    decision = 'accept' if accept else 'request_changes'
    status = phase_compare.record_review(project, phase_id, decision, note,
                                          request_changes or [])
    emit({'ok': True, 'state': status['state'],
          'human_review': status['human_review']['status']})


def main(argv=None):
    try:
        app(args=argv, standalone_mode=False)
    except (phase_store.PhaseError, ValueError, OSError, ClickException) as error:
        print(f'ditto: {error}', file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
