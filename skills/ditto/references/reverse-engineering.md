# MCP package analysis

Android Flutter phases require successful JADX, Apktool, and r2Flutter MCP sessions for the same original APK hash. Keep the full exports in a shared, ignored cache such as `work/`; each original phase pack retains their matching receipts and result indexes. Missing or incompatible required capability blocks the phase.

Start with package-wide indexes and a coarse phase map, then retain only phase-relevant files and findings. Recover useful assets/resources directly and reconstruct behavior from static clues plus runtime evidence; do not promise recovery of the original Dart source. Resolve details as each phase needs them instead of exhaustively analyzing every route up front. The contract's `reverse_engineering.include_globs` controls packaged resources copied into `original/reverse.001/`. The reverse index hashes every retained file and links useful entries to checkpoints. Full MCP analyzer output stays in the shared cache; a phase does not copy thousands of decompiled files.

## Route questions by owner

| Question | MCP evidence |
| --- | --- |
| Manifest, components, permissions, platform channels, Java/Kotlin wrapper | JADX |
| Resource table, strings, dimensions, colors, drawables, XML, assets | Apktool |
| Dart object pools, strings, functions, cross-references, ABI/profile confirmation | r2Flutter |

Use all three required analyzers once per original APK and analyzer version. Reuse the same `output_dir` across phases: `analyze_package` verifies and returns the cached export. Changed APKs or analyzer versions use a new directory. `query_analysis` lists or searches the index and reads bounded file excerpts; it never reruns the analyzer. Cache age and server restarts do not invalidate recorded results. Git ignores the cache but does not delete it; preserve it locally between phases. A fresh machine needs that cache restored or one new analysis run. During investigation, ask the server that owns the unresolved fact. Keep queries bounded around observed anchors such as a label, resource ID, route, storage key, channel method, constant, or function address.

For each question record the package hash, MCP server/tool/session, ABI or Dart profile where relevant, retained output path, finding, checkpoint link, and limitation. A tool connection proves capability only after it reports the expected package and a useful bounded probe.

Reverse-engineered findings are inferred until runtime evidence confirms them. A resource proves that content is packaged, not that it is reachable. Decompiled branches may be incomplete. Flutter wrapper DEX does not establish Dart application logic. Generated names and reconstructed pseudocode are analysis aids, not recovered source.

Turn each useful finding into a runtime question or implementation constraint. When static evidence conflicts with controller evidence, retain both, state the conflicting preconditions, and recollect the smallest necessary original checkpoint through mobile-control.

Never execute extracted scripts or binaries during inspection. Reject unsafe archive paths, linked files, duplicate members, encrypted members, and unbounded extraction. Keep complete decompiler output outside agent context; use the reverse index to retrieve only relevant pieces.
