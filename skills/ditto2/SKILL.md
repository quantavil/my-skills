---
name: ditto2
description: Use when collecting evidence from an Android Flutter APK for cloning with Ditto2, or continuing a Ditto2 reconstruction from that evidence.
---

# Ditto2

Use the independent Ditto2 MCP to collect APK evidence. Reconstruct screens and journeys supported by that evidence, and keep unobserved behavior explicit as gaps. Honor the user's current milestone; the MCP currently covers evidence collection.

## Setup

For a Google Play link or package ID, use the [APK acquisition guide](references/play-apk.md)
and its download script to pull only the x86_64-compatible APKs installed by
Google Play on the signed-in x86_64 emulator. Keep the base APK and all
delivered splits. This x86_64-only input cannot satisfy the current r2Flutter
requirement for `lib/arm64-v8a/libapp.so`; report that static analysis gap
instead of silently downloading another ABI.

Check required tools before collecting evidence. If DroidBot is missing, follow
[automatic setup](references/setup.md), reusing existing authorization and respecting
host build restrictions. Install the approved dependency instead of stopping at
a missing-executable error. Verify with a bounded live MCP exploration.

## Collect and connect evidence

Use one evidence directory for each APK and exploration run:

- `analysis/`: complete Apktool resources and assets, JADX code, r2Flutter exports and native snapshot, plus logs.
- `exploration/`: all DroidBot screenshots, state files, recorded actions and navigation data.
- `review.json`: an index of reviewed screens, transitions, cited findings and gaps. The entire directory is the unified evidence; preserve unreviewed artifacts too.

1. Run `analyze_apk` into `analysis/`. Apktool, JADX and r2Flutter are required. r2Flutter needs `lib/arm64-v8a/libapp.so`; report incompatible input rather than omitting the analyzer.
2. Run `explore_apk` into `exploration/` with an explicit device serial and bounded events/time; use `adb devices -l` to discover devices when needed. `event_count` caps all DroidBot input events, including Android system screens, back/relaunch actions and repeated touches; it is not a screen count. The DFS policy is unguided and can spend a short budget in a file picker before reaching later app tabs. For targeted transitions, pass a DroidBot script via `script_path`; the MCP checks its top-level structure, then DroidBot validates its full grammar. Check the device API with `adb -s SERIAL shell getprop ro.build.version.sdk`: Honeynet DroidBot has unresolved reports for API 32+. If it exits without a valid graph, keep the `.incomplete` logs and report the runtime failure; do not treat it as captured coverage. Keep the original app installed. Do not control the same device elsewhere during exploration.
3. Page through `inspect_exploration`. View screenshots and read event records before confirming their IDs; check both endpoints for each transition. Verify that each requested screen appears in the graph before claiming it was explored. If a target is absent, inspect the saved accessibility tree; retry with a targeted script or a larger event/time budget. Keep manually captured screens/actions outside the graph clearly labeled and list them as gaps in `review.json`. Use `search_analysis` to search saved Apktool, JADX and r2Flutter text; pass both returned offsets to continue deep searches. Inspect relevant matches and assets, and distinguish packaged clues from observed runtime use.
4. Call `unify_evidence` with the evidence directory, reviewed IDs, cited static findings and explicit gaps. Findings name the analyzer and relative source file, with related screen/event IDs where supported. The MCP checks references; the agent judges the claims. Retain missed journeys, sign-in/permission stalls, unreviewed states and actions absent from the navigation graph as coverage gaps. An empty gaps list is not proof of complete coverage.

Use fresh export directories. JADX exit code 3 can still produce useful source: Ditto2 marks that export partial and attempts a separate raw-instruction fallback. Fallback failure is recorded in the manifest and review gaps without discarding the primary exports. Raw instructions are not verified Java source; keep the partial-Java gap even if fallback succeeds. Other failed runs retain logs and partial data marked `.incomplete`; resolve the failure and rerun into a fresh collection before handoff. Reuse successful exports for inspection. If a required tool is unavailable, report the blocker. Stop here when the current milestone is evidence.

## Later stages

- **Generate Flutter directly:** implement the evidenced screens and journeys, reusing relevant assets. Keep unsupported behavior explicit rather than presenting placeholders as complete. Complete the initial implementation without launching the clone in an emulator or Flutter Web; run Dart analysis and focused tests as useful.
- **Compare and improve:** then build Flutter Web. Use browser automation, direct screen access and screenshot comparisons against the evidence for rapid UI corrections. Use Widget Previewer for suitable isolated components and Flutter tests for deterministic functional checks. Track platform behavior the browser cannot verify.
- **Optional Android verification:** perform emulator debugging and platform checks last, when requested.
