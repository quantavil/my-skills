---
name: ditto
description: Use when reconstructing an Android or iOS app from APK, IPA, AAB, or runtime evidence, or reviewing a Flutter clone for behavioral and visual parity. Not for ordinary Flutter development, available full-source migrations, or the Ditto clipboard app.
---

# Ditto

Reconstruct observable behavior using the original app as the oracle. Deliver one complete, compared, user-tested journey at a time. Decompiled code informs contracts; candidate tests cannot establish original behavior.

## Start or resume

Infer mode: evidence-only, reconstruction, or parity repair. Preserve the requested platform, architecture, and authorized differences. Resolve conflicts such as offline-only versus server-backed features explicitly.

Read `spec/progress.md` if present, then only the active journey's contract and linked evidence. Check changed files/build identity before trusting previous results. For a new task, record artifact hash/version, platform, runtime access, and scope in `spec/app.md`; inventory top-level journeys briefly. Check Android access with `adb devices` (prefer an available local Android emulator; discover and explicitly target its serial) or the corresponding iOS tools. Existing valid runtime captures remain evidence when disconnected; missing observations remain unknown.

## Journey loop

1. **Select:** Choose one user outcome, including its UI, data, and restart effects. List its checkpoints, relevant branches, and acceptance criteria. Keep future journeys as short backlog entries.
2. **Observe:** Replay this journey on the original. Capture meaningful states, interactions, back/cancel, and persistence. Use screenshots plus hierarchy/recordings where useful; Flutter/custom-drawn UI may lack useful hierarchy. Inspect static code only for specific unanswered questions. Record unknowns rather than invent behavior.
3. **Build:** Implement the smallest complete slice within existing boundaries. Add only dependencies needed by this slice. Keep domain logic separate from widgets. Use focused tests tied to observed expectations; refactor touched code when responsibility boundaries demand it.
4. **Compare:** Replay equivalent fixtures/actions against both apps. Generate 3-panel visual composites (`[Original | Candidate | Diff]`), mask dynamic system bars, and map XML hierarchy bounding-box deltas via `diff_screenshots.py`. Record visual, behavioral, persistence, and relevant platform results separately. Fix discrepancies and rerun affected checks. Shared changes invalidate affected accepted journeys. Passing unit tests or taking screenshots alone is not parity.
5. **User checkpoint:** Deliver a runnable build, short test checklist, known gaps, and evidence links. Record actual feedback; fix and retest. Advance after comparisons pass and the user accepts. If the user explicitly waives testing, record that decision without calling it user-tested. Silence is pending. While waiting, allow bounded evidence collection but no implementation of another journey.

Evidence-only tasks finish with contracts/gaps and need no candidate build or user-testing checkpoint. Missing runtime access does not prevent evidence-backed implementation; it prevents claiming unexecuted comparisons passed. Finish useful work on the active journey and report its blocked checkpoint.

If the user explicitly redirects work to another journey, record the pending checkpoint and follow that direction. Redirection is not acceptance or a testing waiver.

## Keep work fast

- For laptop Android iteration, use the [warm emulator loop](references/parity.md#fast-laptop-iteration): install once, keep Flutter attached, hot reload UI edits, and capture both apps in the same environment. A disconnected phone alone is not a blocker.
- Load references only at the relevant step below. Reuse inventories, fixtures, captures, and installed tools; invalidate by artifact/build/environment changes.
- Batch independent reads, filter large dumps, and keep raw artifacts on disk. Read summaries and relevant excerpts instead of whole decompilations or image catalogs.
- Run focused checks during corrections and required project checks at the checkpoint. Revisit failures with new evidence, not repeated blind edits.
- Maintain one compact `spec/progress.md`: active journey/stage, build IDs, contract/result links, blockers, user decision, next command. Update it at checkpoints; avoid duplicate status reports and giant implementation plans.

## References and tools

| Need | Read/use |
| --- | --- |
| New binary/tool selection | [toolchain.md](references/toolchain.md); `scripts/inventory.py` |
| Missing source/runtime access | [extraction.md](references/extraction.md) |
| Reverse logic or diagnose tool access | [reverse-engineering.md](references/reverse-engineering.md) |
| New dependency decision | [flutter-stack.md](references/flutter-stack.md) |
| Record contracts or results | [contracts.md](references/contracts.md) |
| Compare a journey | [parity.md](references/parity.md); `scripts/diff_screenshots.py` |

Before claiming a checkpoint, run `python3 <ditto-path>/scripts/validate_spec.py --check-files` from the project root. This validates evidence records, not truth or app completeness. Legacy unsupported passes must be reassessed, not patched with invented metadata.

## Boundaries and reporting

Use authorized accounts/services; preserve user data. Do not reset a personal app installation to create fixtures. Keep credentials out of captures; label instrumented originals. Never ship inspection hooks or disabled TLS validation.

Report implemented scope, executed/required comparisons, user-testing status, and unresolved gaps from the ledger. Keep intentional differences explicit and user-authorized. No universal parity percentage, source-recovery promise, or completion claim based on green candidate tests.
