# Still-image parity and semantic verdicts

`phase compare` processes the checkpoints present in the active clone pack in contract order. It compares PNG pairs at native resolution and uses hierarchy XML only when both checkpoint artifacts contain it. It writes immutable result, diff, and triptych revisions, then refreshes the compact report and overview with retained results for unaffected checkpoints.

Each triptych contains three labeled panels in this order:

```text
ORIGINAL APK | CLONE APK | DIFF
```

Panels remain at full capture resolution. `phase_overview.png` uses thumbnails for navigation. Inspect the full triptych before making a visual decision.

The pixel metric uses YIQ color distance. `threshold` controls per-pixel sensitivity; `max_diff_ratio` controls how many compared pixels may change. Exclusions remove declared nondeterministic pixels from both numerator and denominator. Never resize captures, hide meaningful UI, loosen thresholds, or expand masks to manufacture a pass.

Metric status and semantic verdict are separate:

- Any ratio can fail when content, controls, navigation, or persistent behavior is wrong.
- Use the ratio to prioritize inspection, not as a fixed acceptance threshold. Explain larger deltas using the paired evidence; do not invent an authorized product change merely because rendering differs.
- A semantic pass remains valid until relevant code, fixtures, original evidence, or environment changes. Do not repeatedly capture an already understood harmless difference.

Paired XML adds an automatic hierarchy comparison. When absent, report it as `not_run`; screenshots and triptychs can still support a visible-layout verdict. They do not establish accessibility semantics.

Evidence must fit the dimension. PNGs, triptychs, and visual metric results support visual decisions. Screenshots, triptychs, XML, and layout results support visible layout. Replay traces support behavior and navigation. Write/read/restart observations support persistence; a foreground activity dump alone does not. Traffic records support network. Semantics evidence supports accessibility. A screenshot alone cannot establish these nonvisual dimensions.

Use `phase verdict` after inspecting all relevant evidence. Cite evidence IDs from the immutable result catalog and explain why the observed state is correct or incorrect. `Looks close` is insufficient. A small ratio does not force acceptance, so a failed semantic verdict can stand without repeated capture when the evidence already makes the defect clear.

After corrections, capture a new clone pack and compare again. Old artifacts remain immutable. If a change affects only declared dependencies, use `phase invalidate` and retain unaffected checkpoint decisions with their exact older build identities. The active report lists both evidence builds and the current deliverable build.

The readiness report is the final automated decision packet. It includes per-dimension verdicts, accepted authorizations, proposals, invalidations, build identities, active result links, and the overview limitation. Human review happens once after this packet is ready.
