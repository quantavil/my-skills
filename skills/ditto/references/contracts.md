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
    "required": true,
    "critical": false,
    "observed": false,
    "implemented": false,
    "validation": "not_run",
    "evidence_ids": [],
    "blocker": null
  }]
}
```

Before handing off, verify unique IDs, existing relative artifact paths, actual SHA-256 values, references to known screen/flow IDs, and required-case counts. Run `python3 "$DITTO_SKILL/scripts/validate_spec.py" --check-files` to deterministically validate both `evidence/index.json` and `spec/coverage.json`. Reject a claim of `observed: true` with no supporting runtime evidence, or `validation: pass` without a comparison result. All example placeholders must be replaced in generated project records; the examples themselves must never enter a real evidence ledger unchanged.
