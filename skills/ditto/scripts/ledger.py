#!/usr/bin/env python3
"""Write the Ditto evidence ledger. validate_spec.py reads and checks it.

Nothing here decides whether the candidate matches the original. These
subcommands only record what was captured, with real hashes, so that no
digest is ever typed by hand:

  capture     pull a checkpoint off a connected Android device and record it
  adopt       register files captured some other way (iOS, manual, historical)
  comparison  write a comparison record and set the coverage case result
  init        create an empty ledger and coverage file

Every subcommand is additive and refuses to silently overwrite a record.
Standard library only.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pngtool  # noqa: E402

DIMENSIONS = ('visual', 'behavior', 'navigation', 'network',
              'persistence', 'platform', 'accessibility')
RESULTS = ('pass', 'fail', 'blocked', 'not_run', 'not_applicable')
ID_RE = re.compile(r'^[a-z0-9][a-z0-9._-]*$')


class LedgerError(RuntimeError):
    pass


# --------------------------------------------------------------------------
# small helpers
# --------------------------------------------------------------------------

def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def check_id(value, label):
    if not isinstance(value, str) or not ID_RE.match(value):
        raise LedgerError(f'{label} must be lowercase [a-z0-9._-]: {value!r}')
    return value


def load_json(path, default):
    if not Path(path).exists():
        return default
    try:
        data = json.loads(Path(path).read_text(encoding='utf-8'))
    except json.JSONDecodeError as error:
        raise LedgerError(f'{path} is not valid JSON: {error}') from None
    if not isinstance(data, dict):
        raise LedgerError(f'{path} must contain a JSON object')
    return data


def save_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    temp.replace(path)
    return path


def relative_to(root, path):
    rel = Path(path).resolve().relative_to(Path(root).resolve())
    return rel.as_posix()


def runtime_identity(args, root):
    """Record injected source separately from the installed APK/IPA identity."""
    if args.runtime_mode == 'installed':
        if args.runtime_source or args.runtime_session:
            raise LedgerError('runtime source/session requires hot-reload or instrumented mode')
        return {'mode': 'installed'}
    if not args.runtime_source or not args.runtime_session:
        raise LedgerError('modified runtime requires --runtime-source and --runtime-session')
    sources = [{'path': relative_to(root, path), 'sha256': sha256_file(path)}
               for path in args.runtime_source]
    return {'mode': args.runtime_mode, 'session': args.runtime_session,
            'sources': sorted(sources, key=lambda item: item['path'])}


def runtime_digest(record):
    return hashlib.sha256(json.dumps(record.get('runtime_identity', {'mode': 'installed'}),
                         sort_keys=True, separators=(',', ':')).encode()).hexdigest()


# --------------------------------------------------------------------------
# adb
# --------------------------------------------------------------------------

def adb_binary():
    explicit = os.environ.get('DITTO_ADB')
    if explicit:
        if not Path(explicit).is_file() or not os.access(explicit, os.X_OK):
            raise LedgerError(f'DITTO_ADB is not executable: {explicit}')
        return explicit
    found = shutil.which('adb')
    if found:
        return found
    sdk = os.environ.get('ANDROID_HOME') or os.environ.get('ANDROID_SDK_ROOT')
    if sdk:
        candidate = Path(sdk) / 'platform-tools' / 'adb'
        if candidate.is_file():
            return str(candidate)
    raise LedgerError('adb not found. Set DITTO_ADB or ANDROID_HOME, or use "adopt".')


def adb(serial, *args, binary=None, timeout=60, check=True):
    cmd = [binary or adb_binary(), *(['-s', serial] if serial else []), *args]
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise LedgerError(f'adb timed out: {" ".join(args)}') from None
    if check and proc.returncode != 0:
        detail = proc.stderr.decode('utf-8', 'replace').strip()
        raise LedgerError(f'adb {" ".join(args)} failed ({proc.returncode}): {detail}')
    return proc


def adb_text(serial, *args, binary=None, default=''):
    proc = adb(serial, *args, binary=binary, check=False)
    if proc.returncode != 0:
        return default
    return proc.stdout.decode('utf-8', 'replace').replace('\r\n', '\n').strip()


def device_environment(serial, binary):
    """Common environment facts; callers record other relevant settings."""
    properties = dict(re.findall(r'^\[([^]]+)\]: \[(.*)\]$',
                      adb_text(serial, 'shell', 'getprop', binary=binary), re.MULTILINE))
    size = adb_text(serial, 'shell', 'wm', 'size', binary=binary)
    density = adb_text(serial, 'shell', 'wm', 'density', binary=binary)
    override = re.search(r'Override size:\s*(\d+)x(\d+)', size)
    physical = re.search(r'Physical size:\s*(\d+)x(\d+)', size)
    chosen = override or physical
    d_override = re.search(r'Override density:\s*(\d+)', density)
    d_physical = re.search(r'Physical density:\s*(\d+)', density)
    d_chosen = d_override or d_physical
    dpi = int(d_chosen.group(1)) if d_chosen else None
    env = {
        'serial': serial,
        'viewport_px': f'{chosen.group(1)}x{chosen.group(2)}' if chosen else None,
        'density_dpi': dpi,
        'device_pixel_ratio': round(dpi / 160, 4) if dpi else None,
        'os_release': properties.get('ro.build.version.release'),
        'sdk_int': properties.get('ro.build.version.sdk'),
        'model': properties.get('ro.product.model'),
        'is_emulator': properties.get('ro.kernel.qemu') == '1'
                       or 'emulator' in properties.get('ro.build.characteristics', '').split(','),
        'locale': properties.get('persist.sys.locale') or properties.get('ro.product.locale'),
        'font_scale': adb_text(serial, 'shell', 'settings', 'get', 'system', 'font_scale',
                               binary=binary) or None,
        'night_mode': adb_text(serial, 'shell', 'cmd', 'uimode', 'night', binary=binary) or None,
    }
    return env


def package_build_hash(serial, package, binary, workdir):
    """Hash installed APKs, including splits; this excludes hot-loaded code."""
    if not re.fullmatch(r'[A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)+', package):
        raise LedgerError('invalid Android package id')
    paths = adb_text(serial, 'shell', 'pm', 'path', package, binary=binary)
    entries = [line[8:].strip() for line in paths.splitlines() if line.startswith('package:')]
    if not entries:
        raise LedgerError(f'package {package} is not installed on {serial}')
    if any(not re.fullmatch(r'/[A-Za-z0-9_./+=@~-]+', p) for p in entries):
        raise LedgerError('unexpected installed APK path')
    # Hash on-device in one call. Pull only if sha256sum is unavailable.
    output = adb_text(serial, 'shell', 'sha256sum', *entries, binary=binary)
    hashes = {}
    for line in output.splitlines():
        parts = line.split(maxsplit=1)
        if len(parts) == 2 and re.fullmatch(r'[0-9a-fA-F]{64}', parts[0]):
            hashes[parts[1].lstrip('*')] = parts[0].lower()
    if any(p not in hashes for p in entries):
        with tempfile.TemporaryDirectory(prefix='ditto-apk-') as temporary:
            for index, remote in enumerate(entries):
                local = Path(temporary) / f'{index}.apk'
                adb(serial, 'pull', remote, str(local), binary=binary, timeout=300)
                hashes[remote] = sha256_file(local)
    installed = sorted([{'name': Path(p).name, 'sha256': hashes[p]} for p in entries],
                       key=lambda item: item['name'])
    digest = installed[0]['sha256'] if len(installed) == 1 else hashlib.sha256(
        json.dumps(installed, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    version = adb_text(serial, 'shell', 'dumpsys', 'package', package, binary=binary)
    version_name = re.search(r'versionName=(\S+)', version)
    version_code = re.search(r'versionCode=(\d+)', version)
    return digest, {
        'package': package,
        'version_name': version_name.group(1) if version_name else None,
        'version_code': version_code.group(1) if version_code else None,
        'split_count': len(entries),
        'installed_apks': installed,
        'hash_method': 'apk-sha256' if len(installed) == 1 else 'apk-set-sha256-v1',
    }


def grab_screenshot(serial, destination, binary):
    """exec-out first; fall back to shell+pull when a device mangles the stream."""
    proc = adb(serial, 'exec-out', 'screencap', '-p', binary=binary, check=False, timeout=120)
    if proc.returncode == 0 and proc.stdout[:8] == pngtool.PNG_MAGIC:
        Path(destination).write_bytes(proc.stdout)
        try:
            pngtool.read_header(destination)
            return 'exec-out'
        except pngtool.PngError:
            pass
    remote = '/sdcard/ditto-capture.png'
    adb(serial, 'shell', 'screencap', '-p', remote, binary=binary, timeout=120)
    adb(serial, 'pull', remote, str(destination), binary=binary, timeout=120)
    adb(serial, 'shell', 'rm', '-f', remote, binary=binary, check=False)
    pngtool.read_header(destination)
    return 'shell+pull'


def grab_hierarchy(serial, destination, binary):
    remote = '/sdcard/ditto-hierarchy.xml'
    proc = adb(serial, 'shell', 'uiautomator', 'dump', remote,
               binary=binary, check=False, timeout=90)
    if proc.returncode != 0:
        return None, (proc.stderr or proc.stdout).decode('utf-8', 'replace').strip()[:200]
    pull = adb(serial, 'pull', remote, str(destination), binary=binary, check=False, timeout=90)
    adb(serial, 'shell', 'rm', '-f', remote, binary=binary, check=False)
    if pull.returncode != 0 or not Path(destination).is_file():
        return None, 'hierarchy dump could not be pulled'
    text = Path(destination).read_text(encoding='utf-8', errors='replace')
    if '<node' not in text:
        return destination, 'hierarchy contains no nodes; custom-rendered UI is expected to be sparse'
    return destination, None


# --------------------------------------------------------------------------
# record writing
# --------------------------------------------------------------------------

def add_records(index_path, new_records, force=False):
    data = load_json(index_path, {'schema_version': 1, 'records': []})
    data.setdefault('schema_version', 1)
    records = data.setdefault('records', [])
    if not isinstance(records, list):
        raise LedgerError(f'{index_path}: "records" must be a list')
    by_id = {r.get('id'): i for i, r in enumerate(records) if isinstance(r, dict)}
    added, replaced = [], []
    for record in new_records:
        if record['id'] in by_id:
            if not force:
                raise LedgerError(
                    f"evidence id '{record['id']}' already exists. "
                    f'Use a different --label, or pass --force to replace it.')
            records[by_id[record['id']]] = record
            replaced.append(record['id'])
        else:
            records.append(record)
            added.append(record['id'])
    save_json(index_path, data)
    return added, replaced


def upsert_case(coverage_path, case_id, updates, defaults=None):
    data = load_json(coverage_path, {'schema_version': 1, 'cases': []})
    data.setdefault('schema_version', 1)
    cases = data.setdefault('cases', [])
    if not isinstance(cases, list):
        raise LedgerError(f'{coverage_path}: "cases" must be a list')
    for case in cases:
        if isinstance(case, dict) and case.get('id') == case_id:
            case.update(updates)
            save_json(coverage_path, data)
            return case, False
    case = {'id': case_id, 'required': True, 'critical': False,
            'observed': False, 'implemented': False, 'validation': 'not_run',
            'user_testing': 'pending', 'evidence_ids': [], 'blocker': None,
            **(defaults or {}), **updates}
    cases.append(case)
    save_json(coverage_path, data)
    return case, True


# --------------------------------------------------------------------------
# subcommands
# --------------------------------------------------------------------------

def cmd_init(args):
    root = Path(args.project).resolve()
    index = root / 'evidence' / 'index.json'
    coverage = root / 'spec' / 'coverage.json'
    for path, payload in ((index, {'schema_version': 1, 'records': []}),
                          (coverage, {'schema_version': 1, 'cases': []})):
        if path.exists():
            print(f'kept existing {relative_to(root, path)}')
            continue
        save_json(path, payload)
        print(f'created {relative_to(root, path)}')
    (root / 'evidence' / 'runtime').mkdir(parents=True, exist_ok=True)
    (root / 'evidence' / 'static').mkdir(parents=True, exist_ok=True)
    print('An empty ledger is an initial state, never a completion claim.')
    return 0


def cmd_capture(args):
    root = Path(args.project).resolve()
    runtime = runtime_identity(args, root)
    binary = adb_binary()
    serial = args.serial or os.environ.get('DITTO_SERIAL')
    if not serial:
        attached = [line.split()[0] for line in
                    adb_text('', 'devices', binary=binary).splitlines()[1:] if '\tdevice' in line]
        raise LedgerError('--serial is required. Attached: '
                          + (', '.join(attached) if attached else 'none'))

    flow = check_id(args.flow, '--flow')
    state = check_id(args.state, '--state')
    role = args.role
    label = check_id(args.label or f'{flow}.{state}.{role}', '--label')
    case_id = check_id(args.case_id or f'{flow}.{state}.android', '--case-id')
    index_path = root / 'evidence' / 'index.json'
    index = load_json(index_path, {'records': []})
    if any(r.get('id') in (f'ev-{label}-screen', f'ev-{label}-hierarchy')
           for r in index.get('records', [])):
        raise LedgerError('capture evidence is immutable; choose a new --label')
    if args.link_case:
        coverage = load_json(root / 'spec' / 'coverage.json', {'cases': []})
        for case in coverage.get('cases', []):
            if case.get('id') == case_id and any(case.get(k) != v for k, v in
                    {'flow_id': flow, 'state_id': state, 'platform': 'android'}.items()):
                raise LedgerError('case id already belongs to another flow/state/platform')

    out_dir = root / 'evidence' / 'runtime' / flow / state / role / label
    if out_dir.exists():
        raise LedgerError('capture destination exists; choose a new --label')

    env = device_environment(serial, binary)
    app_sha, app_meta = package_build_hash(serial, args.package, binary, root / '.ditto-tmp')
    shot = out_dir / 'screen.png'
    hierarchy, hierarchy_note = (None, 'skipped')
    out_dir.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.capture-', dir=out_dir.parent) as temporary:
        staging = Path(temporary)
        method = grab_screenshot(serial, staging / 'screen.png', binary)
        width, height = pngtool.read_header(staging / 'screen.png')
        if not args.no_hierarchy:
            staged_hierarchy, hierarchy_note = grab_hierarchy(
                serial, staging / 'hierarchy.xml', binary)
            if staged_hierarchy:
                hierarchy = out_dir / 'hierarchy.xml'
            else:
                (staging / 'hierarchy.xml').unlink(missing_ok=True)
        staging.rename(out_dir)
    version = adb_text('', 'version', binary=binary)

    common = {
        'role': role, 'runtime': True, 'app_sha256': app_sha,
        'runtime_identity': runtime,
        'platform': 'android', 'flow_id': flow, 'state_id': state,
        'fixture_id': args.fixture,
        'app': app_meta,
        'environment': {**env, 'capture_px': f'{width}x{height}'},
        'capture': {'tool': 'adb', 'method': method,
                    'version': version.splitlines()[0] if version else 'unknown',
                    'captured_at': time.strftime('%Y-%m-%dT%H:%M:%S%z')},
        'setup': args.setup,
        'actions': args.action or [],
        'limitations': [],
    }
    if env['is_emulator']:
        common['limitations'].append(
            'Captured on an emulator. This is not physical-device evidence for '
            'OEM insets, keyboard, notifications or performance.')

    records = [{'id': f'ev-{label}-screen', 'kind': 'screenshot',
                'path': relative_to(root, shot), 'sha256': sha256_file(shot),
                'viewport_px': f'{width}x{height}', **common}]
    if hierarchy:
        records.append({'id': f'ev-{label}-hierarchy', 'kind': 'hierarchy',
                        'path': relative_to(root, hierarchy),
                        'sha256': sha256_file(hierarchy), **common})
    if hierarchy_note:
        records[-1].setdefault('limitations', []).append(hierarchy_note)

    try:
        added, replaced = add_records(index_path, records)
    except Exception:
        shutil.rmtree(out_dir)
        raise

    if args.link_case:
        case, created = upsert_case(
            root / 'spec' / 'coverage.json', case_id,
            {'validation': 'not_run', 'user_testing': 'pending',
             **({'observed': True} if role == 'original' else {})},
            defaults={'flow_id': flow, 'platform': 'android', 'state_id': state,
                      'required_dimensions': list(args.dimensions or ['visual', 'behavior'])})
        ids = case.setdefault('evidence_ids', [])
        for record in records:
            if record['id'] not in ids:
                ids.append(record['id'])
        case[f'{role}_app_sha256'] = app_sha
        case[f'{role}_runtime_sha256'] = runtime_digest(records[0])
        upsert_case(root / 'spec' / 'coverage.json', case_id, case)
        print(f'case {case_id} {"created" if created else "updated"}')

    print(f'recorded {", ".join(added + replaced)}')
    print(f'  {relative_to(root, out_dir)}  {width}x{height} @ {env["density_dpi"]}dpi '
          f'(dpr {env["device_pixel_ratio"]})  build {app_sha[:12]}')
    if hierarchy_note and hierarchy_note != 'skipped':
        print(f'  note: {hierarchy_note}')
    return 0


def cmd_adopt(args):
    """Register existing files as evidence. Use for iOS, manual and historical captures."""
    root = Path(args.project).resolve()
    runtime = runtime_identity(args, root)
    app_sha = sha256_file(args.app_artifact) if args.app_artifact else args.app_sha256
    if not re.fullmatch(r'[0-9a-fA-F]{64}', app_sha or ''):
        raise LedgerError('adoption requires a valid build SHA-256 or --app-artifact')
    environment = None
    if args.environment:
        environment = load_json(args.environment, {})
        if not environment:
            raise LedgerError('--environment must contain captured device facts')
    flow = check_id(args.flow, '--flow')
    state = check_id(args.state, '--state')
    label = check_id(args.label or f'{flow}.{state}.{args.role}', '--label')
    records = []
    for index, raw in enumerate(args.file):
        path = Path(raw).resolve(strict=True)
        kind = args.kind or ('screenshot' if path.suffix.lower() == '.png' else 'artifact')
        record = {
            'id': f'ev-{label}-{index}' if len(args.file) > 1 else f'ev-{label}',
            'kind': kind,
            'role': args.role,
            'runtime': not args.static,
            'runtime_identity': runtime,
            'path': relative_to(root, path),
            'sha256': sha256_file(path),
            'app_sha256': app_sha,
            'platform': args.platform,
            'flow_id': flow,
            'state_id': state,
            'fixture_id': args.fixture,
            'capture': {'tool': args.tool, 'version': args.tool_version,
                        'captured_at': args.captured_at},
            'setup': args.setup,
            'actions': args.action or [],
            'limitations': list(args.limitation or []),
        }
        if environment is not None:
            record['environment'] = environment
        if args.static:
            record['limitations'].append(
                'UNVERIFIED_STATIC_ONLY: no runtime execution backs this record.')
        if kind == 'screenshot':
            try:
                width, height = pngtool.read_header(path)
                record['viewport_px'] = f'{width}x{height}'
            except pngtool.PngError:
                record['limitations'].append('screenshot dimensions could not be read')
        records.append(record)
    added, replaced = add_records(root / 'evidence' / 'index.json', records, force=args.force)
    print(f'recorded {", ".join(added + replaced)}')
    return 0


def cmd_comparison(args):
    """Write the comparison record and set the case result. Verdicts are yours."""
    root = Path(args.project).resolve()
    check_id(args.case_id, '--case-id')
    index = load_json(root / 'evidence' / 'index.json', {'records': []})
    known = {r.get('id'): r for r in index.get('records', []) if isinstance(r, dict)}

    missing = [e for e in args.original_evidence + args.candidate_evidence if e not in known]
    if missing:
        raise LedgerError(f'unknown evidence id(s): {", ".join(missing)}. Capture or adopt first.')

    dimensions = {}
    for item in args.dimension:
        name, _, verdict = item.partition('=')
        if not verdict:
            raise LedgerError(f"--dimension expects name=verdict, got {item!r}")
        if name not in DIMENSIONS:
            raise LedgerError(f'unknown dimension {name!r}; expected one of {", ".join(DIMENSIONS)}')
        if verdict not in RESULTS:
            raise LedgerError(f'dimension verdict must be one of {", ".join(RESULTS)}')
        dimensions[name] = verdict
    if not dimensions:
        raise LedgerError('at least one --dimension name=verdict is required')

    reasons = {}
    for pair in args.dimension_reason or []:
        name, separator, reason = pair.partition('=')
        if not separator or name not in dimensions or not reason.strip():
            raise LedgerError('--dimension-reason requires a supplied dimension and nonempty reason')
        reasons[name] = reason
    for name, verdict in dimensions.items():
        if verdict == 'not_applicable' and name not in reasons:
            raise LedgerError(f'{name}: not_applicable requires --dimension-reason')
    coverage = load_json(root / 'spec' / 'coverage.json', {'cases': []})
    existing = next((c for c in coverage.get('cases', []) if c.get('id') == args.case_id), {})
    required = existing.get('required_dimensions',
                            [d for d, v in dimensions.items() if v != 'not_applicable'])
    if not required:
        raise LedgerError('comparison requires at least one applicable dimension')
    if any(d not in dimensions or dimensions[d] == 'not_applicable' for d in required):
        raise LedgerError('comparison must cover every predeclared required dimension')
    original = known[args.original_evidence[0]]
    candidate = known[args.candidate_evidence[0]]
    fixture = args.fixture or original.get('fixture_id')
    expected = {k: original.get(k) for k in ('flow_id', 'state_id', 'platform')}
    if existing and any(existing.get(k) != v for k, v in expected.items()):
        raise LedgerError('comparison evidence does not match the existing case')
    for role, ids, first in (('original', args.original_evidence, original),
                              ('candidate', args.candidate_evidence, candidate)):
        for eid in ids:
            item = known[eid]
            if (item.get('role') != role or item.get('runtime') is not True
                    or any(item.get(k) != v for k, v in expected.items())
                    or item.get('fixture_id') != fixture
                    or item.get('app_sha256') != first.get('app_sha256')
                    or runtime_digest(item) != runtime_digest(first)):
                raise LedgerError(f'{eid}: incompatible role, checkpoint, fixture or build')
        if existing and (existing.get(f'{role}_app_sha256') not in (None, first.get('app_sha256'))
                         or existing.get(f'{role}_runtime_sha256') not in (None, runtime_digest(first))):
            raise LedgerError(f'{role}: evidence is stale relative to the case; capture/link current evidence')
    blocking = [d for d, v in dimensions.items() if v not in ('pass', 'not_applicable')]
    result = args.result or ('pass' if not blocking else 'fail')
    if result == 'pass' and blocking:
        raise LedgerError(f'cannot record pass: {", ".join(blocking)} did not pass')

    record = {
        'schema_version': 1,
        'case_id': args.case_id,
        'result': result,
        'original_evidence_ids': args.original_evidence,
        'candidate_evidence_ids': args.candidate_evidence,
        'fixture_id': args.fixture or known[args.original_evidence[0]].get('fixture_id'),
        'method': args.method,
        'steps': args.step,
        'dimensions': dimensions,
        'dimension_reasons': reasons,
        'supporting_artifacts': [relative_to(root, Path(p).resolve(strict=True))
                                 for p in args.supporting or []],
        'discrepancies': args.discrepancy or [],
        'recorded_at': time.strftime('%Y-%m-%dT%H:%M:%S%z'),
    }
    if not record['fixture_id']:
        raise LedgerError('--fixture is required when the evidence record carries no fixture_id')
    if not record['steps']:
        raise LedgerError('at least one --step is required; a verdict without replay steps '
                          'cannot be reproduced')

    destination = Path(args.output) if args.output else (
        root / 'validation' / args.case_id / 'comparison.json')
    relative_to(root, destination)
    if destination.exists() and not args.force:
        raise LedgerError(f'{destination} exists; pass --force to replace it')
    save_json(destination, record)

    updates = {
        'validation': result,
        'comparison': relative_to(root, destination),
        'required_dimensions': required,
        'implemented': True,
        'observed': True,
        'original_app_sha256': original.get('app_sha256'),
        'candidate_app_sha256': candidate.get('app_sha256'),
        'original_runtime_sha256': runtime_digest(original),
        'candidate_runtime_sha256': runtime_digest(candidate),
        'user_testing': 'pending',
        'blocker': None,
    }
    if result != 'pass':
        updates['blocker'] = args.blocker or (
            f'dimensions not passing: {", ".join(blocking)}' if blocking else 'see comparison record')
    case, created = upsert_case(
        root / 'spec' / 'coverage.json', args.case_id, updates,
        defaults={'flow_id': original.get('flow_id'), 'platform': original.get('platform'),
                  'state_id': original.get('state_id')})
    ids = case.setdefault('evidence_ids', [])
    for eid in args.original_evidence + args.candidate_evidence:
        if eid not in ids:
            ids.append(eid)
    upsert_case(root / 'spec' / 'coverage.json', args.case_id, case)

    print(f'comparison {result.upper()} -> {relative_to(root, destination)}')
    print(f'case {args.case_id} {"created" if created else "updated"}')
    print('Run validate_spec.py --check-files before claiming the checkpoint.')
    return 0 if result == 'pass' else 1


# --------------------------------------------------------------------------

def build_parser():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--project', type=Path, default=Path('.'),
                        help='reconstruction project root (default: .)')
    sub = parser.add_subparsers(dest='command', required=True)

    sub.add_parser('init', help='create an empty ledger').set_defaults(func=cmd_init)

    cap = sub.add_parser('capture', help='pull a checkpoint from a connected Android device')
    cap.add_argument('--serial', help='adb serial; required unless DITTO_SERIAL is set')
    cap.add_argument('--package', required=True, help='package id of the app being captured')
    cap.add_argument('--role', required=True, choices=('original', 'candidate'))
    cap.add_argument('--flow', required=True)
    cap.add_argument('--state', required=True)
    cap.add_argument('--fixture', required=True,
                     help='fixture/account state id; both runs must share it')
    cap.add_argument('--label', help='evidence id stem (default <flow>.<state>.<role>)')
    cap.add_argument('--setup', default=None, help='how this state was reached')
    cap.add_argument('--action', action='append', help='action taken, repeatable')
    cap.add_argument('--no-hierarchy', action='store_true')
    cap.add_argument('--link-case', action='store_true',
                     help='also create/update the coverage case')
    cap.add_argument('--case-id', default=None)
    cap.add_argument('--dimensions', nargs='*', choices=DIMENSIONS)
    cap.set_defaults(func=cmd_capture)

    adopt = sub.add_parser('adopt', help='register files captured outside this tool')
    adopt.add_argument('file', nargs='+', type=Path)
    adopt.add_argument('--role', required=True, choices=('original', 'candidate'))
    adopt.add_argument('--flow', required=True)
    adopt.add_argument('--state', required=True)
    adopt.add_argument('--platform', required=True, choices=('android', 'ios'))
    app_identity = adopt.add_mutually_exclusive_group(required=True)
    app_identity.add_argument('--app-sha256',
                       help='sha256 of the build this came from; never reuse the other build\'s hash')
    app_identity.add_argument('--app-artifact', type=Path,
                              help='hash the exact build artifact used for this capture')
    adopt.add_argument('--fixture', required=True)
    adopt.add_argument('--kind', default=None)
    adopt.add_argument('--label', default=None)
    adopt.add_argument('--tool', default='manual')
    adopt.add_argument('--tool-version', default='unknown')
    adopt.add_argument('--captured-at', default=None)
    adopt.add_argument('--setup', default=None)
    adopt.add_argument('--action', action='append')
    adopt.add_argument('--environment', type=Path, help='JSON object of captured device facts')
    adopt.add_argument('--static', action='store_true',
                       help='not a runtime observation; marks UNVERIFIED_STATIC_ONLY')
    adopt.add_argument('--limitation', action='append')
    adopt.add_argument('--force', action='store_true')
    adopt.set_defaults(func=cmd_adopt)

    for capture_parser in (cap, adopt):
        capture_parser.add_argument('--runtime-mode', choices=('installed', 'hot-reload', 'instrumented'),
                                    default='installed')
        capture_parser.add_argument('--runtime-source', type=Path, nargs='+',
                                    help='all source/patch inputs loaded into a modified runtime')
        capture_parser.add_argument('--runtime-session', help='identifier for the attached runtime session')

    comp = sub.add_parser('comparison', help='record a paired comparison result')
    comp.add_argument('--case-id', required=True)
    comp.add_argument('--original-evidence', nargs='+', required=True)
    comp.add_argument('--candidate-evidence', nargs='+', required=True)
    comp.add_argument('--dimension', action='append', required=True, metavar='NAME=VERDICT',
                      help=f'repeatable; NAME in {{{",".join(DIMENSIONS)}}}, '
                           f'VERDICT in {{{",".join(RESULTS)}}}')
    comp.add_argument('--dimension-reason', action='append', metavar='NAME=TEXT',
                      help='required justification for a not_applicable dimension')
    comp.add_argument('--step', action='append', required=True,
                      help='replay step, repeatable and ordered')
    comp.add_argument('--method', required=True, help='how the two runs were compared')
    comp.add_argument('--fixture', default=None)
    comp.add_argument('--supporting', action='append',
                      help='supporting artifact, e.g. validation/<flow>/android/result.json')
    comp.add_argument('--discrepancy', action='append')
    comp.add_argument('--result', choices=RESULTS, default=None)
    comp.add_argument('--blocker', default=None)
    comp.add_argument('--output', type=Path, default=None)
    comp.add_argument('--force', action='store_true')
    comp.set_defaults(func=cmd_comparison)
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except LedgerError as error:
        print(f'ledger: {error}', file=sys.stderr)
        return 2
    except (OSError, ValueError, pngtool.PngError) as error:
        print(f'ledger: {error}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
