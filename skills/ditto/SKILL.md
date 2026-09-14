---
name: ditto
description: Reconstruct an existing Android or iOS app in Flutter using an APK, IPA, app bundle, or running app as evidence. Use for mobile app replication, binary-to-Flutter migration, behavioral specification extraction, and differential parity testing. Does not recover original source or apply to generic Flutter development or the Ditto clipboard app.
---

# Ditto

Rebuild observable mobile behavior in maintainable Flutter code. Use the original app as a test oracle: apply controlled inputs, capture outputs, specify the contract, implement it, and compare both apps. Decompiled code supplies evidence, not a translation plan.

## Establish the task

Infer the requested mode from the user: evidence/specification only, a particular feature, full reconstruction, or parity review. Preserve the selected platform and existing project architecture. Flutter is the default target for reconstruction; honor an explicit alternative instead of silently changing it.

Record the input path and hash, app version and identifier, target platforms, available source/symbols, runtime device, test environment, and requested flows in `spec/app.md`. Use available context before asking for missing information. Start useful static intake even if a device or test account is unavailable; mark runtime-dependent work blocked and do not claim observed parity.

## Start with a concrete tool plan

Use [toolchain.md](references/toolchain.md) for commands, prerequisites, expected outputs, and primary-source links. Run the bundled `scripts/inventory.py` on an APK/IPA/AAB to obtain its hash, member inventory, framework indicators, and tool availability without extracting it.

| Source | Default evidence tools |
| --- | --- |
| Native Android | apkanalyzer + JADX + Apktool; ADB/Maestro for runtime |
| Flutter Android | Apktool + r2flutter; Blutter/flutterdec for specific unresolved AOT questions |
| Native iOS | Apple tools + ipsw; a compatible device/build for runtime |
| Flutter iOS | iOS inventory + r2flutter; never assume Blutter supports iOS |
| Protocol / runtime internals | mitmproxy; Frida/Grapefruit when targeted inspection is needed |
| Candidate implementation | Flutter/Dart + Dart MCP when connected; Maestro for parity; Patrol for candidate system UI |

For a new networked Flutter app, default to Riverpod, Dio, and go_router; add Drift for relational/offline data. Read [flutter-stack.md](references/flutter-stack.md) before choosing dependencies: it includes exact package names, installation groups, secure storage, serialization, asset handling, native bridges, and test commands. Preserve a suitable existing stack.

Write the selected tools, actual versions/commits, input ABI/build, first command, expected output, and known blockers to `spec/toolchain.md`. Install only missing tools needed for the selected route. Do not re-research the whole catalog: use the linked instructions, checking compatibility for the actual input and installed release. Read [extraction.md](references/extraction.md) when source or runtime access is incomplete.

## Evidence to implementation

1. **Inventory.** Preserve the original artifact and record extraction tool versions, commands, and failures. Identify framework, ABI, resources, native dependencies, permissions, and accessible runtime environments. Prefer supplied source, build archives, API contracts, and matching symbols when available.
2. **Observe.** Capture one representative journey before expanding exploration. Record preconditions, actions, screenshots, semantic UI trees where exposed, navigation, network effects, persistence, and native side effects. Use deterministic fixtures and replayable flows. Keep a coverage ledger of discovered states and blocked or untested paths; reachable paths are not the whole application.
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
