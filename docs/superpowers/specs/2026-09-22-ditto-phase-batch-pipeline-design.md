# Ditto Phase-Batch Pipeline Design

Date: 2026-09-22
Status: Approved
Audience: Ditto skill maintainers and agents reconstructing mobile applications

## Purpose

Replace Ditto's repeated journey-slice capture and comparison loop with a phase-batch workflow. A phase collects its original-app evidence first, freezes a stable manifest, implements the complete bounded phase, captures the clone once, compares all checkpoints in a batch, and corrects only failed or invalidated checkpoints.

The new workflow must reduce repeated emulator work and agent context usage without weakening evidence provenance, behavioral verification, or completion gates.

## Decisions

1. A phase is the unit of implementation, automated comparison, and human review.
2. Human review has one stage at the end of an automated-ready phase. It repeats only when that review requests corrections; there are no mandatory implementation-time checkpoints.
3. Original and clone artifacts use flat mirrored folders, stable checkpoint prefixes, and explicit evidence revisions.
4. Every screenshot comparison produces a full-resolution `Original | Clone | Diff` triptych by default.
5. Pixel difference is diagnostic evidence. The AI assigns the semantic verdict after inspecting the triptych and relevant nonvisual evidence.
6. A passing or accepted checkpoint is not recaptured unless a dependency, fixture, build identity, or new oracle observation invalidates it.
7. The AI may inspect any phase artifact and may return to the running original app when evidence is missing or contradictory.
8. Independent implementation work may run in parallel. One owner controls integration, manifests, builds, and each device session.
9. Ditto captures no video. Static and transitional states use screenshots, with ordered screenshot checkpoints when one image cannot explain a state change.
10. Reverse engineering the supplied application package is a standard oracle-collection step, not an exceptional fallback.
11. The phase-batch format replaces the legacy ledger directly. Ditto provides no migration or backward-compatibility layer.
12. Every Flutter reconstruction phase requires the Ditto, Flutter-Dart, and verification-before-completion skills.
13. Android Flutter phases require healthy JADX, Apktool, FlutterDec, r2Flutter, and mobile-control MCP sessions. The agent may not replace them with direct CLI, direct ADB, Maestro, or manual capture.
14. A failed skill or MCP preflight blocks the phase. An MCP must prove the expected capability against the identified package or emulator; configured or connected status alone is insufficient.

## Phase Workspace

Each phase uses a flat mirrored structure:

```text
phases/
  phase_b_daily_logging/
    phase.001.json
    preflight.001.json
    status.json
    notes.md

    original/
      manifest.001.json
      app.0dc0d27c.apk
      reverse.001.json
      reverse.001/
        AndroidManifest.xml
        resources/
        sources/
      001_log_top.r001.png
      001_log_top.r001.xml
      002_log_bottom.r001.png
      002_log_bottom.r001.xml
      003_flow_selection.r001.png
      004_symptoms_picker.r001.png
      004_symptoms_picker.r001.xml
      005_moods_open_start.r001.png
      006_moods_open_mid.r001.png
      007_moods_open_settled.r001.png

    clone/
      manifest.001.json
      app.59b98a00.apk
      001_log_top.r001.png
      001_log_top.r001.xml
      002_log_bottom.r001.png
      002_log_bottom.r001.xml
      003_flow_selection.r001.png
      004_symptoms_picker.r001.png
      004_symptoms_picker.r001.xml
      005_moods_open_start.r001.png
      006_moods_open_mid.r001.png
      007_moods_open_settled.r001.png

    diff/
      001_log_top.r001.triptych.png
      001_log_top.r001.result.json
      002_log_bottom.r001.triptych.png
      002_log_bottom.r001.result.json
      003_flow_selection.r001.triptych.png
      003_flow_selection.r001.result.json
      004_symptoms_picker.r001.triptych.png
      004_symptoms_picker.r001.result.json
      005_moods_open_start.r001.triptych.png
      005_moods_open_start.r001.result.json
      006_moods_open_mid.r001.triptych.png
      006_moods_open_mid.r001.result.json
      007_moods_open_settled.r001.triptych.png
      007_moods_open_settled.r001.result.json
      phase_overview.png
      report.json
```

The AI starts with the current phase contract referenced by `status.json`, `diff/report.json`, and `diff/phase_overview.png` for efficiency, but it may inspect every file in the phase whenever needed. The summary is an index, not an access restriction.

## Naming Contract

Checkpoint artifacts use:

```text
<three-digit-order>_<state-name>.r<evidence-revision>.<extension>
<three-digit-order>_<state-name>.r<evidence-revision>.triptych.<extension>
<three-digit-order>_<state-name>.r<evidence-revision>.result.json
```

