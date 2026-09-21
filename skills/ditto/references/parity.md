# Differential parity workflow

Define acceptance per in-scope flow and platform before measuring. Start with a representative vertical feature, establish reproducible capture, then expand. Keep validation output independent of the implementation's claims.

## The Ground-Truth Rule: Live Device vs Synthetic Traps

Never mistake candidate tests (`flutter test`) for parity verification. They check programmed expectations, not automatically what the original binary does. Optional [golden tests](flutter-build.md#golden-tests-and-batch-verification) check reviewed candidate renders; compare the original separately.

1. **Targeted runtime inspection:** Explore the active journey and its relevant branches. Capture screenshots, actions, and useful UI hierarchy or recordings. A UIAutomator dump may be incomplete for custom rendering; use another observation method instead of treating missing nodes as missing controls.
2. **Coverage is explicit:** Inventory top-level journeys once, then deepen only the active journey. Screenshots do not establish save/cancel, restart, validation, or hidden interactions. Do not estimate an unseen percentage of the app.
3. **Disconnected is not unobserved:** Preserve valid historical runtime evidence for its recorded build/environment. Mark new runtime-dependent claims without evidence as unknown (`UNVERIFIED_STATIC_ONLY` when supported only statically). Changed behavior requires new comparisons.

## Comparable runs

Use separate original and candidate installations or isolated emulators. Record both installed build identities, including splits, and any hot-reloaded source/session identity ([contracts.md](contracts.md)). Installed APK hashes alone do not identify hot-loaded code. Match OS, viewport/density, text scale, theme, locale, permissions, account/fixture state and network conditions. Restore authorized test fixtures between runs as needed; two sequential writes to a shared backend are not equivalent initial conditions. Never reset personal app data.

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

Visual metrics such as pixel differences support inspection; they do not replace behavior tests. Retain original/candidate images, exclusion regions, diff images, metric definitions, and thresholds. Exclude only documented nondeterminism, not inconvenient failures. Compare each target with its corresponding original platform; if no iOS original exists, state that the iOS implementation is adapted and lacks direct iOS parity evidence.

Canonicalize network data only where semantics permit it. Normalize redacted tokens or generated IDs consistently while preserving relationships. Do not sort meaningful arrays, discard meaningful headers, or remove timing/order that affects retry, signing, or idempotency. Compare response handling and side effects, not merely JSON key shapes. Different internal storage schemas are acceptable when the required observable semantics match.

## Checks and reporting

Finish related corrections in a task/phase, then batch affected formatting/analyzer/tests and emulator comparisons. Use goldens only when useful. Finish a lone remaining fix and check it directly; check earlier only if a failure blocks progress or the next edit needs that result. Run required project checks at the checkpoint; repeat only for relevant changes or unresolved failures. Build/run each required target on a capable host and report unavailable checks.

For each case record flow/state/platform, original and candidate evidence IDs, comparison method, result (`pass`, `fail`, `blocked`, `not_run`, or justified `not_applicable`), and discrepancy details. `python3 "$DITTO_SKILL/scripts/validate_spec.py" --json` reports required/passing/blocked/not-run counts and any critical case not currently passing, so skipped work cannot look like full coverage without reading the whole ledger by hand.

Critical authentication, payment, data-integrity, and other user-designated flows require their relevant checks to pass; mark them `"critical": true` in the coverage case. Do not hide a failure behind a weighted average. If the project requests a composite score, document denominators, weights, handling of untested cases, and critical-flow vetoes. There is no universal 95% release threshold.

For each gap preserve reproduction steps, expected and actual behavior, evidence, severity, and affected component. A case left as `"validation": "blocked"` must carry a nonempty `blocker` string — the validator rejects a blocked case with no reason on file. Correct evidence-backed implementation gaps; rerun affected comparisons. Revisit broader flows when shared behavior changes. If missing access or contradictory evidence prevents a fix, report it instead of looping without progress.

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

Check each exit code, JUnit result, and screenshot location. Register relevant screenshots with `ledger.py adopt` in place; do not capture a second copy solely to populate the ledger. A successful `takeScreenshot` does not compare images — use `diff_screenshots.py` below.

### Local AVD Replay & Visual Parity

When running on a local development host with an Android Virtual Device (AVD, e.g. `emulator-5554`), both original and candidate apps can be run sequentially or side-by-side on the same device. Standardize the device profile to match historical baselines (e.g. 1080x2400 @ 420 dpi).

Prefer available emulator/mobile tooling for capture and `ledger.py adopt` for registration. If it lacks necessary capture or provenance capabilities, explain that limitation and use the ADB-backed fallback:

```bash
python3 "$DITTO_SKILL/scripts/ledger.py" --project . capture \
  --serial "$ORIGINAL_SERIAL" --package "$ORIGINAL_PACKAGE" --role original \
  --flow open-settings --state settings.ready --fixture signed-in-test-account \
  --link-case --dimensions visual behavior
```

For a comparison against files already on disk, or against evidence captured elsewhere, use the visual parity tool directly. It needs no external binaries:

```bash
python3 "$DITTO_SKILL/scripts/diff_screenshots.py" \
  validation/original.png validation/candidate.png \
  --output-dir "validation/<flow>/<platform>/" \
  --top-mask 66 --bottom-mask 48 \
  --exclude 0,0,220,66 \
  --xml-original validation/original.xml --xml-candidate validation/candidate.xml \
  --case-id open-settings.settings.ready.android --no-montage
```

`--top-mask` / `--bottom-mask` exclude full-width bands; `--exclude x,y,w,h` excludes a rectangle and is repeatable. Measure regions and document why each is nondeterministic: excluded areas can hide defects. Excluded pixels leave the numerator and denominator. The tool writes `diff.png` and `result.json`; request `--montage` only for a composite you will inspect. With paired XML it reports bounding-box deltas, lists ambiguous labels instead of matching them, and treats hierarchy gaps as hints. Invalid inputs exit 2 (comparison unavailable), not a parity verdict. Capture matching native dimensions; never resize evidence to make it pass.

Retain referenced native captures and the current comparison's `diff.png` and `result.json`. The default omits a montage; pass `--montage` only when it will be reviewed. Keep one canonical set per checkpoint, not copies in multiple output directories:

```text
validation/<flow>/<platform>/
  diff.png
  composite_side_by_side.png  optional 3-panel review montage
  result.json                 metrics, status, and layout deltas
```

The screenshot tool's `result.json` contains visual metrics only. Feed it to `ledger.py comparison --supporting` (see [contracts.md](contracts.md)), which writes the actual pass/fail comparison record and updates the coverage case. Keep network/storage assertions distinct from the visual result.

## Measure workflow efficiency

Run this only when evaluating a workflow change or when requested. Ordinary journeys need no extra metrics file. Add a compact row to the existing progress/report record:

`task | skill revision | model/settings | uncached input / cached input / output tokens | billed cost | elapsed time | correction cycles | required checks passed/total | unresolved defects`

Use actual usage exports when available; mark unavailable values unknown. Word counts, tool calls and LOC are proxies, not token/cost measurements. Count the whole task, including reference loads, tool output, retries and delegated work. For cost, use actual billed cost or the applicable rates for the recorded model/settings and usage categories; do not assume cached tokens cost the same as uncached input.

Compare the old and new workflows on equivalent tasks from the same starting revision, fixtures, acceptance criteria and environment. Use a small representative set (for example UI repair, async behavior and persistence), keep model/settings fixed, and repeat paired runs when feasible. Include failed runs; report median cost/time and the range, not just the best attempt. Preserve user-testing and required parity gates across both variants.

Accept a cheaper workflow only when correctness and required coverage remain at least as good, without increasing unresolved defects. Report measured differences with their sample size and limitations. A shorter entry file or fewer handwritten lines alone cannot establish an AI-bill reduction. Reuse normal task artifacts and keep only the compact comparison summary; do not create duplicate builds/captures solely for reporting.

## User checkpoint and regression

Offer one runnable build with its identity, a short action/expected-result checklist, and known differences. Include cancel/back and reopen/restart where relevant. Record user feedback against that build. User acceptance does not convert missing or failed comparisons into passes; a waiver is distinct from acceptance.

After a shared model, navigation, theme or persistence change, mark affected previous comparisons stale (`not_run`) until the next relevant verification batch. Preserve accepted/referenced evidence. Keep exploratory captures, intermediate pulls/dumps and obsolete generated previews in task-owned temporary storage; remove only unreferenced scratch files you created. Keep one progress file and canonical contracts/results; do not create duplicate plans or status files. Resume from `spec/progress.md`. User checkpoints test the delivered journey, not permission for already authorized work.

## Visual comparison settings that affect the verdict

`diff_screenshots.py` uses a YIQ colour-delta threshold; it is not a complete pixelmatch implementation (for example, it does not reproduce its anti-aliasing handling). `--threshold` is per-pixel sensitivity; `--max-diff-ratio` is the allowed fraction of changed pixels. Excluded pixels leave the denominator, and a fully excluded image is rejected. Exclusions can hide defects inside their region: justify each mask. Never resize screenshots to force a match. This computes pixel differences, not SSIM.

## Fast laptop iteration

Use Android on the laptop as the Android parity target. Browser/desktop previews
are optional layout aids, not proof of Android rendering or native behavior.

1. Discover/reuse a compatible emulator through available emulator/mobile tools.
   Prefer those tools for installation, interaction and capture. If unavailable
   or missing a required capability, explain why the shell fallback is needed. The
   bundled `scripts/emulator_manager.sh start-headless` supports `DITTO_AVD`
   (required — there is no default AVD), `DITTO_EMULATOR_PORT`, `DITTO_BOOT_TIMEOUT`,
   `DITTO_GPU`, `DITTO_ADB` and `DITTO_EMULATOR`. It targets one serial, checks
   its AVD identity, uses software rendering headless unless `DITTO_GPU` says
   otherwise, and makes a bounded attempt to wait for boot-animation completion.
   Confirm the app is interactive before capture. Run `emulator_manager.sh check` to see what it
   resolved. Launch it asynchronously when booting takes time so progress
   reporting continues.
2. Install the original once and candidate once with preferred tooling; the
   fallback is `emulator_manager.sh install <apk> [package]`. It checks AVD identity
   and preserves permission prompts; `--grant-permissions` is explicit fixture setup.
   Keep separate package IDs;
   if IDs collide, use separate emulators. Never repeatedly uninstall to iterate.
3. Keep `flutter run -d <serial>` attached. Use hot reload for Dart UI edits,
   hot restart for initialization changes, and full restart/rebuild for native
   code or plugin changes. Hot reload preserves state; it is not a cold-start test.
4. Capture fresh original and candidate baselines on the same emulator with
   matching resolution, density, OS, font scale, locale, navigation mode and
   keyboard. Capture tools record some of these facts; record navigation mode,
   keyboard and any other missing settings explicitly. A 420-dpi
   emulator cannot directly validate 400-dpi phone captures. Retain those
   phone captures as historical evidence; do not rescale them.
5. Replay deterministic fixtures (dates, records, theme, permission state) for
   the active checkpoint. Keep isolated snapshot/fixture state and record resets;
   candidate-only debug navigation must not ship or replace real journey replay.
6. Collect discrepancies, finish the related fixes in the active phase, hot reload,
   then run affected tests and recapture affected states as one batch. Check a
   single remaining fix directly; check earlier when further work depends on the
   result. Record modified-runtime source/session identity during hot reload.
   Compare transition recordings separately. Before acceptance, build/install a
   distributable APK and perform required fresh-process/restart checks.

Use a physical phone for milestone checks of OEM keyboard/insets, notifications,
permissions and performance. Missing phone access leaves those checks pending;
continue emulator work. Never label an emulator check as physical-device evidence.
