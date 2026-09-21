# Evidence and specification contracts

Use stable screen, state, flow, and evidence IDs. Keep one canonical home for each contract; screen files link to shared API and storage definitions.

Use `scripts/ledger.py` for artifact hashes and record links. Preferred emulator tools produce captures; `adopt` registers them without copying the files. Supply verified build/environment facts; adoption cannot discover them from a screenshot. `capture` is the ADB-backed fallback when preferred tooling lacks required capture/provenance capabilities. Edit coverage metadata to define scope and record actual user decisions; document the reason and authorization for any change to required dimensions before recording another comparison. Do not invent hashes or duplicate records by hand.

## Evidence records

For each durable observation record:

- ID, kind, sanitized artifact path, and SHA-256 of that artifact.
- Original app hash/version; platform, device, OS, viewport/density, locale/theme.
- Capture tool/version, time, setup, actions, and fixture reference.
- Result and relevant limitations, including modifications to the original app.

For each material specification claim record its status (`observed`, `inferred`, `unknown`, or `intentional_difference`), evidence IDs, and a short rationale. Use qualitative confidence with an explanation rather than invented calibrated probabilities. Unknown claims may have no supporting evidence; observed claims must link to an actual observation. Preserve contradictory observations until their differing preconditions are explained.

## Screen contract

Create `spec/screens/<screen-id>.md` with these fields, omitting inapplicable sections and explicitly marking unknown facts:

```markdown
# Screen name

Identity: stable ID, platform, route or entry condition
Evidence: capture IDs and reference screenshots

## Visual contract
Viewport/density, layout, assets/fonts, text, spacing, safe areas,
semantic labels, and measured transition behavior where relevant.
Cite the project's canonical token file (see flutter-build.md) instead of re-describing
colours and spacing in prose.

## States and interactions
| State | Precondition | Action | Observable result | Evidence/status |
| --- | --- | --- | --- | --- |

## Navigation
Entry points, guards, destinations, back/dismiss behavior, deep links.

## Data and platform effects
Links to API/storage contracts; permissions, keyboard, lifecycle,
notifications, and native integration behavior relevant to this screen.

## Acceptance
Replay flow IDs, checkpoints, platform-specific tolerances,
accepted differences, and unresolved questions.
```

Do not fill this template with an example login flow and treat it as discovered behavior.

## Shared contracts

**API:** method, endpoint, query/multipart semantics, required headers, authentication behavior without secret values, request/response shapes and meaningful values, error mapping, retries, pagination, timeouts, ordering, and WebSocket messages where observed. A single example response cannot prove optionality or all possible types. Separate observed constraints from inferred schema generalizations.

**Storage:** logical values/entities, reads/writes, cache expiry, logout cleanup, restart behavior, offline queue and conflict resolution, migrations where needed. Preserve observable effects rather than copying implementation-specific SQL tables by default.

**Navigation:** source state, trigger, guard, destination state, back-stack effects, evidence. Check that referenced screens and states exist.

**Native:** capability, platform, permission sequence, lifecycle and failure behavior, plugin/native adapter boundary, and observable acceptance criteria.

**Coverage:** each in-scope flow/state has `observed`, `implemented`, and `validated` tracked separately, plus blockers. Unreachable states remain gaps; inferred completeness is not measured coverage.

**Accepted differences:** original behavior, candidate behavior, rationale, scope, and user decision or existing authorization. Do not silently turn a failing comparison into an accepted difference.

## Writing records with the ledger tool

