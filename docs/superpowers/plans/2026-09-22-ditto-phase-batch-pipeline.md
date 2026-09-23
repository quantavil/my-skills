# Ditto Phase-Batch Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan.

**Goal:** Replace Ditto's legacy ledger workflow with a phase-based, still-image parity pipeline that indexes reverse-engineered package evidence, collects original and clone packs, creates `Original APK | Clone APK | Diff` triptychs, selectively invalidates affected checkpoints, and requests human review only after automated readiness.

**Architecture:** `ditto.py` becomes a thin nested CLI over focused modules for immutable storage, compulsory capability preflight, package analysis, pack collection, and phase comparison/state transitions. A phase cannot leave `preflight` until exact skill hashes and successful JADX, Apktool, FlutterDec, r2Flutter, and mobile-control MCP probes are recorded. A phase contract defines every checkpoint and dependency; immutable manifests bind MCP-produced evidence to package hashes and controller sessions; `status.json` holds current pointers and verdicts. Batch comparison produces metrics and triptychs, while explicit verdict, readiness, and review commands keep AI judgment and human acceptance distinct.

**Tech Stack:** Python 3 standard library, existing `pngtool.py`, `unittest`, ZIP/APK/IPA/AAB inspection, mandatory JADX/Apktool/FlutterDec/r2Flutter MCP exports, and mandatory mobile-control MCP capture.

**Spec:** [2026-09-22-ditto-phase-batch-pipeline-design.md](../specs/2026-09-22-ditto-phase-batch-pipeline-design.md)

**Global Constraints:**

- This is a clean replacement. Delete legacy ledger, coverage, graph, validator, migration, alias, and dual-reader behavior.
- Require the Ditto, Flutter-Dart, and verification-before-completion skills. Record each resolved `SKILL.md` path and SHA-256 in immutable preflight evidence.
- Require healthy JADX, Apktool, FlutterDec, r2Flutter, and mobile-control MCP sessions for Android Flutter phases. Reject direct CLI reverse-engineering, direct ADB, Maestro, manual capture, and personal-device interaction as substitutes.
- A configured MCP is insufficient. Its bounded probe must succeed, reverse MCPs must identify the original package hash, Flutter analyzers must support its ABI/Dart profile, and the controller must identify and operate the intended emulator.
- Capture and compare PNG screenshots and optional hierarchy XML only. Do not add video inputs, outputs, dependencies, or verdicts.
- Keep `phase.NNN.json`, versioned manifests, evidence files, retained packages, and reverse-engineering indexes immutable. Only `status.json`, `notes.md`, the active phase overview, and the active report are mutable.
- Use the three top-level evidence roles `original/`, `clone/`, and `diff/`. A package-analysis tree may live below `original/reverse.NNN/`; checkpoint artifacts remain flat and mirrored.
- Never resize parity screenshots. Missing XML must produce `layout_comparison_status: "not_run"`, never a zero-delta success.
- Pixel ratio is diagnostic. Only `phase verdict` records semantic acceptance, and every verdict must cite evidence and a rationale appropriate to its dimension.
- `phase review` records a real user decision after `automated_ready`; it must never infer acceptance.
- All project-relative paths must remain below the project root. All writes use a lock plus same-directory atomic replacement. Failed collection or comparison must not leave a current manifest/report pointer.
- Keep the runtime portable across Linux and Windows. Use exclusive lock files rather than `fcntl`.

**Review Focus:**

- A command must never report readiness from missing, stale, mismatched, or unsupported evidence.
- Package extraction must reject traversal, links, duplicates, encrypted entries, oversized selections, and executable use.
- Immutable files must never be overwritten, including during retries and concurrent runs.
- Selective invalidation must fail closed: an unknown changed path invalidates the whole phase.
- The final documentation must describe the phase pipeline directly and contain no journey-loop, mid-phase human checkpoint, video, or legacy-ledger instructions.

## File Structure

### Create

- `skills/ditto/scripts/phase_store.py` — IDs, paths, hashes, locking, atomic JSON, immutable writes, schema/state validation, revision selection.
- `skills/ditto/scripts/phase_preflight.py` — required skill hashing, MCP receipt validation, target/capability agreement, blocked-state reporting.
- `skills/ditto/scripts/phase_package.py` — package inventory, safe phase-filtered extraction, verified MCP-export import, reverse index generation.
- `skills/ditto/scripts/phase_capture.py` — original/clone MCP-export validation, canonical naming, manifest creation, freeze rules.
- `skills/ditto/scripts/phase_compare.py` — batch screenshot/XML comparison, report generation, semantic verdicts, dependency invalidation, readiness and review transitions.
- `skills/ditto/scripts/test_phase_store.py` — schema, path, lock, immutability, and atomic-write tests.
- `skills/ditto/scripts/test_phase_preflight.py` — mandatory skill/MCP capability and no-fallback tests.
- `skills/ditto/scripts/test_phase_package.py` — safe inventory/extraction and provenance tests.
- `skills/ditto/scripts/test_phase_workflow.py` — CLI and end-to-end phase state tests.

