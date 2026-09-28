---
name: ditto2
description: Use when collecting evidence from an Android Flutter APK for cloning with Ditto2, or continuing a Ditto2 reconstruction from that evidence.
---

# Ditto2

Reconstruct the whole app from recovered internals and observed user journeys. Use the independent Ditto2 MCP; reuse older Ditto workflows only when requested. Honor the user's current milestone. The implemented MCP covers evidence collection; later stages below define the roadmap.

## Collect and connect evidence

Use one evidence directory for each APK and exploration run:

- `analysis/`: complete Apktool resources and assets, JADX code, r2Flutter exports and native snapshot, plus logs.
- `exploration/`: all DroidBot screenshots, state files, recorded actions and navigation data.
- `review.json`: an index of reviewed screens, transitions, cited findings and gaps. The entire directory is the unified evidence; preserve unreviewed artifacts too.

1. Run `analyze_apk` into `analysis/`. Apktool, JADX and r2Flutter are required. r2Flutter needs `lib/arm64-v8a/libapp.so`; report incompatible input rather than omitting the analyzer.
2. Run `explore_apk` into `exploration/` with an explicit device serial and bounded events/time; use `adb devices -l` to discover devices when needed. Check its API with `adb -s SERIAL shell getprop ro.build.version.sdk`: Honeynet DroidBot has unresolved reports for API 32+. If it exits without a valid graph, keep the `.incomplete` logs and report the runtime failure; do not treat it as captured coverage. Use a compatible device when available. Keep the original app installed. Do not control the same device elsewhere during exploration.
3. Page through `inspect_exploration`. View screenshots and read event records before confirming their IDs; check both endpoints for each transition. Inspect all three analyzer exports for assets, code structure and available behavior. Distinguish packaged clues from observed runtime use.
4. Call `unify_evidence` with the evidence directory, reviewed IDs, cited static findings and explicit gaps. Findings name the analyzer and relative source file, with related screen/event IDs where supported. The MCP checks references; the agent judges the claims. Retain missed journeys, sign-in/permission stalls, unreviewed states and actions absent from the navigation graph as coverage gaps. An empty gaps list is not proof of complete coverage.

Use fresh export directories. JADX exit code 3 can still produce useful source: Ditto2 marks that export partial, keeps it, and adds its log to the review gaps. Other failed runs retain logs and partial data marked `.incomplete`; resolve the failure and rerun into a fresh collection before handoff. Reuse successful exports for inspection. If a required tool is unavailable, report the blocker without silently replacing it. Stop here when the current milestone is evidence.

## Later stages

- **Generate Flutter directly:** use the full evidence collection to implement the whole app and complete user journeys. Recover and reuse relevant assets. Record evidence gaps instead of inventing hidden journeys or presenting placeholders as complete. Complete the initial implementation without launching the clone in an emulator or Flutter Web; run Dart analysis and focused tests as useful.
- **Compare and improve:** then build Flutter Web. Use browser automation, direct screen access and screenshot comparisons against the evidence for rapid UI corrections. Use Widget Previewer for suitable isolated components and Flutter tests for deterministic functional checks. Track platform behavior the browser cannot verify.
- **Optional Android verification:** perform emulator debugging and platform checks last, when requested.
