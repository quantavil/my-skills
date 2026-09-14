# Differential parity workflow

Define acceptance per in-scope flow and platform before measuring. Start with a representative vertical feature, establish reproducible capture, then expand. Keep validation output independent of the implementation's claims.

## Comparable runs

Use separate original and candidate installations or isolated devices. Record both build IDs. Match OS, viewport/density, text scale, theme, locale, permissions, account/fixture state, and network conditions where they affect the comparison. Reset app and backend fixtures between runs as needed; two sequential writes to a shared backend are not equivalent initial conditions.

Replay the same logical user journey. Selectors may differ by implementation, but preconditions, actions, expected effects, and checkpoints must correspond. Capture each checkpoint after the same state settles. Do not overwrite original baselines with candidate output to make a test pass.

## Compare dimensions separately

| Dimension | Meaningful comparison |
| --- | --- |
| Visual | Text, layout, assets, colors, typography, safe areas, transitions |
| Behavior/navigation | Validation, gestures, state transitions, back stack, error and offline handling |
| Network | Methods, paths, meaningful headers/payloads, responses, retry/order/auth semantics |
| Persistence | Before/after logical state, restart, logout, cache and offline behavior |
| Platform | Permissions, lifecycle, deep links, notifications, hardware/native integration |
| Accessibility | Labels, roles, actions, focus and relevant assistive interaction |

Visual metrics such as pixel differences or SSIM support inspection; they do not replace behavior tests. Retain original/candidate images, masks, diff images, metric definitions, and thresholds. Mask only documented nondeterminism, not inconvenient failures. Compare each target with its corresponding original platform; if no iOS original exists, state that the iOS implementation is adapted and lacks direct iOS parity evidence.

Canonicalize network data only where semantics permit it. Normalize redacted tokens or generated IDs consistently while preserving relationships. Do not sort meaningful arrays, discard meaningful headers, or remove timing/order that affects retry, signing, or idempotency. Compare response handling and side effects, not merely JSON key shapes. Different internal storage schemas are acceptable when the required observable semantics match.

## Checks and reporting

Run project formatting/analyzer checks and focused unit/widget/integration tests appropriate to the feature. Build and run each required target on a capable host. Use a qualified platform harness for system UI interactions that the Flutter test layer cannot reach. Report commands, outcomes, and unavailable checks explicitly.

For each case record flow/state/platform, original and candidate evidence IDs, comparison method, result (`pass`, `fail`, `blocked`, `not_run`, or justified `not_applicable`), and discrepancy details. Report executed/required case counts alongside results so skipped work cannot look like full coverage.

Critical authentication, payment, data-integrity, and other user-designated flows require their relevant checks to pass. Do not hide a failure behind a weighted average. If the project requests a composite score, document denominators, weights, handling of untested cases, and critical-flow vetoes. There is no universal 95% release threshold.

For each gap preserve reproduction steps, expected and actual behavior, evidence, severity, and affected component. Correct evidence-backed implementation gaps; rerun affected comparisons. Revisit broader flows when shared behavior changes. If missing access or contradictory evidence prevents a fix, report it instead of looping without progress.

A feature is verified only when its required comparisons pass and any intentional deviations are recorded under the user's accepted scope. Full reconstruction additionally requires coverage of all agreed flows/platforms. A specification-only task can finish with unresolved runtime gaps clearly labeled; an implementation cannot claim those gaps as passing parity. Publishing or production rollout remains a separate task unless already requested.

## Concrete Maestro replay

Create `oracle/flows/open-settings.yaml` only if this journey was observed. Replace the example labels with captured text or stable selectors. The example assumes both installations are already in equivalent authenticated fixture states; `launchApp` alone does not establish that state.

```yaml
appId: ${APP_ID}
---
- launchApp
- assertVisible: "Home"
- tapOn: "Settings"
- assertVisible: "Notifications"
- takeScreenshot: settings-ready
- back
- assertVisible: "Home"
```

Run the same logical flow against separate targets. Set the four variables to actual device and package IDs; restore equivalent fixtures between runs:

```bash
mkdir -p validation/original validation/candidate
maestro --device "$ORIGINAL_DEVICE" test -e APP_ID="$ORIGINAL_APP_ID" --format JUNIT --output validation/original/results.xml --test-output-dir validation/original oracle/flows/open-settings.yaml
maestro --device "$CANDIDATE_DEVICE" test -e APP_ID="$CANDIDATE_APP_ID" --format JUNIT --output validation/candidate/results.xml --test-output-dir validation/candidate oracle/flows/open-settings.yaml
```

Check each exit code, JUnit result, and actual screenshot location. A successful `takeScreenshot` does not compare the images. Use the project's image comparator, or use `pixelmatch` with `pngjs` for PNG decoding and encoding. Pin their resolved versions in the validation project lockfile. Save the diff image and machine-readable result; wrap the library with an explicit nonzero exit when the agreed changed-pixel budget is exceeded. Never claim SSIM without calculating it. [Maestro CLI](https://docs.maestro.dev/maestro-cli/maestro-cli-commands-and-options), [flow parameters](https://docs.maestro.dev/maestro-flows/flow-control-and-logic/parameters-and-constants)

A useful initial visual gate, when the user has not specified one, is a project-local proposal: equal image dimensions, only documented dynamic regions masked, and a measured changed-pixel fraction reported before choosing a tolerance. Calibrate with repeated original-vs-original captures to identify rendering noise. Do not pick a forgiving threshold after seeing the candidate fail.

For one feature, retain:

```text
validation/<flow>/<platform>/
  original.png
  candidate.png
  diff.png
  mask.png               only if a mask was actually used
  result.json
```

`result.json` includes build IDs, fixture ID, evidence paths, comparison method, thresholds, passed/failed/blocked dimensions, and any accepted-difference IDs. Keep network/storage assertions distinct from the JUnit UI result.

## Pixelmatch settings that affect the verdict

Use equal-sized images and record `threshold` (per-pixel color sensitivity), `includeAA` (whether antialiasing differences count), and the separate allowed changed-pixel fraction. A `threshold` of `0.1` does **not** mean that 10% of the screen may differ. Keep the default whole-image counting mode when calculating `changedPixels / comparedPixels`; a windowed density result has a different denominator. `diffMask` controls output rendering, not exclusion regions. Apply documented exclusion regions to both inputs and exclude those pixels from the denominator; reject an empty comparison area. Never resize screenshots silently to make dimensions match. This computes pixel differences, not SSIM. [Pixelmatch API and PNG example](https://github.com/mapbox/pixelmatch)
