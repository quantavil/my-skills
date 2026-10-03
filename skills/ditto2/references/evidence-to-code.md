# Use reverse-engineering evidence in reconstruction

Use this workflow when implementing or reviewing a reconstruction. Collection-only requests still end after collection. Work within the user's requested feature scope and intentional differences, such as making features free.

## 1. Establish what the tools actually recovered

Verify matching package/version/signers and the complete selected deliveries. Use ARM64 for primary Flutter AOT analysis and x86_64 for emulator exploration. Check analyzer status, ABI, Dart snapshot/profile compatibility and limitations before interpreting results. A partial collection remains useful for its supported artifacts; it does not establish complete logic recovery.

r2Flutter recovers metadata, references and object-pool values, and can annotate analysis. It is not a Dart source decompiler. Names identify places to investigate; they do not specify complete algorithms. JADX primarily exposes Android wrapper/plugin code, not the Flutter AOT application's original Dart logic. Class fields and generic object decodes require corroboration from consuming code. Do not assign meaning to ambiguous fields or treat a successful command as proof that all branches were recovered.

Use existing MCP exports, search, compatible analysis tools and saved files. If only a symbol index was exported, inspect relevant function bodies through an available supported analyzer. Preserve supplementary disassembly and its tool/version, ABI/profile, input hash and command. Record an unavailable body/profile as a gap instead of inventing source or extending architecture support by assumption. No new MCP API is required for this workflow.

## 2. Trace each feature through its logic

Start from requested user actions and rendered outputs. Locate relevant domain functions using metadata and observed keys; follow callers/callees to inputs, model conversion, computation, correction, persistence and UI state. Expand into helpers when they influence a rule. Do not stop after extracting constants while available history or correction bodies remain unread.

For each relevant body, inspect branches, comparisons, units, rounding, null/default paths, time boundaries, iteration/order and mutations. Decode referenced constants using a compatible decoder and corroborate their use in the consuming instructions. Maintain uncertainty where argument/field meaning or indirect targets remain unresolved. Cross-references and names are evidence of structure, not proof of every runtime branch or exact semantics.

Use the relevant collected evidence as fully as the supported tools allow. Account for domain dependencies; do not blindly read every framework, analytics or unrelated function to manufacture a percentage. Classify reviewed material as used, unresolved, or outside the requested behavior. Preserve raw exports regardless of classification.

Finish a feature's current evidence audit when each relevant rule and dependency has either an interpretation or a concrete unresolved reason and next discriminating check. Do not repeatedly retry a known unavailable input/body without new evidence or capability. Honor a user's collection limits; continue supported implementation and report the affected gaps rather than silently approximating or requesting the same missing input again.

### Navigate native evidence without confusing offsets or tool limits

Keep object-pool offsets, virtual instruction addresses and ELF file offsets distinct. Decode constants in the snapshot's pool address space; a file-offset string match is not automatically a pool reference. Reuse compatible pool-reference and caller indexes to locate consuming bodies, rather than repeatedly scanning the whole binary. Inspect indirect dispatch separately from direct calls.

Start disassembly from validated function boundaries. A text section can contain snapshot data, so an empty linear decode is not proof that code is absent. Treat unexpectedly low reference counts as a possible scanner limitation; corroborate relevant sites against annotated instructions. ARM64 instruction patterns and register roles must be checked against the actual ABI/profile, not applied to an x86 file because both are ELF64.

