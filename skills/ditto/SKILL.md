---
name: ditto
description: Use when reconstructing an Android or iOS app from APK, IPA, AAB, or runtime evidence, or reviewing a Flutter clone for behavioral and visual parity. Not for ordinary Flutter development, available full-source migrations, or the Ditto clipboard app.
---

# Ditto

Reconstruct observable behavior using the original as the oracle. Work in manageable journeys with human review at meaningful checkpoints. Decompiled code informs contracts; candidate tests cannot establish original behavior.

Scale the workflow to the task. A small repair needs the affected evidence and checks, not a new plan, graph or full discovery pass. Use these as working defaults; keep firm boundaries around honest evidence, user data and requested scope.

## Resume and select tools

Infer evidence-only, reconstruction, or parity-repair mode. Preserve requested platforms, architecture and authorized differences. Resolve conflicting requirements explicitly.

Read `spec/progress.md` if present, then the active contract and relevant evidence. Reuse results after verifying build/environment identities. Set `DITTO_SKILL` to this directory. For new projects, run `python3 "$DITTO_SKILL/scripts/ledger.py" --project . init`; record artifact identity/scope in `spec/app.md` and briefly inventory journeys.

Prefer working local emulator/mobile tooling; use ADB when it is the practical available path, without adding an approval step for ordinary authorized testing. Android helpers support Linux and Windows; use the shell examples in the runtime reference. Use corresponding iOS tools on a capable host; physical devices serve requested/hardware-specific checks. Disconnection does not invalidate historical evidence.

## Journey loop

1. **Select:** Define one outcome, checkpoints, branches and required comparison dimensions, including relevant restart effects. Inventory every visible choice in the active journey; each needs an observed destination or explicit gap. Do not silently narrow a whole journey to its default branch. Keep future journeys as backlog entries.
2. **Observe:** Replay the original. Register existing captures with `ledger.py adopt`, or use `capture` for ADB-backed collection. Record setup/actions, fixture, build/runtime identity and environment. Sparse hierarchies need screenshots/checkpoints. Inspect static code for specific questions; preserve unknowns.
3. **Build:** Implement the smallest complete slice within existing boundaries. Map distinctive artwork/fonts to source assets or explicit gaps before replacing them. Authorized copy changes do not authorize artwork removal. Reuse confirmed tokens and convert capture pixels to logical dimensions. Preserve working libraries; add dependencies/code generation only when they remove needed complexity. Goldens and theme extraction are optional.
4. **Compare:** Finish related corrections, then batch affected tests and emulator recaptures. Replay matching fixtures/actions against both apps. Use `diff_screenshots.py` and `ledger.py comparison`; compare relevant animations with paired recordings, not settled screenshots. Keep visual, behavior, persistence and relevant platform verdicts separate. Inapplicable dimensions need reasons; required dimensions cannot disappear. Invalidate affected accepted comparisons after shared changes. Screenshots or green candidate tests alone are not parity.
5. **Human checkpoint:** Offer a runnable identified build early enough for useful feedback, with a short review checklist, evidence links and gaps. Human review is part of each meaningful implemented journey, especially appearance, animation and interaction feel. Keep the journey pending until feedback arrives; silence or an automated review is not acceptance. Continue already-authorized independent work while waiting. Use feedback to focus corrections and avoid speculative polish or repeated broad tests; retain checks for saving, data integrity and affected behavior. A waiver is not user testing.

Evidence-only work ends with contracts/gaps. Missing runtime access permits evidence-backed implementation, never invented passes. Finish useful active work and record the blocked checkpoint/reason.

## Efficiency and retention

- Complete a lone remaining fix and check directly. Check earlier only when a failure blocks progress or the next edit depends on its result. Run required checks at checkpoints; repeat for relevant changes, failures or new evidence.
- Keep Flutter attached; hot reload related edits together. Record loaded-source/session identity separately from installed APK hashes. Final comparisons use a fresh installed build and required restart checks.
- Use the [runtime workflow](references/runtime-workflow.md) for fast replay, Linux/Windows and Intel/NVIDIA setup, small review previews and commands. Prefer multiagent work when the harness supports it and independent subtasks exist; keep tiny or sequential tasks local. One owner controls each device/session.
- Search before reading; load one relevant reference below, bounded excerpts and tool summaries. Reuse inventories; request full member lists only for a specific question. Exclude generated/vendor files from routine context; inspect targeted sections when debugging requires them.
- Keep canonical contracts/coverage, one progress file, relevant source/assets, referenced evidence, results and user decisions. Temporary captures/dumps/pulls belong in task-owned temporary storage. Remove only your unreferenced scratch files; preserve user and accepted evidence. Generate montages only for review.
- Update progress at checkpoints: journey/stage, identities, result links, blockers, user decision, next command. Measure efficiency only when requested or evaluating workflow changes; use the [measurement procedure](references/parity.md#measure-workflow-efficiency).

## References: load on demand

| Need | Reference/tool |
| --- | --- |
| Binary/tool choice | [toolchain.md](references/toolchain.md), `inventory.py` |
| Missing access/source | [extraction.md](references/extraction.md) |
| Reverse a specific behavior | [reverse-engineering.md](references/reverse-engineering.md) |
| Dependency decision | [flutter-stack.md](references/flutter-stack.md) |
| Measurements/async implementation | [flutter-build.md](references/flutter-build.md) |
| Evidence/coverage records | [contracts.md](references/contracts.md), `ledger.py` |
| Comparison/measurement | [parity.md](references/parity.md), `diff_screenshots.py` |

At a journey handoff or final completion, run `python3 "$DITTO_SKILL/scripts/ditto.py" check` from the project root. Intermediate repairs need affected checks, not repeated full-ledger hashing. Use `report` for current counts and optional `graph` for a Mermaid view of recorded transitions. These validate records, not truth or completeness; reassess unsupported legacy passes. Unlisted branches and missing assets remain discovery responsibilities. Derive completion claims from current evidence, never test counts or an earlier prose summary.

Use authorized accounts/services; never reset personal app data. Sanitize credentials and label instrumentation. Never ship inspection hooks or disabled TLS validation. Report executed/required comparisons, actual user-testing status and gaps; no invented hashes, universal parity percentage or source-recovery promises.
