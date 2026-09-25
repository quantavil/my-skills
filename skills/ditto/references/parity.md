# Visual and behavioral parity

Each successful **Capture & compare** writes the current checkpoint result and a labeled triptych:

```text
ORIGINAL APK | CLONE APK | DIFF
```

Inspect the full-resolution triptych for every captured checkpoint. The numeric pixel metric helps prioritize review; it does not decide parity. A low difference ratio can still hide incorrect text, controls, navigation, or state. Do not resize images, mask meaningful UI, or change thresholds to manufacture a pass.

Treat visual comparison and semantic judgment separately. For every checkpoint, decide whether the visible content and geometry match and whether the observed interaction reached the expected state. Explain any larger difference from the evidence. Do not infer an authorized product change merely because rendering differs.

Evidence must support the claim. PNGs and triptychs support visible appearance; paired XML can help explain layout. Recorded input and resulting states support behavior and navigation. Persistence requires observing a write, restart, and read. Network and accessibility claims require their own evidence. A screenshot alone cannot establish these nonvisual dimensions.

After a fix, capture only checkpoints affected by that change. A successful retake replaces that checkpoint's current clone image and diff and clears its old verdict. Unaffected results retain the exact build identity they tested. If original evidence changes, its dependent clone comparisons become stale and must be recaptured. The current report must never present a stale verdict as current.

Review the current report, full triptychs, build identities, and unresolved differences together at final human review. The pixel metric is a diagnostic; the AI evaluates the evidence and the human makes the final phase decision.