### Modify

- `skills/ditto/scripts/ditto.py` — replace `check/report/graph` with the `phase` command tree.
- `skills/ditto/scripts/diff_screenshots.py` — always support a labeled full-resolution triptych and explicit layout status.
- `skills/ditto/scripts/test_ditto.py` — retain PNG, inventory, diff, theme, and emulator tests; remove legacy ledger/validator cases and add triptych/layout regressions.
- `skills/ditto/SKILL.md` — concise package-first phase workflow and final human-review rule.
- `skills/ditto/references/contracts.md` — phase contract, manifest, status, naming, verdict, and evidence schemas.
- `skills/ditto/references/reverse-engineering.md` — make package indexing standard and connect findings to phase checkpoints.
- `skills/ditto/references/parity.md` — batch still-image comparison and semantic threshold guidance.
- `skills/ditto/references/runtime-workflow.md` — mobile-control MCP capture, one device owner, and selective recapture.
- `skills/ditto/references/toolchain.md` and `skills/ditto/references/extraction.md` — point tool use at `reverse.NNN.json` and remove ledger examples.
- `skills/ditto/agents/openai.yaml` — update the skill prompt for phase-based reconstruction.

### Delete

- `skills/ditto/scripts/ledger.py` — replaced evidence writer.
- `skills/ditto/scripts/validate_spec.py` — replaced by phase schema/readiness validation.
- `skills/ditto/scripts/test_workflow.py` — legacy command/graph tests replaced by `test_phase_workflow.py`.

Retain `inventory.py`, `pngtool.py`, `theme_extract.py`, `emulator_manager.py`, its shell wrapper, and emulator tests.

## Task 1: Build the immutable phase store and schema validator

**Files:**

- Create: `skills/ditto/scripts/phase_store.py`
- Create: `skills/ditto/scripts/test_phase_store.py`

**Step 1: Write failing schema and storage tests**

Add tests that call these public interfaces:

```python
class PhaseError(RuntimeError): ...

def validate_contract(data: object, expected_phase_id: str | None = None) -> dict: ...
def validate_status(data: object, contract: dict) -> dict: ...
def load_json(path: Path) -> dict: ...
def atomic_write_json(path: Path, data: dict) -> None: ...
def write_immutable_json(path: Path, data: dict) -> None: ...
def sha256_file(path: Path) -> str: ...
def safe_child(root: Path, value: str | Path) -> Path: ...
def checkpoint_stem(checkpoint: dict, revision: int) -> str: ...
def versioned_path(directory: Path, stem: str, revision: int, suffix: str) -> Path: ...
@contextmanager
def phase_lock(phase_dir: Path): ...
```

The fixture contract uses schema version 1 and includes `phase_id`, `revision`, `scope`, `platform`, `fixtures`, `checkpoints`, `reverse_engineering`, `dependency_graph`, `ownership`, and `authorized_differences`. Test duplicate checkpoint numbers/IDs, unsupported artifact kinds, unsafe IDs, absent required dimensions, unknown dependencies, malformed path rules, status pointers to nonexistent checkpoint IDs, traversal, immutable overwrite, and competing lock acquisition.

**Step 2: Run the tests and confirm failure**

Run: `python3 -m unittest skills/ditto/scripts/test_phase_store.py -v`

Expected: import failure because `phase_store.py` does not exist.

**Step 3: Implement the store and validators**

Use lowercase `[a-z0-9][a-z0-9_]*` IDs, three-digit positive checkpoint numbers, artifact kinds `png`, `xml`, `trace`, `state`, `network`, and `semantics`, and dimensions `visual`, `layout`, `behavior`, `navigation`, `persistence`, `platform`, `network`, and `accessibility`. Reject `video`, `mp4`, and arbitrary extensions.

Implement `phase_lock()` using `os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)`. Store PID and timestamp for diagnostics, remove the lock in `finally`, and report an existing lock without silently breaking it. Implement JSON writes through `NamedTemporaryFile` in the destination directory, `flush()`, `os.fsync()`, and `os.replace()`.

**Step 4: Run the focused tests**

Run: `python3 -m unittest skills/ditto/scripts/test_phase_store.py -v`

Expected: all tests pass.

**Step 5: Commit**

```bash
git add skills/ditto/scripts/phase_store.py skills/ditto/scripts/test_phase_store.py
git commit -m "feat(ditto): add immutable phase store"
```

