# Mobile-control capture workflow

All device interaction and phase evidence use the required mobile-control MCP. The browser recorder routes human input through that controller and preserves MCP provenance. Screenshots from a development preview are useful while implementing, but they are not phase evidence.

## Capture the original

Use the device and environment selected for the phase. Prepare the starting fixture, then give the human a short checklist of useful checkpoints and the visible state that counts as settled. The checklist names destinations, not a required click order.

Start the mobile-control browser recorder and let the human navigate freely. Taps, swipes, Back, and supported text input are recorded as actions. The recorder saves candidate screenshots and available hierarchy XML during pauses. **Save screen** optionally bookmarks the next settled view. **Done** ends navigation and exports the candidates and action log.

Review candidate images, available XML, and the recorded path. Select evidence that actually shows each declared checkpoint, with a useful observed-state note. Select-original records the chosen PNG/XML and its device, package, session, environment, and action provenance. If evidence is missing or ambiguous, ask for a targeted recapture. The human's original navigation is valid evidence; do not require AI replay before selection.

Freeze the selected original before clone comparison. A frozen baseline stays current until deliberately replaced. A replacement uses `phase select-original ... --replace-frozen`, replaces only the selected checkpoint evidence, and invalidates its dependent clone comparison.

## Capture and compare the clone

Build the current clone as a debug APK and use the same emulator target and relevant environment as the original. Start the comparison browser with the phase and frozen original. For each checkpoint, the browser shows the original screenshot beside the live clone. The human navigates the clone to the matching settled state, may add an optional note, then selects **Capture & compare**. The controller captures the current clone screen and available XML, and the capture operation immediately writes the current comparison. **Next** advances through the checklist; **Done** ends the session.

The comparison result includes a full-resolution original/clone/diff triptych. The browser returns that result after each capture, so the AI can review all checkpoints together and batch related fixes. After an implementation change, recapture only affected checkpoints. A clone recapture replaces that checkpoint's current clone and diff files and clears its old verdict.

## Keep evidence honest

Every selected image must be tied to the intended original or clone package, MCP server/tool/session, device target, environment, and recorded action context. A successful input call does not establish that the intended UI appeared; inspect the actual captured screen. A failed or unsettled capture cannot be marked as a successful checkpoint.

Screenshots support visible layout. Paired XML can clarify visible hierarchy but does not establish accessibility semantics. Behavior and navigation need recorded actions and resulting states; persistence needs a write/restart/read observation; network and accessibility claims need evidence for those dimensions. A screenshot alone cannot prove them.

Stable current files are maintained under `original/`, `clone/`, and `diff/`. The current report and manifests identify the evidence and build each verdict uses. Successful captures overwrite current evidence. Do not hand-edit receipts, relabel candidate files, or accumulate revision copies. See [commands and evidence records](commands.md) for the current paths and CLI.
