---
name: ditto
description: Use when replicating, migrating, or reconstructing an existing Android or iOS app (APK, IPA, AAB) into Flutter using binary or runtime evidence, extracting behavioral contracts, or verifying differential parity. Does not apply to generic Flutter development or the Ditto clipboard app.
---

# Ditto

Rebuild observable mobile behavior in maintainable Flutter code. Use the original app as a test oracle: apply controlled inputs, capture outputs, specify the contract, implement it, and compare both apps. Decompiled code supplies evidence, not a translation plan.

## When to Use

- Replicating, rewriting, or migrating an Android or iOS application into Flutter without complete original source code.
- Extracting behavioral, navigation, API, and storage contracts from APK, IPA, or AAB release binaries.
- Running differential parity tests between a reference binary application and a candidate Flutter build.

## When NOT to Use

- Generic greenfield Flutter app development where requirements are standard product specs (use standard Flutter tooling).
- Projects where full original Flutter or native source code is already available.
- Attempting 1:1 decompiled source recovery (Ditto reconstructs observable behavior, not identical decompiler output).
- Any task relating to the "Ditto" desktop clipboard manager application.

## Establish the task

Infer the requested mode from the user: evidence/specification only, a particular feature, full reconstruction, or parity review. Preserve the selected platform and existing project architecture. Flutter is the default target for reconstruction; honor an explicit alternative instead of silently changing it.

### The Device-First Mandate (Avoid the "Synthetic Parity Trap")

**CRITICAL RULE:** Statically analyzing decompiled code and relying on a few static screenshots is incomplete and creates the **"Synthetic Parity Trap"** — where 100% of unit/widget tests pass, but the reconstructed app is missing 60%+ of the real app's functions, sub-sheets, category pickers, date scrubbers, and dialogs.

1. **Advise and Request Device Connection Early:** At the start of any reconstruction or parity task, actively check `adb devices` and advise the user to connect a physical device or launch an emulator with the original app installed.
2. **Never Claim Parity From Unit Tests Alone:** Passing headless test suites (`flutter test`) only verifies assertions written by the engineer, NOT the actual oracle application. Full parity claims require live device or emulator runtime evidence (UIAutomator XML hierarchy dumps + interactive screenshots).
3. **Exhaustive Interactive Mapping:** When a device is connected, programmatically drive the original app (via ADB / Maestro / UIAutomator) to systematically open every tab, bottom sheet, sub-picker, drag-and-drop view, and settings dialog to capture the definitive ground truth.

Record the input path and hash, app version and identifier, target platforms, available source/symbols, runtime device, test environment, and requested flows in `spec/app.md`. Use available context before asking for missing information. If a live device is unavailable, proceed with static intake but mark runtime-dependent flows explicitly as `UNVERIFIED_STATIC_ONLY` — never claim full observed parity without runtime verification.

## Start with a concrete tool plan

Use [toolchain.md](references/toolchain.md) for commands, prerequisites, expected outputs, and primary-source links. Run the bundled `scripts/inventory.py` on an APK/IPA/AAB to obtain its hash, member inventory, framework indicators, and tool availability without extracting it. Use `scripts/validate_spec.py` to verify contract integrity, and `scripts/diff_screenshots.py` for visual parity checks.

| Source | Default evidence tools |
| --- | --- |
| Native Android | apkanalyzer + JADX + Apktool; ADB/Maestro for runtime; Ghidra (headless, optional) for native JNI |
| Flutter Android | Apktool + r2flutter; Blutter/flutterdec for specific unresolved AOT questions |
| Native iOS | Apple tools + ipsw; a compatible device/build for runtime; Ghidra/radare2 for native logic |
| Flutter iOS | iOS inventory + r2flutter; never assume Blutter supports iOS |
| Protocol / runtime internals | mitmproxy; Frida/Grapefruit when targeted inspection is needed |
| Candidate implementation | Flutter/Dart + Dart MCP when connected; Maestro for parity; Patrol for candidate system UI |

For a new networked Flutter app, default to Riverpod, Dio, and go_router; add Drift for relational/offline data. Read [flutter-stack.md](references/flutter-stack.md) before choosing dependencies: it includes exact package names, installation groups, secure storage, serialization, asset handling, native bridges, and test commands. Preserve a suitable existing stack.

Write the selected tools, actual versions/commits, input ABI/build, first command, expected output, and known blockers to `spec/toolchain.md`. Install only missing tools needed for the selected route. Do not re-research the whole catalog: use the linked instructions, checking compatibility for the actual input and installed release. Read [extraction.md](references/extraction.md) when source or runtime access is incomplete.

## Evidence to implementation