## Task 2: Replace the CLI and enforce compulsory skill/MCP preflight

**Files:**

- Modify: `skills/ditto/scripts/ditto.py`
- Create: `skills/ditto/scripts/phase_capture.py`
- Create: `skills/ditto/scripts/phase_preflight.py`
- Create: `skills/ditto/scripts/test_phase_workflow.py`
- Create: `skills/ditto/scripts/test_phase_preflight.py`
- Modify: `skills/ditto/scripts/test_ditto.py`
- Delete: `skills/ditto/scripts/ledger.py`
- Delete: `skills/ditto/scripts/validate_spec.py`
- Delete: `skills/ditto/scripts/test_workflow.py`

**Step 1: Write failing CLI tests**

Test:

- `ditto.main(['phase', 'init', 'daily_logging', '--project', root])` creates `phases/daily_logging/phase.001.json`, `status.json`, `notes.md`, and the three role directories.
- The generated contract is valid but cannot freeze until the user fills its required scope and checkpoint list.
- Initial state is `preflight`; original collection is rejected before a valid active preflight exists.
- Repeating `init` refuses to overwrite the phase.
- Removed commands `check`, `graph`, and top-level `report` fail argument parsing.
- `phase report` emits JSON with current revisions, state, checkpoint counts, invalidations, and human-review status.
- The retained test suite contains no imports or cases for the removed ledger and validator.

Test this public interface:

```python
REQUIRED_SKILLS = ('ditto', 'flutter-dart', 'verification-before-completion')
REQUIRED_ANDROID_FLUTTER_MCPS = (
    'jadx', 'apktool', 'flutterdec', 'r2flutter', 'mobile-control'
)

def record_preflight(
    project: Path,
    phase_id: str,
    package: Path,
    skill_paths: dict[str, Path],
    mcp_receipts: list[Path],
) -> dict: ...
```

Each MCP receipt must contain schema version, server and tool identity, capability, tool version, session ID, observed time, bounded probe request/response hashes, status, limitations, and target identity. JADX, Apktool, FlutterDec, and r2Flutter receipts must agree with the locally computed package SHA-256. FlutterDec and r2Flutter must report supported ABI and Dart profile. The mobile-control receipt must report the emulator or contract-authorized test-device identity, environment facts, successful launch/tap/type/swipe/back/screenshot/hierarchy capability probes, and the disposable screenshot hash.

Test missing skills, changed skill bytes, missing MCPs, duplicate capability claims, wrong APK hash, unsupported Flutter ABI/profile, disconnected controller, target identity that differs from the phase contract, partial controller capabilities, stale receipt, and unknown receipt schema. Every failure records `blocked` with exact reasons and cannot advance to collection. Test that CLI/ADB/Maestro/manual provenance is rejected even when artifact files exist.

**Step 2: Run the tests and confirm failure**

Run: `python3 -m unittest skills/ditto/scripts/test_phase_preflight.py skills/ditto/scripts/test_phase_workflow.py -v`

Expected: failures because the nested CLI and phase initializer are absent.

**Step 3: Implement the nested parser and initializer**

Expose:

```python
def build_parser() -> argparse.ArgumentParser: ...
def main(argv: list[str] | None = None) -> int: ...

def init_phase(project: Path, phase_id: str) -> Path: ...
def phase_report(project: Path, phase_id: str) -> dict: ...
```

`phase.001.json` must contain concrete empty collections and schema fields with no unfinished marker values. `status.json` starts in `preflight` with phase revision 1, null preflight/manifest pointers, empty checkpoint status, empty invalidation history, and `human_review.status = "pending"`.

`phase preflight <id> --package <path> --skill <name>=<SKILL.md>... --receipt <json>...` validates all requirements, writes immutable `preflight.NNN.json`, points `status.json` at it, and moves to `collecting_original`. The CLI computes skill and package hashes itself; receipts cannot supply those values as trusted input. A later operation rehashes skills and validates MCP session/target continuity. A changed skill or expired/replaced MCP session moves the phase back to `blocked` until preflight is rerun.

Delete the legacy writer, validator, and graph tests in this same change. Remove their imports and their dedicated test classes from `test_ditto.py`, while retaining its PNG, inventory, diff, theme, and emulator coverage. This keeps every intermediate commit testable without a temporary compatibility CLI.

**Step 4: Run focused tests**

Run: `python3 -m unittest skills/ditto/scripts/test_phase_preflight.py skills/ditto/scripts/test_phase_workflow.py -v`

Expected: all tests pass.

**Step 5: Commit**

```bash
git add -A skills/ditto/scripts
git commit -m "feat(ditto): require skill and MCP preflight"
```

## Task 3: Make reverse engineering part of original collection

**Files:**