Rules:

- Use lowercase snake case.
- Use a stable observable state name, not an action, role, timestamp, or temporary label.
- The `<order>_<state-name>` prefix must identify the same checkpoint in `original`, `clone`, and `diff`.
- Revisions begin at `r001` independently for original and clone and increment only when that role's checkpoint is recaptured.
- Files are immutable. Recapture creates the next revision instead of overwriting an earlier artifact.
- `status.json` selects the active original, clone, and diff revision for each checkpoint.
- The role comes from the folder and must not be repeated in the filename.
- Do not use ambiguous names such as `b01`, `c04`, `final`, `new`, or `fixed`.
- New oracle checkpoints append the next sequence number. Existing original artifacts are not renamed or overwritten after the manifest is frozen.

Examples:

```text
001_log_top.r001.png
004_symptoms_picker.r001.png
011_save_reopen.r001.png
012_cold_restart.r001.png
013_notes_keyboard_open.r002.png
```

Evidence IDs are generated from structured fields rather than filenames:

```text
<phase-id>.<checkpoint-id>.<role>.<kind>
```

## Contracts and manifests

Versioned files such as `phase.001.json` are immutable phase contracts. They own scope, ordered checkpoints, fixture definitions, setup and actions, expected artifacts, required dimensions, dependencies, and authorized differences. A post-freeze contract change creates the next phase revision and invalidates affected results.

Versioned files such as `original/manifest.001.json` are immutable oracle capture manifests containing original build/runtime identity, artifact hashes, capture provenance, and the phase-contract revision they satisfy. Versioned clone manifests record each clone build, its APK path, captures, and the phase revision. Referenced APKs are retained with hash-qualified names such as `app.59b98a00.apk`.

`original/reverse.NNN.json` is the immutable index for a package-analysis pass. Its matching `original/reverse.NNN/` directory contains extracted package metadata and only the decoded resources or source fragments relevant to the phase. The index records the package hash, tools and versions, commands, hashes of retained files, original package paths, phase/checkpoint links, and extraction limitations. Generated decompiler names or inferred behavior are hypotheses until runtime evidence confirms them.

`status.json` is the small mutable state record. It points to the current phase, original, and clone manifest revisions and stores phase state, checkpoint verdicts, invalidation history, and final human-review status. This separation allows status to change without rewriting contracts or evidence history.

`preflight.NNN.json` is an immutable capability record. It stores each required skill's name, resolved `SKILL.md` path and SHA-256; each MCP server and tool identity; a bounded successful probe; the original package hash for reverse-engineering MCPs; the emulator identity for the mobile-control MCP; tool versions; limitations; and capture time. `status.json` points to the active preflight revision. A receipt proves only the recorded probe, so later MCP disconnection or target replacement blocks the next operation until preflight is rerun.

The phase contract contains:

- Phase ID and scope
- Ordered checkpoints
- Fixture, setup, and ordered actions
- Expected artifact kinds
- Required comparison dimensions
- Ownership and dependencies
- Preauthorized intentional differences or exclusions

Example checkpoint:

```json
{
  "number": 1,
  "id": "log_top",
  "setup": "Period recorded from September 18 through September 22",
  "actions": ["Tap the center log button"],
  "artifacts": ["png", "xml"],
  "required_dimensions": ["visual", "behavior"],
  "dependencies": ["daily_log_sheet", "theme", "cycle_calculation"]
}
```

The phase contract and original manifest are frozen before implementation. Adding new original evidence is allowed when the AI identifies a missing or contradictory observation. A new checkpoint or changed contract creates a new phase revision plus a monotonically numbered oracle revision; an additional capture under an unchanged contract creates only a new oracle revision. Existing artifact hashes remain unchanged. `status.json` points to the current revisions and reopens only affected scope.

Every runtime artifact record includes SHA-256, capture time, capture command and tool version, build hash, runtime identity, device facts, fixture revision, ordered actions, and limitations. Manifest updates are staged and atomically renamed only after every declared artifact has been captured and hashed.

## Pipeline

### 1. Define the phase

Inventory every in-scope journey, branch, checkpoint, restart effect, and required comparison dimension. A phase must be bounded enough that its implementation can be integrated and reviewed as one coherent unit.

The inventory is the completeness boundary. Ditto cannot discover an unlisted journey automatically, so the phase contract reports inventoried branches and explicit unknowns rather than claiming whole-app completeness. An unknown in required scope blocks oracle freeze. A demonstrably unreachable or unavailable branch may be recorded as `proposed_exclusion`; it must appear in the phase-end report and requires final human acceptance unless already authorized by the project contract.

