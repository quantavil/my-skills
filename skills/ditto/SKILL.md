---
name: ditto
description: Reconstruct an Android app in Flutter from an APK and runtime evidence, or review a Flutter clone for visual and behavioral parity. The supplied MCP backend supports Android emulators and ARM64 Flutter AOT analysis; iOS and other package formats need a separate capability contract.
---

# Ditto

Reproduce the original app accurately, one bounded phase at a time. Use original screenshots, behavior, and extracted assets to guide Flutter implementation. Static analysis suggests what to inspect; runtime evidence establishes what the user sees and can do.

Ditto contains its own Flutter guidance; no external skill is required. For Android Flutter originals, the four required MCP capabilities are JADX, Apktool, r2Flutter, and mobile-control. Keep these interfaces compulsory. Dart MCP is supplementary. Missing required capability is a specific blocker, not permission to pretend a different tool passed.

All runnable examples are in [commands](references/commands.md). Run bundled scripts through the locked `uv` project; use the mobile MCP to start and control the emulator. The same entry points work on Linux and Windows. See [toolchain](references/toolchain.md) for setup.

## Procedure

1. **Prepare the phase.** Pick a coherent feature or flow. Define its checkpoints, fixtures, actions, and expected results. Explore enough to settle questions that affect this phase; unrelated app questions can wait. Use [commands and contracts](references/commands.md) for the record format and [toolchain](references/toolchain.md) for host setup.
2. **Collect the original.** Reuse verified package analysis across phases. Search relevant strings, routes, assets, and native behavior through the analyzer MCPs. For declared paths, let the AI run guarded checkpoint batches with compact UI inspection. If navigation remains unclear, stop after at most two targeted attempts and offer the local human recorder for that declared path; its clicks still produce mobile-control receipts. Capture still images and useful XML, then freeze the pack. See [reverse engineering](references/reverse-engineering.md) and [runtime capture](references/runtime-workflow.md).
3. **Implement the phase.** Read relevant sections of [Flutter build](references/flutter-build.md); consult [stack](references/flutter-stack.md) only when choosing a dependency or architecture. Reuse extracted assets and measured design values. Implement the bounded phase together; avoid repeated capture after every widget edit. For rapid visual edits, keep one Android `flutter run` session alive, use hot reload, and control its running UI through mobile-control preview mode. Preview images are working views, never phase evidence.
4. **Compare the clone.** End preview, build a fresh APK, and replay the phase on a matching emulator environment through package-bound mobile capture. Batch compare all checkpoints; inspect one full-resolution `ORIGINAL APK | CLONE APK | DIFF` image per checkpoint. Review behavior from executed actions and resulting states. See [parity](references/parity.md).
5. **Correct what matters.** Fix failed checkpoints and recapture only those affected by the change. Pixel percentages prioritize inspection; the AI decides whether content, geometry, and behavior match. Do not repeat a valid accepted check merely to reduce a harmless metric difference. Read any phase file or revisit the original when a concrete uncertainty requires it.
6. **Finish the phase.** Run the relevant analysis/tests, build and capture the identified APK, then run automated readiness. Inspect actual exit results and screenshots before claiming success. Present the build, comparison report, and remaining decisions for one human review at phase end. Automated readiness is not human acceptance.

## Working rules

- Evidence lives in `phases/<phase-id>/original/`, `clone/`, and `diff/`. Scripts retain revisions and build identities; use the current report to navigate. Do not manually maintain duplicate indexes or rewrite tool receipts.
- Analyze a package once per analyzer version. Keep full exports in a shared ignored cache and reuse them across phases; phase packs retain receipts, indexes, and selected package resources. Search or read bounded excerpts instead of loading entire decompilations. A day passing or a server restart does not invalidate recorded analysis or screenshots.
- Check live device identity and environment when collecting new evidence. A command executing successfully does not prove that the intended UI state was reached; use visible UI targets or an explicit state check. Prefer compact UI inspection for navigation; open full screenshots when visual judgment is needed.
- Use screenshots for visible layout; XML is helpful when available. Persistence needs a write/restart/read sequence. A foreground activity dump is not proof of saved application data.
- Keep dependency mapping small. Local changes reopen affected checkpoints; uncertain impact or shared theme/native/dependency changes reopen the relevant broader scope. Retained checks identify their tested build; never call them fresh tests of the final APK.
- One agent can do the whole phase. Use additional agents only when available, permitted, and useful for isolated tasks. One owner controls each emulator and integrates shared code, builds, and verdicts. Independent phases may use separate devices and workspaces; never share a mutable capture session.
- Use still images, not video. Keep fixtures sanitized. Intentional product changes require existing authorization or an explicit proposal in the final review; harmless rendering variation is a semantic judgment.
