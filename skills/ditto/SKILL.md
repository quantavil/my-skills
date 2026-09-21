---
name: ditto
description: Use when reconstructing an Android or iOS app from APK, IPA, AAB, or runtime evidence, or reviewing a Flutter clone for behavioral and visual parity. Not for ordinary Flutter development, available full-source migrations, or the Ditto clipboard app.
---

# Ditto

Reconstruct observable behavior using the original app as the oracle. Deliver one complete, compared, user-tested journey at a time. Decompiled code informs contracts; candidate tests cannot establish original behavior.

Every script below is standard-library Python or bash: no Bun, Node, or ImageMagick is required for any of them.

## Start or resume

Infer mode: evidence-only, reconstruction, or parity repair. Preserve the requested platform, architecture, and authorized differences. Resolve conflicts such as offline-only versus server-backed features explicitly.

Read `spec/progress.md`, then the active contract and linked evidence. Check changed files/build identity before trusting previous results. Set `DITTO_SKILL` to this skill's directory. For a new task, run `python3 "$DITTO_SKILL/scripts/ledger.py" --project . init`, record artifact identity and scope in `spec/app.md`, and briefly inventory journeys.

Prefer a local Android emulator and available emulator/mobile tooling for discovery, interaction, installation and capture. Use direct ADB commands or the ADB-backed capture fallback only when the user requests them or a required operation is unavailable or failing through preferred tooling; state the concrete reason. Emulator tools may use ADB internally. Use physical devices for requested or hardware-specific checks, not as the default iteration target. Preserve the requested platform; use corresponding simulator/device tooling for iOS. Disconnection does not invalidate existing evidence.

## Journey loop

1. **Select:** Choose one user outcome, including its UI, data, and restart effects. List its checkpoints, relevant branches, and acceptance criteria. Keep future journeys as short backlog entries.
2. **Observe:** Replay the original with preferred emulator tooling; register captures using `scripts/ledger.py adopt`. The ADB-backed `capture` command is a fallback for missing capture/provenance capabilities ([contracts.md](references/contracts.md)). Record setup/actions, build and environment facts. Sparse Flutter hierarchies need screenshots and explicit checkpoints. Inspect static code only for unanswered questions; record unknowns.
3. **Build:** Implement the smallest complete slice within existing boundaries. Complete the known, related edits in the current task/phase before rechecking as a batch. Convert capture pixels to logical dimensions; reuse confirmed tokens. Use [flutter-build.md](references/flutter-build.md) for measurement and async-state guidance. Theme extraction and golden tests are optional aids when they reduce repeated work. Add only needed dependencies ([flutter-stack.md](references/flutter-stack.md)); keep domain logic separate from widgets.
4. **Compare:** Replay equivalent fixtures/actions against both apps and capture the candidate the same way. Run `scripts/diff_screenshots.py` for the visual comparison (3-panel composite, masked/excluded regions, XML hierarchy bounding-box deltas), then `scripts/ledger.py comparison` to record the pass/fail verdict per dimension — see [parity.md](references/parity.md). Record visual, behavioral, persistence, and relevant platform results separately; a dimension that is genuinely inapplicable needs `not_applicable` **with a reason**, not silence and not a false pass. Fix discrepancies and rerun affected checks. Shared changes invalidate affected accepted journeys. Passing unit tests, golden tests, or taking screenshots alone is not parity.
5. **User checkpoint:** Deliver a runnable build, short test checklist, known gaps, and evidence links. Record actual feedback; fix and retest. Advance after comparisons pass and the user accepts. If the user explicitly waives testing, record that decision without calling it user-tested. Silence is pending. While waiting, allow bounded evidence collection but no implementation of another journey.

Evidence-only tasks finish with contracts/gaps and need no candidate build or user-testing checkpoint. Missing runtime access does not prevent evidence-backed implementation; it prevents claiming unexecuted comparisons passed. Finish useful work on the active journey and report its blocked checkpoint — a case left `blocked` must carry a recorded reason, or `validate_spec.py` will reject it.

If the user explicitly redirects work to another journey, record the pending checkpoint and follow that direction. Redirection is not acceptance or a testing waiver.

## Keep work fast

- Use the [warm emulator loop](references/parity.md#fast-laptop-iteration): install once, keep Flutter attached, and hot reload related edits together. A disconnected phone alone is not a blocker.
- Load references only at the relevant step below. Reuse inventories, fixtures, captures, and installed tools; invalidate by artifact/build/environment changes.
- `scripts/inventory.py` prints a summary, not the full archive member list — pass `--members <file>` only when a specific question needs the full list, written to its own file. Batch independent reads, filter large dumps, and keep raw artifacts on disk.
- Let ledger tools compute artifact hashes; supply verified build identity for adopted captures. Never invent hashes or reuse another capture's provenance.
- **Batch verification:** finish the related corrections, run the affected checks once, then capture/compare affected states together. If the task has only one remaining fix, finish it and check directly. Check earlier only when a failure blocks further work or the next edit depends on its result. Run required project checks at the checkpoint. Repeat only after relevant changes, failures or new evidence; passing checks alone do not justify another run.
- **Keep only useful artifacts:** one canonical contract/coverage ledger, one progress file, relevant source/assets, referenced evidence, comparison results and user decisions. Put exploratory captures, APK pulls and intermediate dumps in task-owned temporary storage. Remove only your unreferenced scratch files after use; preserve accepted/referenced evidence and user files. Avoid duplicate plans, status reports, token files and screenshot copies. Generate a montage or full archive listing only when it will be inspected.
- Maintain one compact `spec/progress.md`: active journey/stage, build IDs, contract/result links, blockers, user decision, next command. Update it at checkpoints; avoid duplicate status reports and giant implementation plans.

## References and tools

| Need | Read/use |
| --- | --- |
| New binary/tool selection | [toolchain.md](references/toolchain.md); `scripts/inventory.py` |
| Missing source/runtime access | [extraction.md](references/extraction.md) |
| Reverse logic or diagnose tool access | [reverse-engineering.md](references/reverse-engineering.md) |
| New dependency decision | [flutter-stack.md](references/flutter-stack.md) |
| Writing Dart: px→dp, tokens, async state, optional goldens | [flutter-build.md](references/flutter-build.md); `scripts/theme_extract.py` |
| Record contracts or results | [contracts.md](references/contracts.md); `scripts/ledger.py` |
| Compare a journey | [parity.md](references/parity.md); `scripts/diff_screenshots.py` |

Before claiming a checkpoint, run `python3 "$DITTO_SKILL/scripts/validate_spec.py" --check-files` from the project root (add `--json` for a machine-readable summary with required/passing/blocked counts and any critical case not currently passing). This validates evidence records, not truth or app completeness. Legacy unsupported passes must be reassessed, not patched with invented metadata.

## Boundaries and reporting

Use authorized accounts/services; preserve user data. Do not reset a personal app installation to create fixtures. Keep credentials out of captures; label instrumented originals. Never ship inspection hooks or disabled TLS validation.

Report implemented scope, executed/required comparisons, user-testing status, and unresolved gaps from the ledger. Keep intentional differences explicit and user-authorized. No universal parity percentage, source-recovery promise, or completion claim based on green candidate tests — golden tests included, since they check the candidate against itself, not against the oracle.