### 2. Pass the compulsory skill and MCP preflight

Load the Ditto, Flutter-Dart, and verification-before-completion skills and record the exact `SKILL.md` hashes. For an Android Flutter phase, call bounded probes through JADX, Apktool, FlutterDec, r2Flutter, and mobile-control MCPs. The reverse-engineering probes must identify the same original package hash. The controller probe must identify and operate the intended emulator or contract-authorized test device, capture one disposable screenshot, and return device/environment facts.

If a required skill is missing, an MCP is unavailable, the wrong package is loaded, Flutter AOT analysis does not support the package ABI or Dart profile, or the controller cannot perform a required action, record the phase as `blocked`. Do not use a direct executable, direct ADB command, Maestro flow, manually prepared capture directory, or personal-device interaction as a substitute.

MCP backends may internally use JADX, Apktool, FlutterDec, r2Flutter, Android SDK tools, ADB, and the emulator. The no-fallback rule governs the agent-facing interface: all reverse-engineering and UI-control evidence must carry the required MCP provenance.

### 3. Reverse engineer the original package

Hash and retain the supplied APK, IPA, or AAB before runtime exploration. Inspect the package through the required MCPs. For Android this includes the manifest, resource table, strings, dimensions, colors, drawables, fonts, packaged assets, navigation declarations, database schemas, Android wrapper and platform channels, Dart AOT classes/functions/constants, and targeted code connected to the phase. For iOS, a future platform contract must name equivalent compulsory MCP capabilities before an iOS phase can start.

Start with package-wide indexes, then retain a phase-filtered extraction rather than loading a complete decompilation into agent context. Link useful extracted files to checkpoints and dependencies in `reverse.NNN.json`. Reuse original packaged assets when the project is authorized to do so; otherwise treat them as visual references and recreate permitted equivalents. Never execute unknown extracted scripts or binaries as part of inspection.

Reverse engineering guides runtime exploration and implementation: it can identify hidden states, exact strings, dimensions, assets, routes, storage keys, and likely branches. It does not prove that a branch is reachable, that decompiled logic is exact, or that a resource appears in the observed state. Confirm observable claims against runtime screenshots, state transitions, or other suitable evidence.

### 4. Collect the original phase pack

Use the reverse-engineering index to drive a focused replay of the entire phase against the original app through the mobile-control MCP. Capture the declared screenshots, hierarchy XML, state transitions, fixtures, and persistence observations. Record the exact build, MCP session, and runtime environment. Video is not captured.

The original pack is incomplete while any inventoried checkpoint lacks its required evidence. Unknown behavior remains an explicit gap.

Each replay starts from a named fixture revision or emulator snapshot. The manifest fixes clock/date, time zone, locale, theme, font scale, density, viewport, navigation mode, permissions, network conditions, keyboard state, animation scale, and system-chrome treatment when relevant. Stateful journeys declare whether checkpoints run sequentially or reset between captures.

### 5. Freeze the oracle manifest

Hash the original build, reverse-engineering index, and runtime artifacts; validate the manifest; and prevent silent renames, overwrites, or scope reduction. This stable pack becomes the implementation oracle.

### 6. Implement the phase

Agents may inspect all original artifacts, the APK, static analysis results, and the running original app. Implementation proceeds across the whole phase rather than repeatedly stopping for visual comparison after each small slice.

Run inexpensive compile, unit, widget, and launch checks during implementation. Expensive emulator recapture and visual comparison wait until the integrated phase build is ready.

### 7. Parallel work

Parallel agents may own independent components or evidence audits when boundaries are clear. Each task declares owned files, checkpoints, and dependencies. Agents do not share device sessions. A single integration owner resolves shared files, builds the clone APK, and controls the final replay.

The phase contract contains a machine-readable ownership map. Overlapping file ownership or manifest writes are rejected before dispatch. Workers return patches and checks; only the integration owner updates manifests, installs builds, or writes canonical comparison results.

### 8. Capture the clone phase pack

Build and freshly install one identified clone APK through the mobile-control MCP. Replay the original manifest's fixtures and actions in checkpoint order through that MCP. The capture command rejects missing, duplicate, renamed, unexpected, or non-MCP checkpoint pairs. Each checkpoint record stores the exact clone build and controller session used for its evidence.

### 9. Batch comparison

Compare every paired checkpoint in one phase command. Produce:

- A full-resolution triptych for every screenshot checkpoint
- Full-resolution triptychs for every ordered screenshot in a transitional state sequence
- Explicit XML comparison status and hierarchy changes
- Dimension-specific results
- A compact phase overview and machine-readable report

Layout fields must be `not_run` when paired XML was not supplied. A missing comparison must never appear as zero differences.

Screenshot comparison retains Ditto's YIQ colour-delta metric. The result records native dimensions, sensitivity, changed-pixel denominator, allowed ratio, alignment, and every exclusion. Captures are never resized to force a match. Masks cover only declared nondeterminism such as system clock or transient system chrome; each mask is identical across the pair and carries a reason.

Hierarchy comparison is required only for checkpoints whose contract declares `layout` as a required dimension and whose original UI exposes a usable hierarchy. Sparse or unavailable original hierarchy makes layout `not_run` with a reason and prevents a required layout dimension from passing until the phase contract explicitly changes its evidence requirement.

When a transition matters, declare separate start, intermediate, and settled screenshot checkpoints with the exact triggering action and deterministic capture condition for each image. These images validate the declared visible states only. Timing, frame continuity, and motion smoothness are outside the image-only evidence model and must not receive a passing verdict.

### 10. AI semantic review

The AI reviews metrics, triptychs, hierarchy results, reverse-engineering evidence, behavior replay, and persistence evidence. Pixel ratio alone never determines correctness.

Guidance:

- Under 1% difference may still fail when a meaningful control, label, state, or interaction target differs.
- A 1–5% difference requires an explicit semantic explanation.
- A difference above 5% normally fails, but may be accepted when it is dominated by an authorized global difference such as theme or artwork and all relevant structure and behavior match.
- Wrong content, missing controls, clipping, state errors, navigation errors, persistence errors, or unauthorized visual changes fail at any ratio.

An accepted checkpoint records its ratio, affected regions, semantic verdict, rationale, evidence, build identities, and authorization for intentional differences. Authorization comes from the phase contract, an existing project decision, or the final phase review; the AI may classify a difference as acceptable within those boundaries but cannot invent product authorization. A new intentional difference remains `proposed_difference` until final review. `Looks close` is not a valid rationale.

Each passing dimension maps to suitable supporting evidence. Visual metrics support visual verdicts; replay traces support behavior and navigation; write/read/restart traces support persistence; traffic captures support network; semantics or assistive-technology traces support accessibility. The phase-ready command rejects a pass whose evidence kind cannot support its dimension.

### 11. Correction batch

Convert failures into a checkpoint-indexed correction queue. Fix related problems together, rebuild once, and recapture only failed or invalidated checkpoints. Regenerate their diff artifacts and update the phase report.

A new clone APK hash does not automatically invalidate every checkpoint. Impact-validated evidence from an older clone build may be carried forward, and its referenced hash-qualified APK and clone manifest remain in the flat `clone` folder. The integration owner records the source change set and resolves its declared component dependencies to checkpoints. Native build changes, global assets, dependency upgrades, or an incomplete dependency map conservatively invalidate the full phase; otherwise only the transitive affected set reopens. The phase report lists the evidence build for every checkpoint and the current deliverable build.

### 12. Automated readiness and human review

Automated phase readiness requires:

- Every manifest checkpoint paired
- Every required dimension passing, carrying an authorized accepted difference, or carrying a fully evidenced `proposed_difference` that requires only the phase-end product decision
- Every required branch observed, preauthorized as excluded, or recorded as a fully evidenced `proposed_exclusion` for the phase-end scope decision
- No unresolved comparison or provenance errors
- Traceable build and fixture identities for current and carried-forward checkpoint evidence
- No failed or invalidated checkpoints

After the automated phase gate passes, provide the identified build, phase overview, report, accepted differences, and proposed differences for phase-end human review. There are no scheduled mid-phase reviews. Human feedback may accept the phase or reopen specific checkpoints. If changes are requested, automated correction and the phase gate run again before the next phase-end review. Silence and automated review are not human acceptance.

Phase states are:

```text
preflight -> collecting_original -> oracle_frozen -> implementing -> comparing
-> correcting -> automated_ready -> human_accepted
```

Any state may move to `blocked` with a reason. Failed comparisons move `comparing` to `correcting`. New oracle evidence or invalidation moves affected work back to `implementing` or `comparing`. Human changes requested move `automated_ready` to `correcting`. `human_accepted` is the only final completed state.

## Selective Invalidation

A checkpoint remains closed after a passing or authorized accepted verdict. Reopen it only when:

- A changed file or component owns the checkpoint.
- A declared shared dependency changes.
- The original or clone build identity changes in a way that can affect it.
- Its fixture or environment changes materially.
- New original evidence contradicts the recorded contract.
- Human phase review reports a discrepancy.

Shared theme, navigation, model, persistence, localization, or platform changes invalidate all checkpoints that declare that dependency. Unrelated corrections do not trigger a full phase recapture.

Dependencies are stored as a directed graph from files or logical components to checkpoints. Invalidation follows transitive edges. An unknown changed path is treated conservatively as phase-wide until classified. Every invalidation records the triggering change and previously accepted result it superseded.

## Comparison Outputs

For screenshots, the default review artifact is one horizontal image:

```text
Original APK | Clone APK | Diff
```

The triptych preserves full checkpoint resolution per panel. `phase_overview.png` uses thumbnails for navigation and must not be used alone for fine visual acceptance.

Each result file distinguishes:

- `visual_metric_status`
- `semantic_visual_verdict`
- `layout_comparison_status`
- Behavior, navigation, persistence, platform, network, and accessibility verdicts
- Supporting evidence per verdict
- Accepted-difference authorization
- Invalidation status

Passing nonvisual dimensions require dimension-appropriate evidence. Screenshot files cannot establish behavior, navigation, persistence, network, or accessibility passes.

## Completion Command

The existing record-integrity check remains useful, but it is not a completion gate. Add a phase-ready command that exits nonzero when:

- A required checkpoint is missing, failed, pending, or invalidated.
- A required artifact pair is absent.
- A semantic verdict lacks supporting evidence or rationale.
- An accepted difference lacks recorded authorization.
- A required dimension lacks suitable evidence.
- Artifact or build hashes are stale.

Human review status is reported separately because it occurs after automated readiness. The phase is not complete until that review is accepted.

The command surface is:

```text
ditto phase init <phase-id>
ditto phase preflight <phase-id> --package <path> --skill <name>=<path>... --receipt <path>...
ditto phase collect-original <phase-id>
ditto phase freeze-original <phase-id>
ditto phase capture-clone <phase-id> --apk <path>
ditto phase compare <phase-id>
ditto phase verdict <phase-id> <checkpoint-id> --dimension <name> --status <status> --rationale <text>
ditto phase invalidate <phase-id> --changed <path>...
ditto phase ready <phase-id>
ditto phase review <phase-id> --accept --note <text>
ditto phase review <phase-id> --request-changes <checkpoint-id>... --note <text>
ditto phase report <phase-id>
```

`phase verdict` records the AI's dimension-specific semantic decision and supporting evidence. Accepted or proposed differences require the corresponding authorization or proposal metadata. `phase review` may be invoked only to record an actual end-of-phase human decision; it does not infer acceptance from silence.

Commands use a versioned JSON schema, lock manifest writes, stage partial captures outside canonical folders, reject stale reports, and use exit code 0 only when their named operation succeeds. `phase ready` exits nonzero until the phase reaches `automated_ready`; final completion still requires the recorded phase-end human decision.

## Replacement and project cleanup

The phase-batch pipeline replaces the legacy Ditto ledger, coverage files, commands, and directory conventions. The implementation removes the old interfaces instead of carrying aliases, converters, dual readers, or schema migration code.

Existing projects such as Floww are cleaned only after the replacement tools are usable. Recollect their current scope into new phase workspaces, validate the new manifests and reports, then remove obsolete Ditto evidence and legacy metadata. Historical files do not become valid new evidence merely by being copied into the new directory shape.

## Acceptance Criteria

- One command imports a complete mobile-control MCP original phase pack.
- Phase work cannot begin until required skill hashes and successful JADX, Apktool, FlutterDec, r2Flutter, and mobile-control MCP probes are recorded.
- Reverse-engineering and runtime evidence without the required MCP provenance is rejected rather than accepted through a fallback.
- Original collection includes a hashed, tool-versioned, phase-filtered reverse-engineering index.
- One command captures the clone against the frozen manifest.
- One command generates all phase comparisons, triptychs, overview, and report.
- Original and clone folders have matching checkpoint prefixes, with active revisions selected in `status.json`.
- An AI can inspect any phase artifact without reconstructing paths from a ledger.
- Passing checkpoints are not recaptured after unrelated corrections.
- Missing XML reports `not_run`, never zero layout differences.
- No command or contract requires, produces, or claims validation from video.
- Legacy ledgers and commands are removed without migration or compatibility paths.
- Nonvisual passes cite appropriate evidence.
- Human review is requested only after the automated phase gate passes.
- The final skill entry file presents this pipeline concisely and routes detail to references and tool help.