- Create: `skills/ditto/scripts/phase_package.py`
- Create: `skills/ditto/scripts/test_phase_package.py`
- Modify: `skills/ditto/scripts/inventory.py`

**Step 1: Write failing package-analysis tests**

Create small APK/IPA-shaped ZIP fixtures. Test these interfaces:

```python
def analyze_package(
    package: Path,
    destination: Path,
    include_globs: list[str],
    checkpoint_links: dict[str, list[str]],
    mcp_exports: dict[str, Path],
    preflight: dict,
) -> dict: ...

```

Verify package SHA-256, framework inventory, MCP server/tool/session identities, versions from preflight receipts, original archive paths, retained-file hashes, checkpoint links, limitations, and canonical `reverse.001.json`. Require exports from JADX, Apktool, FlutterDec, and r2Flutter, all bound to the same package hash. Verify selected resources are extracted under `original/reverse.001/` without flattening their package paths. Reject traversal, symlinks, duplicate members, encrypted selections, more than 512 MiB selected uncompressed data, and any output that already exists. Verify MCP exports are copied as inert files and never executed. Reject local CLI, unknown, or manually declared analysis provenance.

**Step 2: Run and confirm failure**

Run: `python3 -m unittest skills/ditto/scripts/test_phase_package.py -v`

Expected: import failure because `phase_package.py` is absent.

**Step 3: Implement bounded package analysis**

Reuse `inventory.inventory()` for a bounded local archive summary after compulsory MCP preflight; this summary supplements rather than replaces MCP analysis. Match contract `reverse_engineering.include_globs` with `PurePosixPath`/`fnmatch`, extract only regular selected members after the complete archive passes safety checks, and hash every retained file. Import only exports whose embedded MCP receipt matches the active preflight, package hash, server, tool, and session. Do not discover or invoke JADX, Apktool, FlutterDec, r2Flutter, ADB, or Maestro executables directly.

**Step 4: Run focused tests**

Run: `python3 -m unittest skills/ditto/scripts/test_phase_package.py -v`

Expected: all tests pass.

**Step 5: Commit**

```bash
git add skills/ditto/scripts/phase_package.py skills/ditto/scripts/test_phase_package.py skills/ditto/scripts/inventory.py
git commit -m "feat(ditto): index package evidence during oracle collection"
```

## Task 4: Collect, name, and freeze the complete original pack

**Files:**

- Modify: `skills/ditto/scripts/phase_capture.py`
- Modify: `skills/ditto/scripts/phase_store.py`
- Modify: `skills/ditto/scripts/phase_package.py`
- Modify: `skills/ditto/scripts/ditto.py`
- Modify: `skills/ditto/scripts/test_phase_workflow.py`

**Step 1: Write failing original-pack tests**

The mobile-control MCP export convention is `<order>_<checkpoint-id>.<kind>`, such as `001_log_top.png` and `001_log_top.xml`, accompanied by an immutable controller session receipt. Test that collection:

- Requires exactly the artifact kinds declared by every checkpoint.
- Rejects missing, duplicate, renamed, unexpected, or symlinked staged files.
- Rejects artifacts whose provenance is manual, direct ADB, Maestro, a different controller session, a device identity outside the phase contract, or an MCP session absent from active preflight.
- Writes canonical immutable names such as `001_log_top.r001.png`.
- Copies the retained package as `app.<first-eight-sha256>.apk`, `.ipa`, or `.aab`.
- Writes `original/manifest.001.json` with full hashes, package/runtime identity, fixture, setup/actions, capture provenance, device/environment facts supplied in `capture.json`, limitations, reverse index, and phase revision.
- Does not advance `status.json` until all files and hashes exist.
- Creates `r002` and `manifest.002.json` for a same-contract recapture without overwriting `r001`.

Test `freeze_original(project, phase_id)` rejects unknown required scope, empty checkpoints, missing reverse index, missing required artifacts, and invalid hashes. A valid freeze moves `collecting_original` to `oracle_frozen` and makes the referenced phase contract immutable.

Test the CLI form `phase collect-original <id> --package <path> --controller-export <directory> --mcp-export <server>=<directory>...`. It must validate active preflight, bind every export to its MCP receipt, run package analysis and evidence collection under one phase lock, and publish neither one unless both succeed.

**Step 2: Run and confirm failure**

Run: `python3 -m unittest skills/ditto/scripts/test_phase_workflow.py -v`

Expected: original pack and freeze cases fail.

**Step 3: Implement collection and freeze**

Expose:

```python
def collect_pack(
    role: Literal['original', 'clone'],
    project: Path,
    phase_id: str,
    build: Path,
    controller_export: Path,
    build_metadata: dict,
    preflight: dict,
) -> dict: ...

def freeze_original(project: Path, phase_id: str) -> dict: ...
```