1. **Inventory.** Preserve the original artifact and record extraction tool versions, commands, and failures. Identify framework, ABI, resources, native dependencies, permissions, and accessible runtime environments. Prefer supplied source, build archives, API contracts, and matching symbols when available.
2. **Observe (Live Device First).** When an Android or iOS device/emulator is accessible, connect it immediately. Do not rely on a handful of static screenshots. Use ADB, UIAutomator (`adb shell uiautomator dump`), and automated traversal (e.g. Maestro) to capture full semantic UI trees, screen hierarchies, and pixel-accurate runtime screenshots of every tab, bottom sheet, sub-picker, drag-and-drop view, and dialog. If no device is available, use decompilation to extract strings/assets, but treat the result as `UNVERIFIED_STATIC_ONLY` until confirmed on a real device. Keep a coverage ledger of discovered states and blocked or untested paths; reachable paths are not the whole application.
3. **Specify.** Use [contracts.md](references/contracts.md) for provenance and per-screen contracts. Attach supporting evidence to material behavior claims and distinguish observed, inferred, unknown, and intentionally changed behavior. Resolve conflicting evidence by checking build, environment, and preconditions. A hash proves artifact identity, not truth or completeness.
4. **Implement one vertical feature.** Read its screen, flow, API, storage, and native contracts. Implement the smallest complete UI-to-data slice using project conventions. Add dependencies only for evidenced needs. Keep a small typed Kotlin/Swift adapter where platform behavior requires it. Preserve observable persistence semantics; identical database schemas or internal architecture are unnecessary unless interoperability explicitly requires them.
5. **Compare and correct.** Follow [parity.md](references/parity.md). Replay equivalent inputs against isolated original and candidate environments. Fix evidenced discrepancies, update the specification when observations change, and retain passing flows as regression checks.

Use runtime observations for visible behavior, network captures for protocol claims, and storage observations for persistence claims. Static resources and code can explain unobserved possibilities, but do not promote them to verified behavior. Never invent endpoints, validation rules, hidden screens, or successful test results to complete a specification.

Reproduce the observed design before applying a new design system. Treat screenshots as layout evidence, not a complete interaction model. Observe transitions in recordings when animation fidelity matters. Preserve text, accessibility semantics, keyboard behavior, safe areas, back navigation, and relevant platform differences.

## Scope and access

Use the app, accounts, assets, and services within the user's authorized scope. Test fixtures and permitted backend environments are part of intake. A request to reconstruct an app does not itself authorize production transactions, extracted secret reuse, or bypassing authentication. Prefer supported test login/debug builds; request user completion when MFA or CAPTCHA blocks access. Instrumentation or patched builds must be separately identified because they may change behavior.

Keep credentials and personal data out of durable specifications and source control. Store redacted captures as evidence, hashing those exact sanitized files. Do not ship inspection hooks or disabled TLS validation in the reconstructed app. If access prevents observation, continue independent work and report the precise gap rather than fabricate a replacement backend.

## Completion and handoff

Use the existing repository layout or create only the paths needed:

```text
input/                  original artifacts, excluded from normal source control
evidence/static/       extraction results and provenance
evidence/runtime/      sanitized observations and captures
oracle/flows/          replayable journeys and fixture references
spec/                  app, screens, API, navigation, storage, native contracts
flutter_app/           implementation, unless a project already exists
validation/            comparisons, gaps, accepted differences, reports
```

For a specification task, deliver evidence-linked contracts and coverage gaps. Use the concrete record examples in [contracts.md](references/contracts.md), not prose-only claims that evidence was collected. For implementation, deliver the feature code, relevant checks, replay results, and unresolved differences. For full reconstruction, report each in-scope flow and target platform separately. A successful build or aggregate similarity score does not establish production readiness.

Finish with what is implemented or specified, what was actually tested, and what remains blocked. Do not promise source recovery, a universal parity percentage, or a fixed timeline based on the supplied research estimates.

## Common Mistakes to Avoid

- **The Synthetic Test / False-Green Trap:** Relying solely on green unit/widget tests (`flutter test`) as proof of parity. Tests only verify the assertions the developer wrote, not the real app. Without live UI dumps and screenshot diffs against the oracle binary, major features, category pickers, and sub-sheets will be missed.
- **Relying solely on incomplete static captures:** A handful of random screenshots leaves 70% of the app's interactive states (dialogs, scrubbers, search bars, category pickers, reorderable views) unobserved. Always drive the live oracle on a connected device whenever available.
- **Treating decompiled code as a translation target:** Obfuscated Smali/Java from JADX provides evidence of endpoints and business logic, not code to copy 1:1 into Dart.
- **Running Ghidra on Flutter AOT or DEX:** Ghidra does not parse Flutter Dart AOT snapshots (use `r2flutter`/`blutter`) and is unnecessarily heavy for DEX (use JADX). Use Ghidra strictly for compiled C/C++ JNI `.so` libraries.
- **Unvalidated contracts & leftover placeholders:** Leaving `REPLACE_WITH_*` placeholders in `evidence/index.json` or claiming `observed: true` without recorded evidence. Run `python3 scripts/validate_spec.py` before handoff.
- **Confusing iOS simulator with device builds:** Attempting to install an ARM64 iOS device IPA into a simulator host.
- **Unmasked visual noise:** Failing to mask dynamic areas (clocks, timestamps, ads) before running visual regression diffs with `scripts/diff_screenshots.py`.
- **Prematurely claiming completion:** Never claim "all phases complete" or "100% parity" before running live side-by-side verification and screen-by-screen diffing against the reference binary.

