---
name: ditto2
description: Use when collecting evidence from an Android Flutter APK for cloning with Ditto2, or continuing a Ditto2 reconstruction from that evidence.
---

# Ditto2

Use the independent Ditto2 MCP to collect evidence for rebuilding observed app screens and journeys. Honor the user's current milestone; stop after evidence collection when that is the request.

For reconstruction or parity review, read [evidence to implementation](references/evidence-to-code.md). Relevant reverse-engineering evidence must inform behavior, not remain an unused archive behind a screenshot-based imitation.

## Inputs and setup

Use **ARM64 for primary static analysis and x86_64 for emulator exploration**. Two standalone APKs suffice if complete. For Play split delivery, retain the signed base and every required split; never merge/re-sign them to force two files. Pass the base as `apk_path` and all selected splits explicitly as `split_paths`; sibling files are not automatically installed.

For a Play URL/package, follow [acquisition](references/play-apk.md). Acquire each ABI from a compatible Play device or use supplied complete inputs. Missing ARM64 remains a gap; do not silently substitute another release. The MCP verifies package, version, signer and artifact hashes; differing common DEX/assets block unification. ABI-specific runtime equivalence remains unverified.

Keep the ARM64 requirement for primary Flutter AOT reverse engineering. Supplementary x86 metadata does not replace it or establish recovered application logic. Analyzer success establishes the reported capability only: metadata, constants, disassembly and interpreted behavior are distinct results.

Check Android SDK `apkanalyzer`, `apksigner`, `adb`, Apktool, JADX and r2Flutter. For missing DroidBot follow [automatic setup](references/setup.md), respecting host build restrictions and existing authorization. Discover devices with `adb devices -l`; use an explicit serial and verify its API/ABI. Do not control the same device elsewhere during exploration.

## Collect and review

Use a fresh evidence directory with `analysis/`, `exploration/`, and final `inputs.json`/`review.json`. Preserve the entire collection, including unreviewed artifacts.

1. `analyze_apk(apk_path=ARM64_BASE, split_paths=ARM64_SPLITS, output_dir=EVIDENCE/analysis)`. Each analyzer runs independently. ARM64 libapp.so is located across the selected set. Read `analysis.json`: per-tool status and `collection_status` distinguish complete, usable partial, and failed results. Missing ARM64 or failed r2Flutter does not discard Apktool/JADX. `.incomplete` means interrupted/unfinalized evidence; resolve that interruption before handoff.
2. `explore_apk(apk_path=X86_BASE, split_paths=X86_SPLITS, output_dir=EVIDENCE/exploration, device_serial=SERIAL, event_count=100, timeout_seconds=600, script_path=SCRIPT_OR_NONE, install_mode="install")`. Use `"reuse"` for an already prepared session: the MCP checks installed APK bytes before exploration. `-keep_app` leaves the app installed afterward; it does not guarantee preservation of every live activity.
3. Guide onboarding and dismiss paywalls through the existing [DroidBot script workflow](references/setup.md). Target verified controls and record actions/screens. Use replayable scripts in the recorded run where possible; keep manual captures outside the graph clearly labeled as supplementary evidence and gaps. Never fabricate transitions for manual steps.
4. Page through `inspect_exploration(exploration_dir=..., offset=0, limit=50)`. View screenshots and event files and check both endpoints before confirming IDs. Event budgets count all input events, including system screens and repeated touches; greedy DFS does not guarantee requested screen coverage. Retry missing journeys with targeted scripts or bounded additional runs; preserve each raw run separately.
5. Use `search_analysis(analysis_dir=..., query=..., source="all", offset=0, scan_offset=0, limit=20)`. Continue with both returned offsets. Only usable analyzer exports are searchable in finalized partial collections. JADX exit 3 retains partial Java and a separate raw-instruction fallback; fallback success does not repair Java source.
6. Optionally `extract_semantic_keys(exploration_dir=..., output_path=EVIDENCE/semantic_spec.json)` for debug_/key_ clues with sources. Optionally `deduplicate_graph(exploration_dir=..., output_path=EVIDENCE/graph_view.json)` to group identical screenshots and full state context. Both require new output files and preserve originals. Keys are clues, not verified model/controller names; original UTG IDs remain authoritative for review.
7. `unify_evidence(apk_path=X86_BASE, static_apk_path=ARM64_BASE, evidence_dir=EVIDENCE, confirmed_screen_ids=[...], confirmed_event_ids=[...], findings=[...], gaps=[...])`. Findings require `claim`, `analyzer`, `path` relative to that analyzer, and optional reviewed `screens`/`events`. With split input, Apktool findings use `base/...` or `<split-id>/...`. Cite only usable output. Finalized partial analysis is allowed and its analyzer gaps are added automatically; interruptions and unusable findings are rejected. `inputs.json` links both verified deliveries; legacy exports support only their original same-APK relationship.

Verify requested screens and transitions explicitly. A nonempty graph or empty user-supplied gaps list does not prove complete coverage. API 32+ DroidBot failures can occur: retain diagnostics and report runtime failure when no valid graph exists. Never overwrite original evidence or existing review indexes.

## Later milestones

- **Rebuild:** follow the [evidence-to-code workflow](references/evidence-to-code.md). For each requested feature, trace relevant native bodies, callers/callees, constants and branches into rules; map those rules to Dart code and original-derived test cases. Review relevant evidence already collected before replacing behavior with a guess. Keep unresolved rules and intentional user-requested differences explicit; continue independently evidenced work. Initially use Dart analysis and focused tests without launching the clone.
- **Compare:** verify original and clone with identical profiles, settings, records, dates and elapsed time. Compare numerical outputs, transitions and persistence as well as screenshots; use Flutter Web/Widget Previewer for supported visual checks. A seeded screen or clone-only passing tests cannot verify omitted logic or full-app parity. Track platform behavior the browser cannot verify.
- **Android verification:** emulator/platform checks last, when requested.
