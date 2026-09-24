# Commands and evidence contracts

Replace `<ditto-skill>` with the installed Ditto directory. Run these commands from the reconstruction project root on Linux or Windows; `uv --project` selects dependencies without changing that working directory.

## Command sequence

```text
uv run --project "<ditto-skill>" --locked python "<ditto-skill>/scripts/ditto.py" phase init daily_logging --project .

uv run --project "<ditto-skill>" --locked python "<ditto-skill>/scripts/ditto.py" phase preflight daily_logging --project . --package input/original.apk --receipt work/jadx/receipt.json --receipt work/apktool/receipt.json --receipt work/r2flutter/receipt.json --receipt work/mobile-control/receipt.json

uv run --project "<ditto-skill>" --locked python "<ditto-skill>/scripts/ditto.py" phase collect-original daily_logging --project . --package input/original.apk --controller-export work/original-controller --mcp-export jadx=work/jadx --mcp-export apktool=work/apktool --mcp-export r2flutter=work/r2flutter --build-metadata '{"package_name":"example.original","version":"1.0"}'

uv run --project "<ditto-skill>" --locked python "<ditto-skill>/scripts/ditto.py" phase freeze-original daily_logging --project .
# Only when frozen raw evidence still applies to revised wording/incidental actions:
uv run --project "<ditto-skill>" --locked python "<ditto-skill>/scripts/ditto.py" phase rebind-original daily_logging --project . --contract phases/daily_logging/phase.002.json --reason "Permission popup was incidental"
uv run --project "<ditto-skill>" --locked python "<ditto-skill>/scripts/ditto.py" phase capture-clone daily_logging --project . --apk build/app.apk --controller-export work/clone-controller --build-metadata '{"package_name":"example.clone","version":"1.0"}'
uv run --project "<ditto-skill>" --locked python "<ditto-skill>/scripts/ditto.py" phase compare daily_logging --project .
uv run --project "<ditto-skill>" --locked python "<ditto-skill>/scripts/ditto.py" phase verdict daily_logging log_top --project . --dimension visual --status pass --rationale "Content and geometry match." --evidence diff:001_log_top.r001.result.json
uv run --project "<ditto-skill>" --locked python "<ditto-skill>/scripts/ditto.py" phase invalidate daily_logging --project . --changed lib/theme.dart
uv run --project "<ditto-skill>" --locked python "<ditto-skill>/scripts/ditto.py" phase ready daily_logging --project .
uv run --project "<ditto-skill>" --locked python "<ditto-skill>/scripts/ditto.py" phase review daily_logging --project . --accept --note "Reviewed the identified build and final evidence."
```

`phase ready` returns exit code 1 when the gate is unmet and 2 for malformed input or tool failure. Human review commands are valid only after readiness succeeds.
The recorder is an optional original-capture control surface; its human actions are evidence collection, not `phase review`.


## Phase contract

Edit `phases/<id>/phase.001.json` before original freeze. It contains:

- `scope.summary`, required-scope `unknowns`, and fully evidenced proposed exclusions.
- `runtime_target` with the exact emulator identity; the supplied controller does not yet support physical devices.
- Named fixtures containing sanitized deterministic setup data.
- Ordered checkpoints with number, stable ID, fixture, setup, actions, artifact kinds, required dimensions, and dependencies.
- When rebinding already recorded incidental system actions, `incidental_actions` lists the removed action labels in the revised checkpoint. Preserve the raw trace and state the reason. Do not use rebind for changed screen content or fixtures.
- `reverse_engineering.include_globs` and targeted questions.
- A dependency graph with components, path rules, and directed component edges.
- Ownership for isolated implementation work.
- Existing authorized differences with stable IDs.

Artifact kinds in the contract schema are `png`, `xml`, `trace`, `state`, `network`, and `semantics`; the current local mobile controller can capture only `png`, `xml`, `trace`, and `state`. Declare `network` or `semantics` only when a verified MCP backend supplies them. Dimensions are `visual`, `layout`, `behavior`, `navigation`, `persistence`, `platform`, `network`, and `accessibility`. The controller export must supply every artifact declared for each captured checkpoint, including nonvisual trace or state evidence when required.

Use three-digit checkpoint numbers and lowercase IDs. Controller exports use `<order>_<checkpoint-id>.<kind>`. Canonical retained evidence adds the revision: `001_log_top.r001.png`. Builds use `app.<hash8>.<extension>`.

## Compulsory MCP receipt

Every receipt is JSON with schema version 1 and includes:

- `capability`, `server`, `tool`, `tool_version`, and `session_id`.
- `observed_at`, bounded request and response SHA-256 values, `status`, and `limitations`.
- `provenance: "mcp"`.
- Exact target identity.

JADX, Apktool, and r2Flutter target the locally computed original-package SHA-256. r2Flutter also reports support, ABI, and Dart profile. Mobile-control targets the contract device, reports environment facts, exercises launch/tap/type/swipe/back/screenshot/hierarchy commands (semantic outcomes are checked during replay), and hashes a disposable screenshot.

Ditto's Flutter and verification guidance is in its own `references/`. Preflight requires no other skill paths. Static receipts are reusable for the same package and analyzer version. They do not expire with time. New captures require the active controller session; retained captures remain bound to their historical sessions. Changing the package or target requires new preflight. Live device checks occur during capture.