Read capture-wide facts from required MCP-generated `controller_export/capture.json`. Keep setup/actions in the contract and repeat their hashes in the manifest so stale contract/capture pairings are detectable. Compute artifact and build digests locally. Require every capture record to name the active mobile-control MCP server, tool, session, emulator, action result, and source artifact hash.

Run package analysis and MCP evidence validation in a temporary collection directory, then move the complete immutable package, reverse index/tree, checkpoint artifacts, and manifest into `original/`. A failure leaves `status.json` and its active manifest pointer unchanged. Do not provide a `--from` alias or manual-adoption command.

**Step 4: Run focused tests**

Run: `python3 -m unittest skills/ditto/scripts/test_phase_store.py skills/ditto/scripts/test_phase_package.py skills/ditto/scripts/test_phase_workflow.py -v`

Expected: all tests pass.

**Step 5: Commit**

```bash
git add skills/ditto/scripts/phase_capture.py skills/ditto/scripts/phase_store.py skills/ditto/scripts/phase_package.py skills/ditto/scripts/ditto.py skills/ditto/scripts/test_phase_workflow.py
git commit -m "feat(ditto): freeze complete original phase packs"
```

## Task 5: Collect clone packs against the frozen oracle

**Files:**

- Modify: `skills/ditto/scripts/phase_capture.py`
- Modify: `skills/ditto/scripts/ditto.py`
- Modify: `skills/ditto/scripts/test_phase_workflow.py`

**Step 1: Write failing clone tests**

Test `phase capture-clone <id> --apk <path> --controller-export <directory>`:

- Requires `oracle_frozen`, `implementing`, `comparing`, or `correcting` state.
- Uses the same checkpoint IDs, fixture hashes, setup/action hashes, artifact kinds, and environment requirements as the active original manifest.
- Requires the active mobile-control MCP session and contract target identity, rejecting direct ADB, Maestro, manual, or mismatched-device capture provenance.
- Rejects missing and extra checkpoint files.
- Retains the exact clone APK under its hash-qualified name and records the build hash per checkpoint.
- Creates immutable `clone/manifest.NNN.json`, advances only the active clone pointer, and moves state to `comparing` only after successful collection.

**Step 2: Run and confirm failure**

Run: `python3 -m unittest skills/ditto/scripts/test_phase_workflow.py -v`

Expected: clone collection cases fail.

**Step 3: Implement clone collection**

Reuse `collect_pack()` with role-specific validation. Do not run package extraction for the clone. Preserve all referenced clone APKs and manifests so carried-forward checkpoints continue to identify their exact evidence build.

**Step 4: Run focused tests**

Run: `python3 -m unittest skills/ditto/scripts/test_phase_workflow.py -v`

Expected: all tests pass.

**Step 5: Commit**

```bash
git add skills/ditto/scripts/phase_capture.py skills/ditto/scripts/ditto.py skills/ditto/scripts/test_phase_workflow.py
git commit -m "feat(ditto): collect clone phase packs"
```

## Task 6: Produce labeled full-resolution triptychs and honest layout status

**Files:**

- Modify: `skills/ditto/scripts/diff_screenshots.py`
- Modify: `skills/ditto/scripts/test_ditto.py`

**Step 1: Write failing image-comparison tests**

Replace montage expectations with:

```python
def diff_screenshots(
    original: Path,
    candidate: Path,
    output_dir: Path,
    *,
    triptych: bool = True,
    ...,
) -> tuple[bool, dict]: ...
```

Test that the default creates one PNG containing three native-resolution panels in this exact order: original, clone, diff. Add a fixed-height header band with readable built-in bitmap labels `ORIGINAL APK`, `CLONE APK`, and `DIFF`; no external font dependency is allowed. Verify panel pixels remain unscaled.

Test result JSON uses:

```json
{
  "visual_metric_status": "pass",
  "layout_comparison_status": "not_run",
  "layout_reason": "paired XML not supplied"
}
```

When paired XML exists, layout status is `compared`, with counts and deltas. Dimension mismatch or tool error removes stale outputs and returns unavailable through the CLI.

**Step 2: Run and confirm failure**

Run: `python3 -m unittest skills/ditto/scripts/test_ditto.py -v`

Expected: triptych-default and layout-status tests fail.

**Step 3: Implement the triptych and result schema**

Replace `write_montage()` with `write_triptych()`. Implement only the uppercase glyphs and space needed by the three labels as a small 5x7 bitmap table. Preserve the YIQ metric and exclusions. Rename candidate-facing result fields to clone-facing terms and remove the old ambiguous `layout_delta_count: 0` interpretation when XML is absent.

**Step 4: Run focused tests**

