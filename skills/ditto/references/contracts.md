# Evidence and specification contracts

Use stable screen, state, flow, and evidence IDs. Keep one canonical home for each contract; screen files link to shared API and storage definitions. JSON/YAML is useful for automated consumers, but choose formats that fit the project rather than maintaining duplicate representations by hand.

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

When automation needs schemas, define and validate them for the chosen representation. Also validate evidence paths/hashes and cross-references; syntactically valid JSON alone does not make a contract complete or true.

## Minimal machine-readable records

These examples define field relationships, not facts about the user's app. Replace example values from actual captures. Store evidence records in `evidence/index.json` and flow coverage in `spec/coverage.json`; preserve the existing project's format if it already has equivalents.

```json
{
  "schema_version": 1,
  "records": [{
    "id": "ev-settings-ready-001",
    "kind": "screenshot",
    "role": "original",
    "runtime": true,
    "path": "evidence/runtime/checkpoint-001/screen.png",
    "sha256": "REPLACE_WITH_SHA256_OF_SANITIZED_FILE",
    "app_sha256": "REPLACE_WITH_INPUT_HASH",
    "platform": "android",
    "state_id": "settings.ready",
    "flow_id": "open-settings",
    "fixture_id": "signed-in-test-account",
    "capture": {"tool": "adb", "version": "RECORD_ACTUAL_VERSION"},
    "limitations": []
  }]
}
```

```json
{
  "schema_version": 1,
  "cases": [{
    "id": "open-settings.android",
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

Before handing off, verify unique IDs, existing relative artifact paths, actual SHA-256 values, references to known screen/flow IDs, and required-case counts. Run `python3 "$DITTO_SKILL/scripts/validate_spec.py" --check-files` to deterministically validate both `evidence/index.json` and `spec/coverage.json`. Reject a claim of `observed: true` with no supporting runtime evidence, or `validation: pass` without a comparison result. All example placeholders must be replaced in generated project records; the examples themselves must never enter a real evidence ledger unchanged.

## Enforced comparison record

The validator requires artifact and app SHA-256 digests. Each observed case must reference `role: original`, `runtime: true` evidence matching its flow and platform. Candidate captures use their own build hash, never the original APK's hash. Synthetic renders use `runtime: false`. Scope cases to checkpoints/branches, not whole subsystems.

A passing case requires `observed: true`, `implemented: true`, nonempty `required_dimensions`, the current `original_app_sha256` and `candidate_app_sha256`, and `comparison` pointing to a project-relative JSON file:

```json
{
  "case_id": "open-settings.android",
  "result": "pass",
  "original_evidence_ids": ["ev-settings-ready-001"],
  "candidate_evidence_ids": ["ev-candidate-settings-ready-001"],
  "fixture_id": "signed-in-test-account",
  "method": "paired runtime replay plus visual comparison",
  "steps": ["Launch from matching fixture", "Open Settings", "Back returns home"],
  "dimensions": {"visual": "pass", "behavior": "pass"}
}
```

Both evidence lists must be included in the case's `evidence_ids`, have the correct role, matching flow/platform/state/build hash, and the comparison's fixture ID. All required dimensions must pass. Keep measurements, expected/actual observations, replay logs, and accepted-difference links alongside this record; the validator checks structure and provenance relationships, not the truth of a manually entered verdict. Choose required dimensions before implementation. A persistence claim needs restart/readback evidence, not a screenshot of a form. Update the case's build hashes when the target changes; the validator cannot discover the installed build automatically.

`user_testing` is `pending`, `changes_requested`, `accepted`, or `waived`. Accepted/waived requires `user_decision`, a project-relative nonempty text record of the actual user response, date, build, and scope. Automated validation cannot authenticate that response. Acceptance and comparison results remain separate.

Legacy schema-version-1 ledgers need these additional fields before their claims validate. Preserve old evidence, downgrade unsupported claims, and add metadata only when known; do not relabel synthetic captures as runtime, replace hashes blindly, or invent user decisions. Missing coverage is an error. For an existing alternate ledger format, export these two JSON files from its canonical records before using the bundled validator; do not maintain duplicate ledgers by hand. Use `--check-files` to verify referenced artifact bytes; running without it checks metadata and comparison records only.

Boolean status fields must be booleans, and `not_applicable` requires a `reason`. Empty ledgers may represent an initial static inventory, never completion. The validator does not discover omitted journeys, verify capture-environment details, or authenticate user feedback: inspect these manually and report executed/required counts against the agreed scope. It is a record-integrity check, not a certification of parity.