## Controller capture receipt

`controller-export/capture.json` repeats the active mobile-control server, tool, session, target, environment, limitations, MCP provenance, installed-package SHA-256, and capture timestamp. Each artifact record names its checkpoint, kind, path, source SHA-256, installed-package SHA-256, fixture, setup/action hashes, successful action result, and the same capture-session identity. Executed action records include arguments and protocol step labels; their ordered labels must match the declared actions. The agent supplies an observed-state description for image review. Missing, duplicate, renamed, extra, linked, manually supplied, foreign-build, or foreign-session files are rejected. MCP `capture` returns compact paths and hashes; `capture.json` retains full provenance.

## Stored records

`original/manifest.NNN.json` binds the contract revision, original build, reverse index, fixture protocol, setup/action hashes, controller session, environment, and every artifact hash. `clone/manifest.NNN.json` binds equivalent clone evidence to its exact build. A same-contract recapture creates a new manifest and new evidence revisions without overwriting prior files. After the original is frozen, `collect-original --checkpoint <id>` revises named checkpoints and carries unchanged original artifacts forward by hash; affected clone checkpoints reopen.

`diff/<checkpoint>.result.json` stores immutable metrics, layout status, manifest/build identities, evidence catalog, and comparison revision. `status.json.checkpoints.<id>.dimensions` stores mutable semantic verdicts and history. `diff/report.json` is the active machine-readable view; `diff/phase_overview.png` is a navigation index.

Valid semantic statuses are `pass`, `fail`, `accepted_difference`, and `proposed_difference`. Every verdict needs a nonempty rationale and evidence IDs whose kinds support the dimension. Accepted differences cite an ID from `authorized_differences`; proposals carry decision metadata for final review.

## Setup and emulator

Run the config generator from the MCP checkout, then merge its output into the
client's configuration and restart the client. It does not overwrite existing files.

```text
uv run --project servers/ditto-bridge --locked python servers/ditto-bridge/configure.py --dart --output ditto-mcp.json
```

Use the mobile-control MCP `manage_emulator` tool with `operation="start"`, the
contract's `avd` name, and optional `port`, `gpu` and `accel`. Use `gpu="software"`
without GPU hardware; `accel` controls CPU virtualization separately. Operations:
`start`, `start-headless`, `status`, `check`, `stop`. APK installation belongs to
MCP probe/begin, which verifies the installed package. Read [runtime workflow](runtime-workflow.md)
for replay and capture fields.

For iterative Android UI work, keep `flutter run -d <emulator-serial>` open. Once
the clone is visible, call mobile-control `preview_begin` with `serial`, `target_id`
(AVD name), and `package_name`; then use `perform`/`replay`, `inspect_ui`, and
`observe_screen`. Hot reload from the Flutter terminal (`r`). Call `abort` to
release the preview session. Preview has no APK receipt and cannot be supplied to
`phase capture-clone`; stop the Flutter run session and build the identified APK
before the package-bound `begin`/capture path.

After `mobile_control(operation="begin", ...)`, a guarded batch call has this shape. Replace the labels, fixture, and observed state with the declared checkpoint; `expect` must identify the resulting screen. The MCP waits up to 5 seconds for it by default (`expect_timeout_ms` can raise that to at most 30000). Do not use a shared button label such as `Next` as the screen marker.

```json
{"operation":"run_checkpoints","plan":[{"steps":[{"action":"tap_target","selector":"Continue","step":"Continue"}],"expect":"Welcome","checkpoint":{"number":1,"checkpoint_id":"welcome","fixture":"fresh","setup":"Fresh launch","actions":["Continue"],"kinds":["png","xml","trace"],"observed_state":"Welcome screen is visible"}}]}
```

## Measurement

Replace checkpoint paths and density with the actual recorded evidence:

```text
uv run --project "<ditto-skill>" --locked python "<ditto-skill>/scripts/theme_extract.py" phases/<phase-id>/original/<checkpoint>.png --hierarchy phases/<phase-id>/original/<checkpoint>.xml --dpi 420 --dart lib/design/tokens.dart
```

## Flutter project

Run from the clone project root. Use only the applicable dependency groups;
these are examples, not a batch installation requirement.

```text
flutter --version
dart --version
# Run only the individual additions justified by the active feature:
flutter pub add flutter_riverpod  # shared async feature state
flutter pub add dio              # richer HTTP requirements
flutter pub add go_router        # declarative routing/deep links

# Relational persistence:
flutter pub add drift drift_flutter path_provider
flutter pub add --dev drift_dev build_runner

# JSON models:
flutter pub add json_annotation
flutter pub add --dev json_serializable build_runner

# Optional union models:
flutter pub add freezed_annotation
flutter pub add --dev freezed
```

Generate only when the corresponding inputs changed:

```text
dart run build_runner build
flutter gen-l10n
```

After related edits, run relevant checks and build the APK to capture. Adapt
paths/flavors; run integration tests only when present. Review automated fixes
before applying them.

```text
dart fix --dry-run
dart format --output=none --set-exit-if-changed lib test
flutter analyze
flutter test                                    # includes golden tests, see flutter-build.md
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

Update a chosen dependency from its uv project directory with
`uv lock --upgrade-package <name>`, run the affected checks, and commit the lockfile.