```bash
# once per project
python3 "$DITTO_SKILL/scripts/ledger.py" --project . init

# Preferred: register an emulator-tool capture already inside this project.
# --app-artifact must be the exact artifact used for this installation.
python3 "$DITTO_SKILL/scripts/ledger.py" --project . adopt evidence/settings.png \
  --role original --flow open-settings --state settings.ready --platform android \
  --app-artifact input/original.apk --fixture signed-in-test-account \
  --tool emulator-tool --tool-version "$CAPTURE_TOOL_VERSION" \
  --environment "$CAPTURE_ENV_JSON" \
  --setup "Signed in, default theme" --action "Tap Settings from Home"

# Fallback when preferred tooling cannot capture required provenance:
python3 "$DITTO_SKILL/scripts/ledger.py" --project . capture \
  --serial "$ORIGINAL_SERIAL" --package com.example.original --role original \
  --flow open-settings --state settings.ready --fixture signed-in-test-account \
  --setup "Signed in, default theme" --action "Tap Settings from Home" \
  --link-case --dimensions visual behavior

python3 "$DITTO_SKILL/scripts/ledger.py" --project . capture \
  --serial "$CANDIDATE_SERIAL" --package com.example.candidate --role candidate \
  --flow open-settings --state settings.ready --fixture signed-in-test-account \
  --link-case

# register something captured another way (iOS, historical, manual)
python3 "$DITTO_SKILL/scripts/ledger.py" --project . adopt path/to/screen.png \
  --role original --flow open-settings --state settings.ready --platform ios \
  --app-artifact input/original.ipa \
  --fixture signed-in-test-account
```

`capture` requires ADB, hashes all installed APKs on-device where supported, and otherwise pulls them into automatically cleaned temporary storage. A single APK uses its file SHA-256; a split installation uses a SHA-256 of the sorted `{name, sha256}` manifest recorded in `app.installed_apks`. This installed-set identity differs from a source AAB or universal APK hash. It records viewport, density, DPR, locale, font scale, night mode and emulator status; record other relevant settings separately.

Captures are immutable: duplicate IDs are rejected before capture, even if old files exist. Use a new `--label` for another observation. Each label has its own directory; `--link-case` defaults to `<flow>.<state>.android` and marks that case unverified pending comparison. Do not overwrite historical evidence to update a build. `adopt --environment path/to/facts.json` embeds known environment facts in the record; the input can be a temporary tool export. `--app-sha256` accepts an already verified installation digest when no exact local artifact is available.

Hot reload and instrumentation can change running code without changing installed APKs. For such captures/adoptions, use `--runtime-mode hot-reload` (or `instrumented`), `--runtime-session <session-id>` and `--runtime-source <all-loaded-source-or-patch-files...>`. The tool hashes those files separately; the caller must ensure they match code actually loaded. Case and comparison runtime digests prevent mixing revisions. Use a freshly built/installed, cold-started candidate for the final checkpoint. Never infer runtime freshness from the installed hash alone.

## Minimal machine-readable records

These examples define field relationships, not facts about the user's app. `ledger.py` produces records in this shape automatically; read this section to understand what it wrote, not as a template to fill in by hand.

```json
{
  "schema_version": 1,
  "records": [{
    "id": "ev-open-settings.settings.ready.original-screen",
    "kind": "screenshot",
    "role": "original",
    "runtime": true,
    "path": "evidence/runtime/open-settings/settings.ready/original/open-settings.settings.ready.original/screen.png",
    "sha256": "<computed by ledger.py, not typed>",
    "app_sha256": "<computed by ledger.py, not typed>",
    "platform": "android",
    "state_id": "settings.ready",
    "flow_id": "open-settings",
    "fixture_id": "signed-in-test-account",
    "environment": {"viewport_px": "1080x2400", "density_dpi": 420, "device_pixel_ratio": 2.625},
    "capture": {"tool": "adb", "method": "exec-out", "version": "1.0.41"},
    "limitations": []
  }]
}
```

```json
{
  "schema_version": 1,
  "cases": [{
    "id": "open-settings.settings.ready.android",
    "flow_id": "open-settings",
    "platform": "android",
    "state_id": "settings.ready",
    "required": true,
    "critical": false,
    "observed": false,
    "implemented": false,
    "validation": "not_run",
    "required_dimensions": ["visual", "behavior"],
    "user_testing": "pending",
    "evidence_ids": [],
    "blocker": null
  }]
}
```

Before handing off, run `python3 "$DITTO_SKILL/scripts/validate_spec.py" --check-files` to deterministically validate both `evidence/index.json` and `spec/coverage.json`. Reject a claim of `observed: true` with no supporting runtime evidence, or `validation: pass` without a comparison result. All example placeholders must be replaced in generated project records; the examples themselves must never enter a real evidence ledger unchanged.

