# Differential parity workflow

Define acceptance per in-scope flow and platform before measuring. Start with a representative vertical feature, establish reproducible capture, then expand. Keep validation output independent of the implementation's claims.

## The Ground-Truth Rule: Live Device vs Synthetic Traps

Never mistake synthetic test suites (`flutter test`) for parity verification. A green test suite only proves the candidate matches what the engineer programmed into the test, not what the oracle binary actually does.

1. **Targeted runtime inspection:** Explore the active journey and its relevant branches. Capture screenshots, actions, and useful UI hierarchy or recordings. A UIAutomator dump may be incomplete for custom rendering; use another observation method instead of treating missing nodes as missing controls.
2. **Coverage is explicit:** Inventory top-level journeys once, then deepen only the active journey. Screenshots do not establish save/cancel, restart, validation, or hidden interactions. Do not estimate an unseen percentage of the app.
3. **Disconnected is not unobserved:** Preserve valid historical runtime evidence for its recorded build/environment. Mark new runtime-dependent claims without evidence as unknown (`UNVERIFIED_STATIC_ONLY` when supported only statically). Changed behavior requires new comparisons.

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

Check each exit code, JUnit result, and actual screenshot location. A successful `takeScreenshot` does not compare the images.

### Local AVD Replay & Visual Parity

When running on a local development host with an Android Virtual Device (AVD, e.g. `emulator-5554`), both original and candidate apps can be run sequentially or side-by-side on the same device. Standardize the device profile to match historical baselines (e.g. 1080x2400 @ 420 dpi).

Use the bundled visual parity helper:
```bash
python3 "$DITTO_SKILL/scripts/diff_screenshots.py" \
  validation/original.png \
  validation/candidate.png \
  --output-dir validation/<flow>/<platform>/ \
  --mask-system-bars \
  --xml-original validation/original.xml \
  --xml-candidate validation/candidate.xml
```

The helper masks the explicitly selected top/bottom rows, computes changed pixels
against the unmasked area, and emits a three-panel montage and optional XML deltas.
Specify measured `--top-mask` / `--bottom-mask` values: the defaults (110/80)
are examples, not device-independent safe areas. Never mask app layout errors.
Missing metrics, invalid dimensions, failed masking, or a missing diff artifact
must fail the comparison; exit code alone is not a parity verdict. A tool error
is an unavailable comparison, not evidence of a visual mismatch or match.
XML matches are supporting hints: repeated labels can be ambiguous and absent
nodes do not establish that a rendered control is missing.

For one feature, retain:

```text
validation/<flow>/<platform>/
  original.png
  candidate.png
  diff.png
  composite_side_by_side.png  3-panel visual review montage
  result.json                 metrics, status, and layout deltas
```

The screenshot helper's `result.json` contains visual metrics only. Link it as a supporting artifact from the journey's `comparison.json`, using the schema in [contracts.md](contracts.md). That record links both builds through evidence IDs, the fixture, replay steps, and required dimension results. Keep network/storage assertions distinct from the JUnit UI result.

## User checkpoint and regression

Offer one runnable build with its identity, a short action/expected-result checklist, and known differences. Include cancel/back and reopen/restart where relevant. Record user feedback against that build. User acceptance does not convert missing or failed comparisons into passes; a waiver is distinct from acceptance.

After a shared model, navigation, theme, or persistence change, mark affected previous comparisons stale (`not_run`) until rerun; retain historical artifacts. Resume from `spec/progress.md` rather than repeating full intake. Do not request confirmation again for an already authorized action; the user checkpoint is testing the delivered journey.

## Pixelmatch settings that affect the verdict

Use equal-sized images and record `threshold` (per-pixel color sensitivity), `includeAA` (whether antialiasing differences count), and the separate allowed changed-pixel fraction. A `threshold` of `0.1` does **not** mean that 10% of the screen may differ. Keep the default whole-image counting mode when calculating `changedPixels / comparedPixels`; a windowed density result has a different denominator. `diffMask` controls output rendering, not exclusion regions. Apply documented exclusion regions to both inputs and exclude those pixels from the denominator; reject an empty comparison area. Never resize screenshots silently to make dimensions match. This computes pixel differences, not SSIM. [Pixelmatch API and PNG example](https://github.com/mapbox/pixelmatch)

## Fast laptop iteration

Use Android on the laptop as the Android parity target. Browser/desktop previews
are optional layout aids, not proof of Android rendering or native behavior.

1. Discover the SDK, AVD and serial; reuse a running compatible emulator. The
   bundled `scripts/emulator_manager.sh start-headless` supports `DITTO_AVD`,
   `DITTO_EMULATOR_PORT`, `DITTO_BOOT_TIMEOUT`, `DITTO_ADB` and `DITTO_EMULATOR`.
   It targets one serial, checks its AVD identity and bounds boot waits. Launch
   it asynchronously when booting takes time so progress reporting continues.
2. Install the original once and the candidate once. Keep separate package IDs;
   if IDs collide, use separate emulators. Never repeatedly uninstall to iterate.
3. Keep `flutter run -d <serial>` attached. Use hot reload for Dart UI edits,
   hot restart for initialization changes, and full restart/rebuild for native
   code or plugin changes. Hot reload preserves state; it is not a cold-start test.
4. Capture fresh original and candidate baselines on the same emulator with
   matching resolution, density, OS, font scale, locale, navigation mode and
   keyboard. A 420-dpi emulator cannot directly validate 400-dpi phone captures.
   Retain those phone captures as historical evidence; do not rescale them.
5. Replay deterministic fixtures (dates, records, theme, permission state) for
   the active checkpoint. Keep isolated snapshot/fixture state and record resets;
   candidate-only debug navigation must not ship or replace real journey replay.
6. Capture at native resolution, compare, fix the measured discrepancy, hot reload,
   and recapture only affected states. Compare transition recordings separately;
   a still frame cannot establish animation timing. Run a fresh process/restart
   check before acceptance and build a distributable APK at the checkpoint.

Use a physical phone for milestone checks of OEM keyboard/insets, notifications,
permissions and performance. Missing phone access leaves those checks pending;
continue emulator work. Never label an emulator check as physical-device evidence.