Run: `python3 -m unittest skills/ditto/scripts/test_ditto.py -v`

Expected: all retained and new PNG/diff tests pass.

**Step 5: Commit**

```bash
git add skills/ditto/scripts/diff_screenshots.py skills/ditto/scripts/test_ditto.py
git commit -m "feat(ditto): emit labeled parity triptychs"
```

## Task 7: Batch compare checkpoints and record semantic verdicts

**Files:**

- Create: `skills/ditto/scripts/phase_compare.py`
- Modify: `skills/ditto/scripts/ditto.py`
- Modify: `skills/ditto/scripts/test_phase_workflow.py`

**Step 1: Write failing batch and verdict tests**

Test:

```python
def compare_phase(project: Path, phase_id: str) -> dict: ...
def record_verdict(
    project: Path,
    phase_id: str,
    checkpoint_id: str,
    dimension: str,
    status: str,
    rationale: str,
    evidence: list[str],
    authorization: str | None = None,
) -> dict: ...
```

`compare_phase()` must compare every active PNG pair in checkpoint order, use XML only when both manifests supply it, create immutable checkpoint result/triptych revisions, and atomically replace `diff/report.json` plus `diff/phase_overview.png`. The overview is a thumbnail index and declares that full triptychs govern acceptance.

Test ratio guidance without automatic semantic acceptance: below 1% may remain failed, 1–5% requires rationale, and above 5% may pass only through an explicit semantic verdict with cited authorized difference. Test wrong evidence kinds for dimensions, empty rationale, missing evidence IDs, accepted differences without authorization, and proposed differences without proposal metadata.

**Step 2: Run and confirm failure**

Run: `python3 -m unittest skills/ditto/scripts/test_phase_workflow.py -v`

Expected: comparison and verdict cases fail.

**Step 3: Implement batch comparison and verdict storage**

Result files contain metric data, layout status, per-dimension verdicts, evidence references, package/manifest identities, invalidation state, and semantic history. `phase verdict` updates `status.json` under lock and regenerates the report; it never edits immutable metric results. Use `status.json.checkpoints[id].dimensions` as the mutable semantic record.

**Step 4: Run focused tests**

Run: `python3 -m unittest skills/ditto/scripts/test_ditto.py skills/ditto/scripts/test_phase_workflow.py -v`

Expected: all tests pass.

**Step 5: Commit**

```bash
git add skills/ditto/scripts/phase_compare.py skills/ditto/scripts/ditto.py skills/ditto/scripts/test_phase_workflow.py
git commit -m "feat(ditto): batch compare phase checkpoints"
```

## Task 8: Add conservative dependency invalidation

**Files:**

- Modify: `skills/ditto/scripts/phase_compare.py`
- Modify: `skills/ditto/scripts/ditto.py`
- Modify: `skills/ditto/scripts/test_phase_workflow.py`

**Step 1: Write failing invalidation tests**

Test:

```python
def affected_checkpoints(contract: dict, changed_paths: list[str]) -> tuple[set[str], list[str]]: ...
def invalidate(project: Path, phase_id: str, changed_paths: list[str]) -> dict: ...
```

Cover exact and glob path rules, transitive component edges, shared theme/navigation/model/persistence components, multiple changed paths, unrelated known paths, and unknown paths. Unknown paths, native build files, global assets, dependency upgrades, or a cyclic/malformed dependency graph must invalidate every checkpoint. Every invalidation records timestamp, changed paths, resolved components, reopened checkpoints, superseded result revisions, and reason.

Verify passing unaffected checkpoints retain their evidence manifest/build pointers after a new clone build. Invalidated checkpoints become pending and state moves to `correcting`.

**Step 2: Run and confirm failure**

Run: `python3 -m unittest skills/ditto/scripts/test_phase_workflow.py -v`

Expected: invalidation cases fail.

**Step 3: Implement graph traversal and CLI command**

Resolve path rules first, traverse component edges with an explicit visited set, and map reached components to checkpoint dependency declarations. Treat any unclassified input as phase-wide. Do not infer dependencies from filenames beyond contract rules.

**Step 4: Run focused tests**

Run: `python3 -m unittest skills/ditto/scripts/test_phase_workflow.py -v`

Expected: all tests pass.

**Step 5: Commit**

```bash
git add skills/ditto/scripts/phase_compare.py skills/ditto/scripts/ditto.py skills/ditto/scripts/test_phase_workflow.py
git commit -m "feat(ditto): invalidate affected checkpoints"
```

## Task 9: Enforce automated readiness and final human review

**Files:**

- Modify: `skills/ditto/scripts/phase_compare.py`
- Modify: `skills/ditto/scripts/ditto.py`
- Modify: `skills/ditto/scripts/test_phase_workflow.py`

