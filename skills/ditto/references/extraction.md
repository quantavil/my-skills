# Package and runtime feasibility

Preserve the supplied APK, AAB, or IPA and compute its SHA-256 before analysis. Work from a copy in controlled temporary storage. Reject archive traversal, linked entries, duplicates, encrypted members, and selections beyond the configured size bound. Never execute bundled code during inventory.

For Android, identify package type, framework indicators, ABI set, split requirements, assets, and install feasibility. An AAB needs an identified generated install set. A base APK may be incomplete when required splits are missing. Successful archive parsing does not prove launch.

For Flutter Android, retain the matching `libapp.so`, engine/profile facts, wrapper DEX context, Flutter assets, fonts, and relevant resources through the compulsory MCP exports. An unsupported r2Flutter snapshot or ABI blocks the phase; do not guess application logic when analysis is unsupported.

For iOS, record bundle metadata, platform and architecture, signing/runtime constraints, frameworks, assets, and symbol identity. A device IPA is not automatically usable in a simulator. Runtime parity requires a compatible, authorized target and an explicit compulsory MCP set.

The phase reverse index owns retained package evidence. Start broad enough to identify package structure, then retain only files and MCP findings connected to the phase's questions, checkpoints, and dependencies. Full tool output can remain in bounded working storage; do not load it wholesale into agent context.

Static findings stay `inferred` until controller evidence confirms observable claims. Missing runtime access can support an evidence report and explicit blockers, but cannot produce passing parity verdicts.