These navigation checks are informed by the reviewed [apk-reverse Dart AOT reference](https://github.com/newliver666/apk-reverse/blob/7b6c6932a95f03d778e81e5e1a2cbf6f62dc97fd/skills/apk-reverse/references/dart-aot.md). This is selective methodological use: no external scripts are installed, no reported scanner counts are treated as our verification, and no APK patching/repacking workflow replaces independent Flutter reconstruction.

## 3. Write a small feature map before implementing its rules

Keep one concise Markdown table in the project, not a new database or API:

Account for every requested feature in this map, then expand its behavior-affecting rules as needed. Record a reason when excluding a discovered domain dependency from scope; do not exclude history or corrections merely because the prototype omits them.

| Feature/rule | Original evidence | Recovered behavior and uncertainty | Dart implementation | Original-derived verification | Status |
| --- | --- | --- | --- | --- | --- |
| Next interval after a short entry | ARM64 artifact + symbol/address; runtime capture/action | Known input/output units; threshold unresolved | File/symbol, or missing | Same profile/history, short-entry sequence, observed result | Partial; threshold unresolved |

Evidence references identify exact files, symbols/addresses where available, capture/run context and input identity. Use project-relative paths so the project can move. Keep raw evidence in a project-local Git-ignored directory; retain useful source assets in the app. Do not overwrite raw receipts or previous reviews. The table is a trace of reasoning and implementation, not a claim that findings were accepted by an analyzer.

Separate collected, interpreted, implemented and verified status. Mark rules as statically recovered, runtime-observed, inferred, unresolved, or intentionally changed. "Implemented" does not imply "verified against original." An intentional commerce change does not excuse missing premium feature behavior. For an existing clone, audit provisional constants, generic editors and missing domain dependencies against this table before trusting green tests.

## 4. Resolve uncertainty through targeted runtime experiments

Use existing app-specific scripts and supplementary captures. Prepare known profiles/settings/records and vary one relevant input at a time. Record the before state, action, elapsed time and after output; keep screenshots/state files with the sequence. Use the original to distinguish candidate interpretations rather than choosing the most convenient one.

Choose cases from recovered branches: empty and accumulated history, alternate settings, short/late/skipped entries, pause/resume, edits/deletes, restart persistence, overnight boundaries and invalid input where applicable. Do not assume every app has the same scenarios or force these sleep examples into unrelated apps.

Use disposable isolated accounts/data or a verified offline session for mutations. An emulator snapshot can restore local state but cannot undo remote writes. A reuse session, keep-app option or snapshot does not establish cloud rollback. Never reset the user's original session to obtain clean test data. Continue read-only analysis and independently evidenced implementation while isolation or missing inputs remain unavailable.

If original screen IDs collide, use capture filenames, screenshots, state content and run context to disambiguate them. Keep original graph IDs and raw runs; manual actions are supplementary evidence, not fabricated graph transitions.

## 5. Implement and verify the recovered rules

Translate the supported rules into Dart with their defaults, boundaries, rounding, corrections and persistence. Record any intentional product difference separately. If an essential rule is unresolved, state the narrow missing input or experiment and continue supported work; do not silently fill it with a fixed array, sample value or generic formula.

Create expected outputs from original observations or sufficiently interpreted native code, not by copying the clone's current output. Verify the baseline, discriminating branch cases and stateful sequences. Use identical profile/settings/history, date/timezone, selected/logical day and elapsed time. Specify tolerances only when evidence justifies them; do not invent tolerances to hide mismatch.

Compare numerical results and transitions before claiming behavioral parity. Compare screenshots at matched viewport/platform state for visual parity. Web cannot certify Android notifications, widgets, native sharing or system integration; verify applicable native behavior separately. A fixture proves only its supported state, and must be identified as a fixture. Do not hardcode a date's displayed totals to make a screenshot match.

For numerical/stateful business logic, include original runtime cases that distinguish plausible interpretations before claiming behavioral parity. If runtime confirmation is unavailable, report the bounded static implementation and remaining verification gap; tests derived from one possibly mistaken interpretation do not settle it.

Before claiming a feature verified, check that relevant domain dependencies have been interpreted or explicitly recorded as unresolved, implemented rules have source references, and original-derived cases match. Report remaining gaps. Do not turn retained function counts, collected graph sizes, copied asset counts or clone-only test totals into a completeness certificate or a promise of 100% source recovery.

An essential unresolved rule, available-but-unread relevant body, or missing required implementation prevents an unqualified feature/full-clone verification claim. Report only the supported cases as verified. A deadline or green clone tests do not lower this standard.

## Tool research

Official references checked October 3, 2026:

- [r2Flutter overview](https://github.com/radareorg/r2flutter/blob/main/README.md): metadata and analysis aid, not a Dart source decompiler.
- [r2Flutter support matrix](https://github.com/radareorg/r2flutter/blob/main/doc/support.md): ARM64/AArch64 is the primary analysis target; compatibility is capability-specific.
- [Blutter](https://github.com/worawit/blutter): Android ARM64 analysis with annotated assemblies and object-pool dumps. These outputs still require interpretation; this reference does not mandate installing another tool or changing the MCP backend.

Recheck installed-tool capabilities for each input rather than treating this research as a permanent compatibility promise.

See the [workflow review](workflow-review.md) for validation results and the selective apk-reverse assessment.
