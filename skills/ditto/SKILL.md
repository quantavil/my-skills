---
name: ditto
description: Reconstruct an Android app in Flutter from an APK and runtime evidence, or review a Flutter clone for visual and behavioral parity. The supplied MCP backend supports Android emulators and ARM64 Flutter AOT analysis; iOS and other package formats need a separate capability contract.
---

# Ditto

Reconstruct one bounded phase at a time. Static analysis points to what to inspect; captured original behavior and current comparisons establish what the app shows and does.

For Android Flutter originals, JADX, Apktool, r2Flutter, and mobile-control MCP are required. Dart MCP is supplementary. If a required capability is missing or incompatible, report the specific blocker; do not claim another tool satisfies it. Ditto contains its own Flutter guidance. Runnable examples are in [commands](references/commands.md); host setup is in [toolchain](references/toolchain.md).

## Procedure

1. **Prepare the phase.** Analyze the original package once per analyzer version and reuse its verified export. Map coarse phases, choose one coherent flow, and prepare deterministic fixtures plus a short checklist of checkpoints and capture conditions. Resolve only questions that affect this phase. See [reverse engineering](references/reverse-engineering.md).
2. **Capture the original.** Prepare the starting fixture and give the human the checklist. The human navigates the original in the mobile-control browser recorder; it records actions and candidate screenshots/XML automatically, with **Save screen** available as an optional bookmark. After **Done**, inspect the candidates and select trustworthy evidence for each checkpoint. A replay is not required. Freeze the selected original before clone comparison. See [runtime workflow](references/runtime-workflow.md).
3. **Implement in a batch.** Follow the relevant [Flutter build](references/flutter-build.md) guidance and consult the [stack](references/flutter-stack.md) only when choosing a dependency or architecture. Reuse confirmed assets and measured values. Keep `flutter run` open for related visual edits and use hot reload for preview; preview images are not evidence. When the batch is ready, build a fresh local debug APK with `flutter build apk --debug`.
4. **Capture and compare the clone.** Open the comparison browser with the selected original screenshot beside the live clone. The human navigates the clone, optionally adds a note, and uses **Capture & compare** on each settled checkpoint. **Next** advances; **Done** ends the session. Each successful capture updates the current clone evidence and diff. Inspect every current triptych and assess behavior from the recorded actions and resulting states. See [parity](references/parity.md).
5. **Correct and review.** Fix related failures together, then recapture only affected checkpoints. A recapture clears the affected stale verdict. Repeat until current comparisons are ready. Run the relevant project checks and automated readiness against the current build and evidence; inspect their actual results. Present the current build, report, and unresolved differences for final human review. Readiness and human-operated capture are evidence, not approval.

## Evidence rules

- Current files live under `phases/<phase-id>/original/`, `clone/`, and `diff/`. The script maintains the current phase metadata and manifests. Successful captures overwrite current checkpoint files; do not keep manual revision histories or duplicate indexes.
- A frozen original changes only through deliberate replacement. Replacement invalidates comparisons for affected checkpoints. Clone recapture also invalidates that checkpoint's verdict; retained verdicts keep the build identity they actually tested.
- Preserve MCP provenance, package/build identity, device environment, and recorded input context. A command or tap succeeding proves transport, not that the expected state appeared. Inspect the captured image and observed state.
- Only one human or agent controls a device session at a time; keep each capture flow on the browser recorder so its actions and images share MCP provenance.
- Screenshots establish visible layout. XML can clarify hierarchy. Screenshots alone do not prove navigation, persistence, network behavior, or accessibility; use the corresponding recorded actions, state checks, or semantics evidence.
- Keep phase fixtures sanitized and deterministic. Do not infer privacy or product differences; use only differences already authorized for the project.
- Build only debug APKs locally. Never run a local release APK build or `assembleRelease`; CI may build release APKs.
