# Targeted reverse engineering

Use this when a journey depends on unresolved calculation, serialization, validation, routing, storage, or platform behavior. Runtime observation and binary analysis complement each other. Do not invent a formula because the UI screenshots omit it.

## Check capability, not just configuration

Discover exposed MCP tools and locally installed executables/checkouts. Record separately: configured, callable, backend responding, intended artifact loaded, compatible analysis succeeded. Prefer an existing working analysis session; otherwise use a CLI. A successful MCP connection alone does not identify its loaded APK.

- **JADX MCP:** perform a small read such as manifest or main application names. Confirm identity against the target artifact. A plugin connection error means the GUI/plugin backend is unavailable; use installed JADX CLI for targeted extraction, or report the missing backend. Do not repeatedly retry unchanged failures.
- **Apktool MCP:** health/workspace inspection establishes whether decoding is available. An empty workspace is not decoded evidence. Decode to a fresh directory only when needed.
- **Ghidra:** discover actual MCP capabilities if exposed; otherwise find `support/analyzeHeadless` in the local installation. A GUI launcher is not a connected analysis session. Preserve existing projects and import into a fresh project without overwrite flags.
- **Blutter/r2flutter:** look for executable paths and known checkout scripts, not only PATH command names. Record unsupported ABI/snapshot separately from absent tools. Use local help and upstream compatibility guidance before expensive builds.

## Route by the code that owns the behavior

| Owner | Preferred analysis |
| --- | --- |
| Java/Kotlin DEX | JADX search → relevant method → callers/callees; Apktool Smali when decompilation is ambiguous |
| Flutter Dart AOT | Compatible available Blutter or r2flutter → object pools/strings/functions → targeted assembly and cross-references |
| Flutter Android wrapper/plugins | JADX for platform channels and native services; this does not recover Dart domain logic |
| Native C/C++ library | Ghidra/radare2 for relevant functions and their bridge |
| Assets/configuration | Archive/Apktool extraction; assets indicate possible content, not reachable behavior |

For Android ARM64 Blutter, keep `libapp.so` and its matching `libflutter.so` from the same artifact/ABI together. Blutter may compile a matching Dart runtime on its first run. Reuse that build and extraction output. Its `asm/`, `pp.txt`, and `objs.txt` are analysis evidence, not recovered Dart source. Check current [Blutter support](https://github.com/worawit/blutter) and [r2flutter support](https://github.com/radareorg/r2flutter) for the actual binary. Do not infer Dart version from an unrelated Flutter SDK string.

Ghidra is not a Dart-aware source recovery tool, but targeted ARM64 disassembly can supplement Flutter-aware extraction when symbol/object information is available. Avoid whole-engine decompilation as the default. Keep `libflutter.so` engine code distinct from `libapp.so` application code.

## One question → one trace → one contract

1. State the unknown and its implementation consequence: e.g. “Does saving a log preserve unedited fields?”
2. Search an observed anchor: storage key, UI label, channel method, class/function name, or distinctive constant. Scope JADX to app packages and paginate results. Search large AOT dumps on disk with `rg`; retrieve only relevant functions and immediate references.
3. Follow the values through input, branches, transformation, and output/side effect. Record binary hash, ABI, tool/version, artifact path, function/address, and exact supporting excerpt. A string or package name alone does not prove execution or ownership.
4. Write a small behavioral contract and a boundary fixture that would distinguish competing interpretations. Label static deductions as inferred until runtime checks confirm them. Trace original app code, not candidate code.
5. If two targeted probes add no evidence, record the specific blocker and switch evidence channel (runtime input/output, authorized storage inspection, channel trace, or matching symbols). Do not substitute guessed logic or repeat full extraction.

Keep these findings with the active journey's contract: `question | artifact/function | finding/status | distinguishing test | remaining gap`. Reuse extracted indexes keyed by binary hash, ABI, and tool version. Tool use is successful when it resolves a contract question, not when it produces a large dump.

For existing reports, verify that cited classes/functions belong to the target artifact. A Java citation inside a Flutter report may describe wrapper/plugin code or another app; establish ownership before adopting its algorithm. Do not infer complete dependency graphs from license notices or original widget composition from bundled assets.