**Step 1: Write failing readiness and review tests**

Test:

```python
def ready_phase(project: Path, phase_id: str) -> dict: ...
def record_review(
    project: Path,
    phase_id: str,
    decision: Literal['accept', 'request_changes'],
    note: str,
    checkpoints: list[str] = (),
) -> dict: ...
```

`ready_phase()` exits nonzero for changed required skill bytes, missing or stale active preflight, MCP target/session mismatch, non-MCP evidence provenance, missing pairs, hash mismatch, stale report, pending/failed/invalidated checkpoint, required layout with unavailable XML, unsupported evidence-to-dimension mapping, unauthorized accepted difference, unresolved proposed exclusion outside the final decision packet, or a deliverable build without traceable checkpoint evidence. Success moves the state to `automated_ready` but leaves human review pending.

`record_review()` rejects calls before automated readiness and blank notes. Acceptance moves to `human_accepted`. Requested changes require at least one valid checkpoint, reopen those checkpoints, append the decision history, and move to `correcting`. A second review can occur only after readiness passes again.

**Step 2: Run and confirm failure**

Run: `python3 -m unittest skills/ditto/scripts/test_phase_workflow.py -v`

Expected: readiness/review cases fail.

**Step 3: Implement gates and transitions**

Centralize state transitions in one validated table. Make CLI exit code 0 mean the requested gate or review write succeeded; use 1 for an unmet gate and 2 for malformed input/tool failure. Print a compact error list and keep full details in `diff/report.json`.

**Step 4: Run focused tests**

Run: `python3 -m unittest skills/ditto/scripts/test_phase_store.py skills/ditto/scripts/test_phase_package.py skills/ditto/scripts/test_phase_workflow.py -v`

Expected: all tests pass.

**Step 5: Commit**

```bash
git add skills/ditto/scripts/phase_compare.py skills/ditto/scripts/ditto.py skills/ditto/scripts/test_phase_workflow.py
git commit -m "feat(ditto): gate readiness and phase review"
```

## Task 10: Rewrite the skill documentation for the replacement pipeline

**Files:**

- Modify: `skills/ditto/SKILL.md`
- Modify: `skills/ditto/references/contracts.md`
- Modify: `skills/ditto/references/reverse-engineering.md`
- Modify: `skills/ditto/references/parity.md`
- Modify: `skills/ditto/references/runtime-workflow.md`
- Modify: `skills/ditto/references/toolchain.md`
- Modify: `skills/ditto/references/extraction.md`
- Modify: `skills/ditto/agents/openai.yaml`

**Step 1: Add a failing documentation-contract test**

In `test_phase_workflow.py`, scan the Ditto source/reference files. Assert there are no executable or instructional references to `ledger.py`, `validate_spec.py`, `spec/coverage.json`, `evidence/index.json`, paired recordings, video capture, journey-level human checkpoints, migration, legacy compatibility, direct ADB control, Maestro fallback, manual capture adoption, or direct reverse-engineering CLI fallback. Allow the design document's explicit statements that these paths are unsupported.

Assert `SKILL.md` contains the sequence:

1. Define phase.
2. Load and hash compulsory skills.
3. Pass JADX, Apktool, FlutterDec, r2Flutter, and mobile-control MCP probes.
4. Reverse engineer package through MCPs.
5. Collect/freeze the complete original pack through the controller MCP.
6. Implement whole phase.
7. Collect the clone pack through the controller MCP.
8. Batch compare and semantically review.
9. Correct only failed/invalidated checkpoints.
10. Run automated readiness.
11. Request one end-of-phase human review.

**Step 2: Run and confirm failure**

Run: `python3 -m unittest skills/ditto/scripts/test_phase_workflow.py -v`

Expected: documentation scan fails on current legacy instructions.

**Step 3: Rewrite documentation and remove old implementation**

Keep `SKILL.md` short. Put preflight, receipt, schema, and command examples in `contracts.md`; package-analysis routing in `reverse-engineering.md`; still-image comparison guidance in `parity.md`; and MCP controller/session details in `runtime-workflow.md`. Explain that reverse-engineered findings are inferred until confirmed by runtime evidence. Remove all video guidance, migration/backward-compatibility text, direct ADB control, Maestro fallback, manual evidence adoption, and direct reverse-engineering CLI fallback from operational files.

Confirm the removed scripts and tests are still absent. Preserve unrelated inventory, image, theme, and emulator coverage.

**Step 4: Run focused tests and scans**

Run:

```bash
python3 -m unittest discover -s skills/ditto/scripts -p 'test_*.py' -v
rg -n "ledger\.py|validate_spec\.py|coverage\.json|evidence/index\.json|\.mp4|video capture|paired recordings|journey checkpoint|direct ADB|Maestro fallback|manual adoption" skills/ditto
```

