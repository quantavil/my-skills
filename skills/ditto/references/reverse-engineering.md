# MCP package analysis

Android Flutter phases require successful JADX, Apktool, and r2Flutter MCP analysis of the same original APK. Keep full exports in a shared ignored cache and reuse them across phases for the same package and analyzer versions. Missing or incompatible required capability blocks the phase.

Start with package indexes and a coarse phase map. Keep the investigation bounded to the active flow, then retain only useful assets and findings. Recovering resources can guide implementation; decompilation does not promise recovery of the original Dart source.

| Question | MCP evidence |
| --- | --- |
| Manifest, components, permissions, platform channels, Java/Kotlin wrapper | JADX |
| Resource table, strings, dimensions, colors, drawables, XML, assets | Apktool |
| Dart object pools, strings, functions, cross-references, ABI/profile | r2Flutter |

Reuse an analyzer's verified export instead of rerunning it. Query bounded excerpts around a concrete anchor such as a visible label, resource ID, route, storage key, channel method, constant, or function address. Record the package hash, MCP server/tool/session, relevant ABI or Dart profile, finding, and limitation alongside the phase context.

Static findings remain inferred until runtime evidence confirms observable claims. A packaged resource does not prove that a screen uses it; reconstructed pseudocode may omit behavior. Turn useful findings into a checkpoint question or implementation constraint. If runtime evidence conflicts with analysis, retain the distinction and collect the smallest original checkpoint needed to resolve it.

Never execute extracted scripts or binaries. Reject unsafe archive paths, linked files, duplicate or encrypted entries, and unbounded extraction. Keep full decompiler output out of agent context; retrieve only relevant excerpts.
