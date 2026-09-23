# Mobile-control runtime workflow

All agent-facing UI operation and capture for an Android Flutter phase goes through the mobile-control MCP. The server may use Android platform tooling internally. Ditto accepts evidence only through the recorded MCP server, tool, session, target, and receipt.

## Establish the session

Use the emulator or authorized test device named by `runtime_target`. The preflight probe exercises launch, tap, type, swipe, back, screenshot, and hierarchy commands and returns device/environment facts. Input-command success only proves the transport; observe meaningful app outcomes during phase replay. Record viewport pixels, density, OS/API, locale, theme, font scale, orientation, renderer when relevant, and package identity.

One integration owner controls a device session. Parallel agents can inspect package evidence or implement isolated components, but they do not share or independently drive that session. Re-probe after device replacement or controller restart. New capture sessions read the current environment, and each checkpoint rejects changes within that session. Previously retained evidence keeps its historical session identity.

## Collect the original pack once

Prepare each named fixture, execute the contract setup and actions in checkpoint order, and export exactly the declared PNG, XML, trace, state, network, and semantics files. Use `<order>_<checkpoint-id>.<kind>` names plus `capture.json`. Stop the sequence when an action fails; never label the resulting state successful.

The original pack is complete only when every declared artifact exists, hashes match, controller identity matches active preflight, reverse MCP exports match the original package, and the manifest binds all facts. Freeze after reviewing scope unknowns and evidence completeness.

The AI may inspect any file in the phase and may query the running original again when evidence is missing or contradictory. After freeze, use `phase collect-original --checkpoint <id>` with a fresh controller export for each selected checkpoint. This creates a new original manifest, keeps unchanged evidence by hash, and reopens affected clone comparisons. A changed checkpoint definition belongs in a new contract revision.

## Implement and capture the clone

Implement the complete bounded phase before final replay. Build and install one identified clone APK through mobile-control, restore equivalent fixtures, and repeat the frozen original protocol. Keep the same target and environment. Export the exact declared files and controller receipt.

Each clone checkpoint records the APK SHA-256 and manifest revision. A later build does not erase earlier evidence. After dependency invalidation or a revised oracle, export only the files for reopened checkpoints. The controller capture must identify the installed APK hash, fixture, setup/actions, and capture time. The next clone manifest and comparison cover those checkpoints; unaffected verdicts retain their earlier result and exact build identity.

## Efficient control

Use the phase contract and original manifest as the replay script. `perform` records action arguments; label each declared action with its exact `step` text. `replay(steps=[...])` batches up to 100 actions and stops on the first execution failure. `observe_screen` shows the current UI without creating another checkpoint. `capture` requires the executed step labels in order and an `observed_state` description that the AI checks against the screenshot. Setup/fixture labels describe the intended preparation; they do not themselves prove it ran.

Use explicit `reset` only for a fixture that calls for clearing app data; `stop`, `launch`, and `restart` support lifecycle checks. Unicode text entry, traffic capture, and Flutter semantics have no backend yet; identify these limits during preparation. A fixture requiring an unavailable capability blocks that checkpoint. `abort` discards an incomplete capture and releases the device. Finalize releases it after saving. A process crash also releases the OS device lock. Query hierarchy when it supplies a declared artifact or resolves an uncertain selector. Capture one deterministic settled state per checkpoint. Batch checkpoints in one controlled session while resetting fixtures exactly where the contract requires it.

Do not ask for human feedback during collection, implementation, or correction. Run the automated readiness gate after all required semantic verdicts close. Then present the identified build, overview, full triptychs, report, accepted differences, proposals, and gaps for one end-of-phase decision.