Expected: all tests pass. `rg` returns only historical design explanation where explicitly allowed by the test, with no operational instruction or code dependency.

**Step 5: Commit**

```bash
git add -A skills/ditto
git commit -m "docs(ditto): replace journey workflow with phase batches"
```

## Task 11: Prove the clean replacement end to end

**Files:**

- Modify: `skills/ditto/scripts/test_phase_workflow.py`
- Modify as required by failures: `skills/ditto/scripts/phase_*.py`, `skills/ditto/scripts/ditto.py`, `skills/ditto/scripts/diff_screenshots.py`

**Step 1: Add one end-to-end acceptance test**

Build a temporary two-checkpoint phase and execute the CLI through subprocesses:

1. Initialize phase.
2. Write and validate the contract.
3. Hash all three required skills and record valid same-package JADX, Apktool, FlutterDec, and r2Flutter receipts plus a complete emulator-controller receipt.
4. Collect an original APK, reverse index, controller-produced PNGs, XML for one checkpoint, and trace evidence.
5. Freeze the oracle.
6. Collect a clone APK and matching controller-produced artifacts.
7. Batch compare and confirm two labeled triptychs.
8. Record visual, behavior, and layout verdicts; confirm missing XML is `not_run` and cannot satisfy a required layout dimension.
9. Reach automated readiness after correcting the contract/evidence.
10. Invalidate one checkpoint through a known component path and prove the other remains closed on its older identified clone build.
11. Recapture/recompare the affected checkpoint, reach readiness again, record human acceptance, and confirm final state `human_accepted`.

Also assert the temporary project contains only the new phase format and no legacy ledger files.

**Step 2: Run the test and fix only demonstrated failures**

Run: `python3 -m unittest skills/ditto/scripts/test_phase_workflow.py -v`

Expected: the new end-to-end test passes.

**Step 3: Run the complete Ditto suite**

Run:

```bash
python3 -m unittest discover -s skills/ditto/scripts -p 'test_*.py' -v
python3 -m compileall -q skills/ditto/scripts
git diff --check
```

Expected: every test passes, compilation succeeds, and `git diff --check` prints nothing.

**Step 4: Exercise CLI help and removal boundaries**

Run:

```bash
python3 skills/ditto/scripts/ditto.py --help
python3 skills/ditto/scripts/ditto.py phase --help
python3 skills/ditto/scripts/ditto.py check
test ! -e skills/ditto/scripts/ledger.py
test ! -e skills/ditto/scripts/validate_spec.py
```

Expected: both help commands succeed; removed `check` exits nonzero with an argparse error; both file-absence checks succeed.

**Step 5: Commit**

```bash
git add skills/ditto
git commit -m "test(ditto): verify phase pipeline end to end"
```

## Task 12: Final spec coverage and review audit

**Files:**

- Review: `docs/superpowers/specs/2026-09-22-ditto-phase-batch-pipeline-design.md`
- Review: all files changed by Tasks 1–11

**Step 1: Check every acceptance criterion against code and tests**

Create a temporary checklist outside the repository and map each design acceptance criterion to one implementation location and one passing test. Pay special attention to compulsory skill hashes, same-package MCP provenance, emulator-controller-only capture, Flutter AOT capability checks, screenshot-only evidence, adaptive semantic decisions, selective recapture, final-only human review, and absence of compatibility or fallback code.

**Step 2: Scan for unfinished or stale implementation language**

Run:

```bash
rg -n "unfinished-marker|not implemented|legacy|migration|backward.compat|\.mp4|video|direct ADB|Maestro fallback|manual adoption" skills/ditto
```

Inspect every result. Remove unfinished implementation markers and stale operational guidance. Keep explicit statements that legacy compatibility and video are unsupported only where they clarify the contract.

**Step 3: Run final verification once**

Run:

```bash
python3 -m unittest discover -s skills/ditto/scripts -p 'test_*.py' -v
python3 -m compileall -q skills/ditto/scripts
git diff --check
git status --short
```

Expected: all tests pass, compilation and whitespace checks succeed, and only intentional reviewed changes are present.

**Step 4: Request code review and fix confirmed findings**

Review against the **Review Focus** section above. Fix every confirmed high-confidence issue, rerun the affected test first, then rerun the final verification commands once.

**Step 5: Commit final corrections if needed**

```bash
git add skills/ditto docs/superpowers/plans/2026-09-22-ditto-phase-batch-pipeline.md
git commit -m "fix(ditto): close phase pipeline review findings"
```

Floww cleanup is intentionally a later project task. Begin it only after this plan passes and the new Ditto commands can recollect Floww's evidence directly into phase workspaces; do not write a legacy-data converter.
