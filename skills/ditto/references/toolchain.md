# Required tool roles

The Android Flutter phase has one compulsory stack. Capability is established by verified MCP receipts, not configuration files, PATH entries, or prose claims.

| Capability | Required role | Required proof |
| --- | --- | --- |
| JADX MCP | DEX, manifest, wrapper, platform-channel analysis | Healthy bounded probe for the original APK SHA-256 |
| Apktool MCP | Resources, decoded XML, assets, Smali when needed | Healthy bounded probe for the same APK |
| r2Flutter MCP | Dart AOT object/function/cross-reference analysis | Supported ABI and Dart profile for the same APK |
| mobile-control MCP | Human-operated device capture, screenshot, hierarchy, and clone comparison | Required control probes for the contract target and environment |


The reconstruction agent uses these MCP interfaces. Their server implementations may invoke the underlying analyzers, Android SDK, emulator, or device bridge internally. Every selected result must retain MCP provenance and its originating session identity.
The browser recorder is the human interaction surface in the mobile-control MCP server, not a fifth service. It routes navigation through the controller and saves action and screenshot/XML candidates with package and session context. The AI selects trustworthy original candidates directly; an executable replay is not required. The same browser supports clone capture beside the selected original screenshot.

Use `inventory.py` only for a bounded, read-only archive summary before preflight or for diagnosis. It hashes the package, reports safe member statistics, framework indicators, assets, and ABIs. It does not replace any compulsory MCP probe or prove runtime behavior.

`diff_screenshots.py` is the deterministic local metric engine used by clone capture. It uses Pillow for PNGs and panel rendering and NumPy for the YIQ comparison, preserves panel resolution, writes the labeled triptych, and can compare paired hierarchy XML. The AI evaluates the current result and records the semantic judgment in the phase state.

Flutter implementation uses the project's pinned Flutter/Dart toolchain and Ditto's [Flutter build](flutter-build.md) and [stack](flutter-stack.md) guidance. Keep analyzer, unit/widget tests, and build verification proportionate to the implementation. The final parity evidence comes from a freshly identified packaged build captured through mobile-control.

If a required MCP is unavailable, invalid, attached to another package/device, or incompatible with the APK's ABI/profile, record the blocker and stop the phase. Installing and repairing these servers belongs in the MCP workspace; weakening the phase contract does not resolve missing capability.

For iOS, define an equivalent compulsory MCP contract before starting. Do not assume the Android capability set proves iOS extraction or runtime support.

## Portable local setup

Use Python 3.11+, uv, Java, JADX, Apktool, r2Flutter, and the Android SDK
(platform-tools, build-tools, emulator, and a compatible AVD). The MCP bridge
is local Python code; its external analyzers still need compatible installations.
Use the consolidated [setup command](commands.md#setup-and-emulator) to generate
standalone MCP JSON, merge the entries, and restart the client. The generator
needs no Bun or fixed checkout location.

SDK discovery uses `ANDROID_HOME` or `ANDROID_SDK_ROOT`, then the standard Linux
or Windows SDK location. Explicit `DITTO_ADB_BIN`, `DITTO_EMULATOR_BIN`, and
`DITTO_AAPT_BIN` override discovery. Analyzer executable overrides are documented
in the MCP integration reference. Java archives and supported Windows launchers
run with argument lists, including paths containing spaces.

Start/reuse the AVD through the mobile MCP; see [commands](commands.md#setup-and-emulator).
The MCP backend owns SDK discovery and emulator startup; the skill contains no
second launcher. Its shared Python implementation detects Windows/Linux automatically.
Use `gpu="software"` without GPU hardware; the default is `auto`. CPU virtualization
is a separate `accel="auto|on|off"` choice. Software rendering does not solve an
incompatible APK ABI or unsupported Dart profile. Never count a crashing app as a
successful mobile probe. Native Windows validation is a separate check.

Phase/image commands share a locked uv environment. `pyproject.toml` and `uv.lock` specify
Pillow and NumPy; uv installs binary wheels in an isolated environment. There is
one image implementation, no optional slow fallback. Transparent PNGs composite
on white; 16-bit grey values use their high byte. Screenshot panels keep native
resolution; only the overview is resized. Do not install these packages globally.

Analyzer exports are reusable for the same APK and tool version after integrity
validation; they do not expire by age. Query cached exports for relevant excerpts.
Each new capture records its live MCP session and device environment. Keep a device
capture within one browser session and do not mix images from different packages,
targets, or environments.
