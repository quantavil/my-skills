# Commands and current evidence records

Replace `<ditto-skill>` with the installed Ditto directory. Run examples from the reconstruction project root. `uv --project` uses Ditto's locked Python dependencies without changing the working directory.

## Phase commands

Initialize the phase:

```text
uv run --project "<ditto-skill>" --locked python "<ditto-skill>/scripts/ditto.py" phase init <phase-id> --project .
```

Edit `phase.json` for the actual phase: set its scope summary, runtime target, named fixtures, and checkpoints. Give each checkpoint a stable ID, a `capture_when` description of the settled visible state, required evidence dimensions, and dependencies. Record phase-specific reverse-engineering questions and only already-authorized differences. Keep the checklist focused on the observable flow; it is not an executable replay protocol.

Then verify the four required MCP capabilities against the original package and selected device:

```text
uv run --project "<ditto-skill>" --locked python "<ditto-skill>/scripts/ditto.py" phase preflight <phase-id> --project . --package input/original.apk --receipt work/jadx/receipt.json --receipt work/apktool/receipt.json --receipt work/r2flutter/receipt.json --receipt work/mobile-control/receipt.json
```

Reuse one raw walkthrough output directory per role and phase. On later runs, pass `replace_output=true` to `mobile_control(begin, ...)`; only a validated completed walkthrough may be replaced, and it stays intact until Done succeeds.

For original capture, start the package-bound mobile-control session, then call mobile-control `recorder_control` to open the local panel for the phase contract. A checklist can limit which checkpoints appear; navigation itself stays free-form:

```json
{"operation":"start","contract_path":"phases/<phase-id>/phase.json","checkpoint_ids":["<checkpoint-id>"],"role":"original"}
```

The recorder saves candidate screenshots, available XML, and the action log. After the human selects **Done**, review the candidate screenshots and select the image that actually shows each checkpoint. Call `recorder_control` with `operation="select"` to write the provenance-bearing selection file:

```json
{"operation":"select","exploration_dir":"<finished-export-dir>","selections":[{"checkpoint_id":"<checkpoint-id>","candidate_number":1,"observed_state":"The expected screen and content are visible"}]}
```

Then select the chosen original evidence and freeze it. Supply verified reverse-engineering exports on the first selection; later selections reuse them:

```text
uv run --project "<ditto-skill>" --locked python "<ditto-skill>/scripts/ditto.py" phase select-original <phase-id> --project . --selection <finished-export-dir>/selected-candidate.json --package input/original.apk --mcp-export jadx=work/jadx --mcp-export apktool=work/apktool --mcp-export r2flutter=work/r2flutter
uv run --project "<ditto-skill>" --locked python "<ditto-skill>/scripts/ditto.py" phase freeze-original <phase-id> --project .
```

For clone comparison, begin a package-bound mobile-control session with the fresh debug APK installed, then call `recorder_control` to open the same browser with the project, phase contract, and skill CLI path. It displays the original beside the live clone:

```json
{"operation":"start","contract_path":"phases/<phase-id>/phase.json","checkpoint_ids":["<checkpoint-id>"],"role":"clone","project_path":".","phase_cli_path":"<ditto-skill>/scripts/ditto.py"}
```

For each settled checkpoint, the human uses **Capture & compare**; the browser invokes the shared CLI, displays the resulting triptych, and advances with **Next**. **Previous checkpoint** supports a targeted retake. **Notes** are optional. **Done** ends the session. The capture result includes `ok`, `checkpoint_id`, `status`, `result`, `triptych`, and `report`. The browser's per-checkpoint CLI request has this form:

```text
uv run --project "<ditto-skill>" --locked python "<ditto-skill>/scripts/ditto.py" phase capture-clone <phase-id> --project . --selection <comparison-request.json> --apk build/app-debug.apk
```

Do not run a separate replay as a prerequisite for original or clone capture.

Replacing a frozen original checkpoint is deliberate and invalidates its dependent comparison. Use `--replace-frozen` on `phase select-original` when replacing it. A successful clone retake replaces its current checkpoint files and clears its old verdict. When code or fixture changes affect a checkpoint, explicitly invalidate that scope before recapture. Record AI parity decisions, check readiness, and present the current report for final human review:

```text
uv run --project "<ditto-skill>" --locked python "<ditto-skill>/scripts/ditto.py" phase invalidate <phase-id> --project . --changed lib/theme.dart
uv run --project "<ditto-skill>" --locked python "<ditto-skill>/scripts/ditto.py" phase verdict <phase-id> <checkpoint-id> --project . --dimension visual --status pass --rationale "Visible content and geometry match." --evidence <evidence-id>
uv run --project "<ditto-skill>" --locked python "<ditto-skill>/scripts/ditto.py" phase ready <phase-id> --project .
uv run --project "<ditto-skill>" --locked python "<ditto-skill>/scripts/ditto.py" phase report <phase-id> --project .
uv run --project "<ditto-skill>" --locked python "<ditto-skill>/scripts/ditto.py" phase review <phase-id> --project . --accept --note "Reviewed the current build and evidence."
```

`phase verdict` accepts `pass`, `fail`, `accepted_difference`, or `proposed_difference`; accepted differences require `--authorization <id>`. Use `phase review --request-changes <checkpoint-id>` instead of `--accept` when the human requests another correction. Readiness is not human acceptance.

## Current records

Each phase has one current original manifest, one current clone manifest, and one current report. The scripts maintain current evidence and metadata; successful captures overwrite the current checkpoint files instead of accumulating revisions.

| Evidence | Current path |
| --- | --- |
| Phase checklist/contract | `phase.json` |
| Current MCP preflight | `preflight.json` |
| Original screenshot and optional hierarchy XML | `original/NNN_<checkpoint-id>.png` and `.xml` |
| Clone screenshot and optional hierarchy XML | `clone/NNN_<checkpoint-id>.png` and `.xml` |
| Comparison triptych and machine result | `diff/NNN_<checkpoint-id>.triptych.png` and `.result.json` |
| Current comparison report and verdict state | `diff/report.json`, `status.json` |
| Current original/clone capture metadata | `original/manifest.json`, `clone/manifest.json` |

The original selection preserves `provenance: "mcp"`, an inline MCP receipt, server/tool/session, device target and environment, package hash, action-log path/hash, selected PNG and optional XML hashes, timestamp, and observed actions. Keep those references tied to the evidence. Do not hand-edit receipts or promote unrelated screenshots into current evidence.

Preflight receipts identify capability, server/tool/version, session, observed time, status, limitations, MCP provenance, and exact target. JADX, Apktool, and r2Flutter must identify the same original APK hash. r2Flutter also reports ABI and Dart profile. Mobile-control verifies the configured device and captures environment facts. A configured tool path or a successful connection alone does not satisfy a required receipt.

Use [runtime workflow](runtime-workflow.md) for browser capture and device handling. Use [parity](parity.md) for interpreting the current image comparison.

## Setup and emulator

Run the config generator from the MCP checkout, merge its output into the MCP client's configuration, and restart the client. It does not overwrite existing files.

```text
uv run --project servers/ditto-bridge --locked python servers/ditto-bridge/configure.py --dart --output ditto-mcp.json
```

Use the mobile-control MCP `manage_emulator` tool with `operation="start"`, the phase AVD name, and optional `port`, `gpu`, and `accel`. Use `gpu="software"` without GPU hardware; `accel` controls CPU virtualization separately. Operations are `start`, `start-headless`, `status`, `check`, and `stop`. The MCP probe/capture path verifies the installed package.

For iterative Android UI work, keep `flutter run -d <emulator-serial>` open and hot reload with `r`. Preview is for implementation feedback only. Build the fresh debug APK used by clone comparison after related edits; never use a hot-reloaded screenshot as packaged APK evidence.

## Measurement

Replace the checkpoint paths and density with the actual recorded evidence:

```text
uv run --project "<ditto-skill>" --locked python "<ditto-skill>/scripts/theme_extract.py" phases/<phase-id>/original/<checkpoint>.png --hierarchy phases/<phase-id>/original/<checkpoint>.xml --dpi 420 --dart lib/design/tokens.dart
```

## Flutter project

Run from the clone project root. Choose dependencies and generation tools from the [Flutter stack](flutter-stack.md) only when the phase needs them; retain existing project conventions.

After related edits, run appropriate project checks and build a local debug APK for comparison. Adapt project paths and flavors. Run integration tests only when present.

```text
dart fix --dry-run
dart format --output=none --set-exit-if-changed lib test
flutter analyze
flutter test
flutter build apk --debug
flutter test integration_test -d "<emulator-serial>"
```

## Tool maintenance

From the skill directory (no emulator required):

```text
uv run --locked python -m unittest discover -s tests -p "test_*.py"
```

From the MCP checkout:

```text
uv run --project servers/ditto-bridge --locked python -m unittest discover -s servers/ditto-bridge/tests -p "test_*.py"
bun test
bunx tsc --noEmit
bun run check
bun run deploy
```

Update a chosen dependency from its uv project directory with `uv lock --upgrade-package <name>`, run affected checks, and commit the lockfile.
