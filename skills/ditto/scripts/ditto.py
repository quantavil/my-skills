#!/usr/bin/env python3
"""Ditto phase workspace command line interface."""
import json
from pathlib import Path
import sys
from typing import Annotated

import typer

sys.path.insert(0, str(Path(__file__).resolve().parent))
import phase_capture  # noqa: E402
import phase_compare  # noqa: E402
import phase_preflight  # noqa: E402
import phase_store  # noqa: E402

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
    """Create a phase workspace."""
    print(phase_capture.init_phase(project, phase_id))


@phase.command('report')
def report(phase_id: str, project: Project = Path.cwd()):
    """Print compact phase status."""
    emit(phase_capture.phase_report(project, phase_id))


@phase.command('preflight')
def preflight(phase_id: str, package: Annotated[Path, typer.Option('--package')],
              receipt: Annotated[list[Path], typer.Option('--receipt')],
              project: Project = Path.cwd()):
    """Record compulsory capabilities."""
    record = phase_preflight.record_preflight(project, phase_id, package, receipt)
    emit({'ok': True, 'revision': record['revision']})


@phase.command('collect-original')
def collect_original(
    phase_id: str,
    package: Annotated[Path, typer.Option('--package')],
    controller_export: Annotated[Path, typer.Option('--controller-export')],
    mcp_export: Annotated[list[str], typer.Option('--mcp-export')],
    checkpoint: Annotated[list[str] | None, typer.Option('--checkpoint')] = None,
    build_metadata: Annotated[str, typer.Option('--build-metadata')] = '{}',
    project: Project = Path.cwd(),
):
    """Collect a complete original evidence pack."""
    pairs = [path_pair(value) for value in mcp_export]
    exports = dict(pairs)
    if len(exports) != len(pairs):
        raise phase_store.PhaseError('duplicate --mcp-export name')
    active = phase_preflight.require_active_preflight(project, phase_id)
    manifest = phase_capture.collect_pack(
        'original', project, phase_id, package, controller_export,
        json.loads(build_metadata), active, exports, checkpoint_ids=checkpoint)
    emit({'ok': True, 'revision': manifest['revision']})


@phase.command('freeze-original')
def freeze_original(phase_id: str, project: Project = Path.cwd()):
    """Freeze the original oracle."""
    status = phase_capture.freeze_original(project, phase_id)
    emit({'ok': True, 'state': status['state']})


@phase.command('rebind-original')
def rebind_original(
    phase_id: str,
    contract: Annotated[Path, typer.Option('--contract')],
    reason: Annotated[str, typer.Option('--reason')],
    project: Project = Path.cwd(),
):
    """Rebind frozen raw oracle evidence to revised wording and incidental actions."""
    manifest = phase_capture.rebind_original(project, phase_id, contract, reason)
    emit({'ok': True, 'revision': manifest['revision'],
          'phase_revision': manifest['phase_revision']})


@phase.command('capture-clone')
def capture_clone(phase_id: str, apk: Annotated[Path, typer.Option('--apk')],
                  controller_export: Annotated[Path, typer.Option('--controller-export')],
                  build_metadata: Annotated[str, typer.Option('--build-metadata')] = '{}',
                  project: Project = Path.cwd()):
    """Capture a clone evidence pack."""
    active = phase_preflight.require_active_preflight(project, phase_id)
    manifest = phase_capture.collect_pack(
        'clone', project, phase_id, apk, controller_export,
        json.loads(build_metadata), active)
    emit({'ok': True, 'revision': manifest['revision']})


@phase.command('compare')
def compare(phase_id: str, project: Project = Path.cwd()):
    """Compare captured checkpoints."""
    emit(phase_compare.compare_phase(project, phase_id))


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
    """Record a semantic verdict."""
    result = phase_compare.record_verdict(
        project, phase_id, checkpoint_id, dimension, status, rationale,
        evidence, authorization)
    emit({'ok': True, 'verdict': result})


@phase.command('invalidate')
def invalidate(phase_id: str, changed: Annotated[list[str], typer.Option('--changed')],
               project: Project = Path.cwd()):
    """Reopen affected checkpoints."""
    emit(phase_compare.invalidate(project, phase_id, changed))


@phase.command('ready')
def ready(phase_id: str, project: Project = Path.cwd()):
    """Run the automated readiness gate."""
    status = phase_compare.ready_phase(project, phase_id)
    emit({'ok': True, 'state': status['state']})


@phase.command('review')
def review(phase_id: str, note: Annotated[str, typer.Option('--note')],
           accept: Annotated[bool, typer.Option('--accept')] = False,
           request_changes: Annotated[list[str] | None, typer.Option('--request-changes')] = None,
           project: Project = Path.cwd()):
    """Record final human review."""
    if accept == bool(request_changes):
        raise phase_store.PhaseError('provide either --accept or --request-changes')
    decision = 'accept' if accept else 'request_changes'
    status = phase_compare.record_review(project, phase_id, decision, note, request_changes or [])
    emit({'ok': True, 'state': status['state']})


def main(argv=None):
    try:
        try:
            app(args=argv, prog_name='ditto.py')
        except SystemExit as error:
            if error.code != 0:
                raise
        return 0
    except phase_compare.ReadinessError as error:
        print('ditto: automated readiness not met', file=sys.stderr)
        for reason in error.errors:
            print(f'- {reason}', file=sys.stderr)
        return 1
    except (phase_store.PhaseError, ValueError) as error:
        print(f'ditto: {error}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
