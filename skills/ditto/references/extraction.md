# Extraction and runtime access

Use [toolchain.md](toolchain.md) for the default tools and commands. This reference covers evidence gaps and when to change the extraction approach. Prefer narrow extraction over loading whole decompiler dumps into context.

## Shared intake

Record SHA-256, file size, package/bundle identifier, app version, build type, framework indicators, ABI, and any missing split packages or asset packs. Record uncertainty when indicators conflict. Inspect archives in a separate workspace without modifying originals. Validate archive paths and size before extraction; do not execute bundled code as part of inventory.

Distinguish what can be inspected on the current host from what can be run. An Android AAB or incomplete split APK set is not automatically an installable standalone APK. An iOS device IPA is not automatically a simulator build, even when the CPU architecture appears compatible. Record an actual launch result before claiming a working oracle.

## Android native or hybrid

Use package metadata and resources to map entry points, components, permissions, links, strings, images, and native libraries. Run the Android command sequence in toolchain.md. Use APKiD if protection signatures would change the runtime approach; add MobSF only if its broader inventory is useful.

Trace only the code relevant to an unresolved behavior. Obfuscated names are not architectural truth; use supplied mapping files when available. Compose and embedded web interfaces may require runtime inspection beyond resource XML. Inspect WebView behavior and its bridge without assuming the whole app is native.

For JNI or native libraries, prioritize JADX for the Java/Kotlin bridge and method signatures. Escalate to headless Ghidra (`analyzeHeadless`), LIEF, or radare2 only when proprietary algorithms, native request signatures, or cryptographic ciphers are compiled into `.so` binaries and materially affect the target flow. Never route general DEX analysis or Flutter `libapp.so` reversing through Ghidra.

## Flutter AOT

Inspect Flutter assets, font metadata, native wrapper, plugins, and platform-channel boundaries. A release artifact does not provide the original Dart project merely because the destination is also Flutter.

Start with r2flutter header/function output. Use Blutter or flutterdec only for an unresolved question their outputs can answer. Check each tool's supported OS, architecture, Dart snapshot/runtime version, and obfuscation handling. Do not infer iOS support from Android ARM64 support. Record parse failures and unsupported snapshots as coverage gaps. Do not paste speculative pseudocode into production as recovered source.

When extraction is unproductive, prioritize reachable behavior and request existing build symbols or source if necessary for a specific unresolved requirement. Avoid open-ended assembly analysis without a concrete behavioral question.

## iOS native or Flutter

Inventory Info.plist, entitlements, frameworks, assets, Mach-O architecture/platform information, and executable protection. Match available dSYM UUIDs to the actual binary before relying on symbols. Candidates include Apple command-line tools, ipsw, LIEF, and targeted Ghidra/radare2 analysis; Objective-C metadata does not reconstruct SwiftUI source.

Runtime work needs an actual compatible device/build and appropriate signing/access. When only a device build is available, do not keep trying to install it in a simulator. On a host without an Apple build environment, continue portable inventory and specification work, but report iOS build and execution as untested.

## Runtime observation

Choose an available driver: Maestro or Mobile MCP for supported targets, uiautomator2 for Android, or the project's existing test harness. Confirm actual capabilities; a skill description does not imply an MCP server is connected. Prefer stable semantic selectors. When accessibility nodes are absent, pair screenshot-based actions with explicit checkpoints and record reduced automation reliability.

Observe applicable states: initial, loading, populated, empty, validation failure, server failure, offline, denied permission, expired session, restart, background/resume, and supported theme/locale/orientation variants. These are exploration candidates, not requirements to invent absent states.

For network evidence, prefer permitted debug capture or test server logs, then a qualified proxy setup. Certificate pinning, custom transports, and instrumentation restrictions may prevent capture. Frida or Grapefruit can support authorized targeted inspection, but no generic hook guarantees visibility. TLS plaintext does not automatically reveal request-signing logic or keys. An HTTP-shaped response alone does not establish full backend semantics.

For storage, capture before/after semantics using supported test exports or authorized inspection. Encrypted storage may remain unavailable; use observed restart/offline behavior to bound conclusions. Keep credentials and raw sensitive captures separate from agent-facing evidence.

End intake with a small table: question, evidence obtained, tool/build, limitation, next useful observation. Stop retrying an unsupported path when the same failure yields no new evidence; continue another evidence channel or identify the missing prerequisite.