## Enforced comparison record

The validator requires artifact and app SHA-256 digests. Each observed case must reference `role: original`, `runtime: true` evidence matching its flow and platform. Candidate captures use their own build hash, never the original APK's hash. Synthetic renders use `runtime: false`. Scope cases to checkpoints/branches, not whole subsystems.

Write the comparison record with `ledger.py comparison`, not by hand:

```bash
python3 "$DITTO_SKILL/scripts/diff_screenshots.py" \
  evidence/runtime/open-settings/settings.ready/original/open-settings.settings.ready.original/screen.png \
  evidence/runtime/open-settings/settings.ready/candidate/open-settings.settings.ready.candidate/screen.png \
  --output-dir validation/open-settings/android --top-mask 66 \
  --case-id open-settings.settings.ready.android --no-montage

python3 "$DITTO_SKILL/scripts/ledger.py" --project . comparison \
  --case-id open-settings.settings.ready.android \
  --original-evidence ev-open-settings.settings.ready.original-screen \
  --candidate-evidence ev-open-settings.settings.ready.candidate-screen \
  --dimension visual=pass --dimension behavior=pass \
  --dimension network=not_applicable --dimension-reason network="feature has no network call" \
  --step "Launch from matching fixture" --step "Open Settings" --step "Back returns home" \
  --method "paired runtime replay plus visual comparison" \
  --supporting validation/open-settings/android/result.json
```

`comparison` preserves existing required dimensions and rejects missing verdicts or attempts to mark a required dimension inapplicable. Other inapplicable dimensions require `--dimension-reason`. It checks paired role/checkpoint/fixture/build/runtime identity before writing. A failed or blocked dimension cannot produce a pass. It writes one comparison record and updates coverage; actual user acceptance must be recorded separately after changes.

A passing case requires `observed: true`, `implemented: true`, nonempty `required_dimensions`, the current `original_app_sha256` and `candidate_app_sha256`, and `comparison` pointing to a project-relative JSON file. Both evidence lists must be included in the case's `evidence_ids`, have the correct role, matching flow/platform/state/build hash, and the comparison's fixture ID. Keep measurements, expected/actual observations, replay logs, and accepted-difference links alongside this record; the validator checks structure and provenance relationships, not the truth of a manually entered verdict. Choose required dimensions before implementation. A persistence claim needs restart/readback evidence, not a screenshot of a form. Update the case's build hashes when the target changes; the validator cannot discover the installed build automatically.

**Dimension-level `not_applicable` requires a reason and cannot cover a required dimension.** Optional dimensions may be omitted; required dimensions must have verdicts. An optional network dimension for an offline-only feature can be explicitly marked inapplicable with a reason.

**`validation: "blocked"` requires a recorded `blocker`.** A case cannot sit indefinitely blocked with no reason on file; the validator checks that `blocker` is a nonempty string whenever `validation` is `blocked`.

`user_testing` is `pending`, `changes_requested`, `accepted`, or `waived`. Accepted/waived requires `user_decision`, a project-relative nonempty text record of the actual user response, date, build, and scope. Automated validation cannot authenticate that response. Acceptance and comparison results remain separate.

Legacy schema-version-1 ledgers need these additional fields before their claims validate. Preserve old evidence, downgrade unsupported claims, and add metadata only when known; do not relabel synthetic captures as runtime, replace hashes blindly, or invent user decisions. Missing coverage is an error. For an existing alternate ledger format, export these two JSON files from its canonical records before using the bundled validator; do not maintain duplicate ledgers by hand. Use `--check-files` to verify referenced artifact bytes; running without it checks metadata and comparison records only.

Boolean status fields must be booleans. Empty ledgers may represent an initial static inventory, never completion. `validate_spec.py --json` reports required/passing/blocked counts and which critical cases are not passing, so scope does not have to be computed by reading the whole coverage file. The validator does not discover omitted journeys, verify capture-environment details, or authenticate user feedback: inspect these manually and report executed/required counts against the agreed scope. It is a record-integrity check, not a certification of parity.
