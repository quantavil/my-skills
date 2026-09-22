# Practical runtime workflow

Start with one device, the active journey and existing tools. Reuse the project's
records. Add replay automation or a graph when repeated work or branching makes
it useful; a small correction can go straight to an affected check.

## Establish once, invalidate deliberately

Reuse a compatible running emulator. Check CPU acceleration and APK/system-image
ABI compatibility before blaming rendering: KVM on Linux, a working Windows
hypervisor on Windows. Android recommends WHPX on Windows; use the emulator's
`-accel-check` to inspect availability rather than assuming Linux `/dev/kvm` rules
apply. [Android acceleration](https://developer.android.com/studio/run/emulator-acceleration).
Intel UHD and NVIDIA both start with the
emulator's `auto` graphics selection, including headless runs. Inspect the actual
renderer and app output: GPU presence does not prove GPU use. Use `DITTO_GPU` only
for a demonstrated driver/backend problem; consult the installed emulator's help
for supported modes. Headless does not inherently require software rendering.
Keep the working backend; do not benchmark every backend on every journey.

Record device, build/runtime, renderer, display, locale, font scale, theme and
fixture facts at batch entry. Reuse verified facts within that controlled batch;
recheck after installs, resets, configuration changes, interruptions or unexpected
state. Hot reload changes source identity even when the installed APK is unchanged.
The fallback `ledger.py capture` still recollects identity per capture; do not claim
it caches sessions. Preferred capture plus `adopt` can reuse verified batch facts.
Keep final original/candidate comparisons on matching environments. Never lower
the emulator resolution just to reduce image tokens.

## Explore once, replay with assertions

Observe unknown states interactively. Save known journeys in the project's existing
runner (Maestro when already suitable). Confirm the entry state, then check the
expected result of each transition with a bounded wait; the previous successful
check can establish the next starting state. Use an
appropriate visual/stability check where accessibility nodes are sparse. A static
tree alone does not establish completed rendering or a finished network operation.
Keep original animations enabled when measuring motion.

Reuse mapped coordinates only while viewport, scroll, keyboard, overlays and layout
remain compatible. Obtain a hierarchy for unknown controls or diagnosis, not every
tap. In the fallback, `ledger.py capture --no-hierarchy` skips unnecessary dumps.
Capture one settled image per required checkpoint and reuse it for checks and
registration. Do not take a second image solely for a global-state recheck.
Batch replay and local analysis, not unchecked taps. On failure, stop that sequence,
save the failed checkpoint and inspect the cause. A transient read can be retried;
check state before repeating a tap or a save that may already have succeeded.

Restore only authorized test fixtures. Snapshots can shorten setup but cannot prove
the navigation, cold start or persistence they bypass. Validate snapshot compatibility
after environment/build changes. Run required end-to-end paths before acceptance.

## Measure instead of guessing

Keep native captures for local comparison. For AI review, default to a preview about
540 pixels wide, preserving aspect ratio; inspect native crops for uncertain text,
assets or geometry. Previews are disposable derivatives, never parity baselines.
Lower JPEG quality alone is not a reliable token-saving measure. Do not install an
image stack just to produce a preview when existing tooling can supply it.

Check each distinctive image and important control region, not only a whole-screen
pixel ratio. Measure overlay bounds, padding, text wrapping, pointer and target
alignment in native pixels, then convert using the recorded capture scale. Record
expected/actual measurements and tolerances in the existing screen contract.
Use hierarchy bounds where available; visual inspection still matters for custom
rendering, wrong artwork and clipping. No "looks close" pass without supporting
comparison. Never loosen thresholds or mask defects to obtain a pass.

Reuse valid original observations. Finish related changes, then check affected
states together. Shared component/token/asset changes invalidate every dependent
state; broaden checks if dependencies are uncertain. Keep required final restart
and packaged-build checks. Time slow commands only when diagnosing performance;
include retries and agent work when measuring improvements.

## Commands and tracking

Use Python 3. Run from the project root with `DITTO_SKILL` set to the installed
skill directory. Linux shell:

```bash
python3 "$DITTO_SKILL/scripts/ditto.py" check
python3 "$DITTO_SKILL/scripts/ditto.py" report
python3 "$DITTO_SKILL/scripts/ditto.py" graph
```

Windows PowerShell (set `$env:DITTO_SKILL` to the actual installation directory):

```powershell
py -3 "$env:DITTO_SKILL/scripts/ditto.py" check
py -3 "$env:DITTO_SKILL/scripts/ditto.py" report
py -3 "$env:DITTO_SKILL/scripts/ditto.py" graph
```

Use `python` instead of `py -3` if that is the available Python 3 interpreter.
Other Python helper examples translate the same way. The portable launcher is
`scripts/emulator_manager.py`: run `check`, then `start` (or `start-headless` when
needed) with `DITTO_AVD` set to an existing AVD. Linux uses `export DITTO_AVD=...`;
PowerShell uses `$env:DITTO_AVD = '...'`. It resolves standard SDK locations and
`.exe` tools on Windows; paths containing spaces are supported. The older `.sh`
launcher remains for existing Linux callers. Native Windows does not need WSL.

`check` verifies referenced files and record integrity at handoff. `report` emits
lightweight structured record validation without rehashing evidence. `graph` prints Mermaid from coverage cases and optional
`transitions`; it never invents sequential edges from file order. Commands are
read-only; exit 0 means the requested check/render succeeded, 1 record-validation
failure, 2 invocation/input failure. `graph` checks graph structure only; a zero
exit is not journey acceptance. Existing `ledger.py`, replay runner
and `diff_screenshots.py` remain the capture/comparison interfaces; consult their
`--help` rather than guessing flags. Keep logs on disk and return concise failures.

When a graph helps a branching journey, add `transitions` to `spec/coverage.json`:

```json
{"transitions": [{"from": "existing-case-id", "action": "Observed choice", "to": "destination-case-id"}]}
```

Use existing case IDs, including explicit not-run cases for unknown destinations.
The generated graph displays recorded verdicts, not independent verification.
Keep observed, implemented, comparison and user acceptance separate in coverage.
Reconcile visible choices with recorded transitions manually during discovery;
graph validation cannot discover an omitted UI choice. Keep asset mappings and
measurement details in screen contracts rather than duplicating them in a graph.

## Multiagent execution when available

Prefer bounded independent work when the harness supports delegation: asset discovery,
implementation in disjoint files, or review of saved evidence can overlap device
replay. Give each worker scope, evidence IDs, owned outputs and a stopping condition.
Share bounded artifacts rather than the entire repository/conversation by default.

Exactly one owner controls a device and attached Flutter session. Serialize install,
build and canonical ledger writes; workers return separate findings for integration.
Do not let reviewers navigate the device while another worker captures it. Verify
worker claims against artifacts. Small tasks stay local. More emulators require
isolated fixtures and measured CPU/RAM/GPU headroom; NVIDIA alone does not justify
parallel devices. When delegation is unavailable, execute the same bounded tasks
sequentially. Report elapsed-time and token tradeoffs without promising a speedup.
