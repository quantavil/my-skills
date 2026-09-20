# Toolchain: selection, commands, outputs

Primary documentation checked 2026-09-14. These are operational defaults for Ditto, not claims that every tool is installed or every binary is supported. Use the installed release's help when flags differ; record the actual version or commit with each capture. Run only the branch needed for the task.

## Select the smallest working stack

| Input/task | Start with | Add when needed | Required result |
| --- | --- | --- | --- |
| Native Android APK | `apkanalyzer`, JADX, Apktool, ADB, Maestro | APKiD for protections; uiautomator2 for inspection; Ghidra for native JNI libraries; Frida for a specific runtime question | Decoded manifest/resources, relevant code evidence, recorded journey |
| Flutter Android APK | Archive inventory, Apktool, r2flutter, ADB, Maestro | Blutter for Android ARM64 ObjectPool/assembly; flutterdec for experimental pseudocode | Assets/wrapper, snapshot profile, runtime states |
| Native iOS IPA/app | `plutil`, `otool`, `dwarfdump`, `ipsw`; compatible original runtime | Ghidra/radare2 for unresolved native logic; Frida/Grapefruit for runtime internals | Bundle/entitlement inventory, symbol match, device/build feasibility |
| Flutter iOS app | iOS inventory, Flutter assets, r2flutter, compatible runtime | Native wrapper/channel inspection | Supported snapshot evidence and observed behavior; never route to Blutter |
| Network contract | Test backend logs or mitmproxy | Frida/Grapefruit when authorized and proxy capture is insufficient | Sanitized request/response/error fixtures |
| Flutter implementation | Flutter/Dart SDK, existing project tooling, Dart MCP if available | Packages in [flutter-stack.md](flutter-stack.md) | Analyzed, tested vertical feature |
| Differential validation | Maestro for original/candidate; Flutter tests for candidate | Patrol for candidate native UI; image comparator for checkpoints | Separate visual, behavioral, protocol, storage and platform results |

JADX reconstructs Java-like code from DEX; it does not guarantee complete decompilation. Use `--single-class` once a relevant class is known instead of repeatedly exporting everything. [JADX CLI](https://github.com/skylot/jadx)

APKiD identifies compiler/packer/protection signatures; it does not establish application behavior. MobSF is optional broad inventory, not a prerequisite for every feature. [APKiD](https://github.com/rednaga/APKiD), [MobSF](https://github.com/MobSF/Mobile-Security-Framework-MobSF)

## Local KVM Android Virtual Device (AVD) & ARM Translation

Use a configured local AVD for the frequent Android iteration loop. Check KVM
access, the installed system image, APK ABIs and actual original-app launch.
ARM translation availability and performance vary; neither an x86_64 Google APIs
image nor successful installation proves the original renders correctly. Record
launch success and any translation limitations instead of promising a frame rate.

Discover existing AVDs with `emulator -list-avds` before creating another.
Use `scripts/emulator_manager.sh` to reuse an explicitly selected AVD and serial
with bounded boot checks. Configure `DITTO_AVD` and SDK paths for the host.
Run both packages on the same emulator where IDs differ, and target every ADB
or Maestro operation explicitly (for example `adb -s emulator-5554 ...`).

Match recorded display/OS settings or collect fresh original/candidate baselines
on the same new environment. See [fast laptop iteration](parity.md#fast-laptop-iteration)
for install-once, hot-reload and checkpoint rules. Preserve physical-device
captures and keep remaining hardware checks explicit.

## Intake without installing mobile tools

From the reconstruction workspace, set `DITTO_SKILL` to this skill's directory and run:

```bash
python3 "$DITTO_SKILL/scripts/inventory.py" input/original.apk --output evidence/static/inventory.json
```

The bundled helper hashes the file, lists ZIP members, flags unsafe member paths, reports framework/ABI indicators, reads bounded iOS Info.plist metadata, and locates relevant executables on PATH. It does not extract files, execute tools, decode Android binary XML, or prove framework completeness. It refuses to overwrite output. Use `apkanalyzer` for Android identity.

For each selected tool, capture its version once and record its executable path. Start with `adb version`, `jadx --version`, `apktool --version`, `maestro --version`, and `flutter --version`; query only tools used by the chosen branch. A PATH entry is not a working device or server connection.

## Android extraction

Run from the reconstruction workspace after creating `input/original.apk`. Use a fresh output directory for each extraction run:

```bash
mkdir -p evidence/static/android
apkanalyzer apk summary input/original.apk > evidence/static/android/summary.txt
apkanalyzer manifest print input/original.apk > evidence/static/android/manifest.xml
apkanalyzer files list input/original.apk > evidence/static/android/files.txt
jadx -d evidence/static/android/jadx input/original.apk
apktool d input/original.apk -o evidence/static/android/apktool
```

Inspect `jadx/sources/` for relevant managed logic; `apktool/res/`, `assets/`, and `smali*/` for resources and fallback instructions. Record nonzero exit codes and partial outputs. Do not use force-overwrite flags to destroy prior evidence. [`apkanalyzer`](https://developer.android.com/tools/apkanalyzer), [Apktool decode options](https://apktool.org/docs/cli-parameters/)

For split APKs, obtain the complete applicable split set before installation; do not treat a successfully decoded base APK as a complete runtime. Framework indicators can coexist: DEX in a Flutter APK often belongs to its Android wrapper.

## Native library analysis with Ghidra (Optional)

Use Ghidra for relevant compiled C/C++ native shared libraries (`.so` in Android JNI, Mach-O in iOS). Prefer JADX for Java/Kotlin DEX and a compatible r2flutter/Blutter for Flutter AOT. Ghidra can supplement Flutter-aware extraction with targeted disassembly; it is not a Dart source decompiler. See [reverse-engineering.md](reverse-engineering.md) for MCP health checks and question-driven tracing.

To analyze an extracted JNI binary in headless non-interactive mode without launching the GUI:

```bash
mkdir -p evidence/static/native
DITTO_GHIDRA_PROJECT=$(mktemp -d -t ditto-ghidra-XXXXXX)
analyzeHeadless "$DITTO_GHIDRA_PROJECT" TempProj \
  -import evidence/static/android/apktool/lib/arm64-v8a/libnative-lib.so \
  -noanalysis
```

To run a headless post-analysis decompiler script and export decompiled C functions:

```bash
analyzeHeadless "$DITTO_GHIDRA_PROJECT" TempProj \
  -process libnative-lib.so \
  -postScript DecompileExport.java evidence/static/native/decompiled.c
```

Record the Ghidra version, target architecture, imported binary hash, and decompiled C output in `evidence/static/native/`. Keep native reversing tightly bounded to specific unresolved contract questions. [Ghidra Headless Analyzer](https://htmlpreview.github.io/?https://github.com/NationalSecurityAgency/ghidra/blob/master/Ghidra/RuntimeScripts/Common/support/analyzeHeadlessREADME.html)

## App Bundles and APK sets

An `.aab` is not directly installable. Use Google's `bundletool` to generate a device-specific `.apks` set. Set `BUNDLETOOL_JAR` to the downloaded release JAR and select the test device explicitly:

```bash
java -jar "$BUNDLETOOL_JAR" build-apks --bundle=input/original.aab --output=evidence/static/original.apks --connected-device --device-id="$ORIGINAL_SERIAL"
java -jar "$BUNDLETOOL_JAR" install-apks --apks=evidence/static/original.apks --device-id="$ORIGINAL_SERIAL"
```

Without signing options, bundletool attempts debug signing. Record that certificate difference: signature-dependent login, APIs, or updates may behave differently. Prefer a supplied matching signed APK set when those behaviors matter. A universal APK may omit non-fused feature modules; do not substitute it for complete split coverage. Inventory the generated archive and relevant contained APKs separately; the helper does not recursively inspect nested APKs. [Google bundletool documentation](https://developer.android.com/tools/bundletool)

## Flutter AOT commands and limits

Set `R2FLUTTER_BIN` to the built standalone executable and `AOT_BINARY` to the identified `libapp.so` or supported iOS bundle. Do not select a binary by guessing its Dart version.

```bash
mkdir -p evidence/static/flutter
"$R2FLUTTER_BIN" -jH "$AOT_BINARY" > evidence/static/flutter/header.json
"$R2FLUTTER_BIN" -f "$AOT_BINARY" > evidence/static/flutter/functions.txt
```

r2flutter accepts Android libraries/directories and iOS `.app` bundles; AArch64 is its primary target. Its current README requires radare2 6.2.2+ (or a qualifying 6.2.1 git build), and describes in-tree Dart layouts from 2.10 through 3.12. Layout presence is not a guarantee for every snapshot. Build with `make`; `make user-install` installs its radare2 plugin. Use `r2flutter -AAA` inside radare2 only when deeper references are needed. [README](https://github.com/radareorg/r2flutter), [support matrix](https://github.com/radareorg/r2flutter/blob/main/doc/support.md)

Blutter is an Android ARM64 extractor and can be the first AOT tool when already available and compatible. Keep both `libapp.so` and the matching engine in the extracted ABI directory. From the Blutter checkout:

```bash
python3 blutter.py "$ANDROID_ARM64_LIB_DIR" "$BLUTTER_OUTPUT_DIR"
```

Read `asm/`, `objs.txt`, and `pp.txt`. The tool may download and compile a matching Dart runtime; account for that cost before choosing it. Its generated Frida template is analysis material, not an app dependency. [Blutter](https://github.com/worawit/blutter)

For flutterdec, inspect first:

```bash
flutterdec info input/original.apk --json
flutterdec adapter list
```

If the reported snapshot has a supported registry entry, install its matching adapter using `flutterdec adapter install --dart-hash "$SNAPSHOT_HASH"`, then run:

```bash
flutterdec decompile input/original.apk -o evidence/static/flutter/flutterdec
```

Read `report.json`, `quality.json`, and `pseudocode/`. A nonzero quality exit may still leave outputs; preserve the failure and unresolved branches. Do not raise quality limits merely to call extraction successful. Its current prerelease is `v0.1.0-alpha.4`; packaged `bin/` and `share/` must stay together. This is experimental pseudocode, not recovered Dart. [flutterdec usage and adapter requirements](https://github.com/caverav/flutterdec)

## iOS inventory

After bounded archive inspection/extraction, set `IOS_APP` to the selected `.app` and `IOS_BINARY` to its `CFBundleExecutable` path. On macOS:

```bash
mkdir -p evidence/static/ios
plutil -p "$IOS_APP/Info.plist" > evidence/static/ios/plist.txt
otool -L "$IOS_BINARY" > evidence/static/ios/libraries.txt
xcrun dwarfdump --uuid "$IOS_BINARY" > evidence/static/ios/binary-uuid.txt
```

If a dSYM is supplied, compare its `dwarfdump --uuid` output with the binary. A matching product name is insufficient. [Apple symbol matching](https://developer.apple.com/documentation/xcode/locating-a-missing-debug-symbol-file)

For structured Mach-O inspection, including on supported non-macOS hosts:

```bash
ipsw macho info "$IOS_BINARY" --json > evidence/static/ios/macho.json
ipsw macho info "$IOS_BINARY" --ent > evidence/static/ios/entitlements.txt
```

[`ipsw` Mach-O commands](https://blacktop.github.io/ipsw/docs/guides/macho/)

Use local `xcrun simctl help` / `xcrun devicectl help` to choose deployment for the actual build. Do not install a device IPA into a simulator. If the current host has no Apple runtime, finish portable inventory and identify the required macOS/device handoff; do not claim an iOS build test.

## Runtime capture and MCP

Prefer connected MCP tools for exploration; save the resulting journey as a replayable flow. Standard stdio server definitions are:

```json
{
  "mcpServers": {
    "dart": {"command": "dart", "args": ["mcp-server"]},
    "maestro": {"command": "maestro", "args": ["mcp"]}
  }
}
```

Adapt this to the client's configuration format; do not overwrite existing server entries. Dart MCP operates on the Flutter implementation and SDK; Maestro operates the original/candidate device UI. Confirm server tools are exposed and a device is visible before relying on either. If MCP is unavailable, use the same CLI workflows. [Flutter setup](https://docs.flutter.dev/ai/get-started), [Maestro MCP maintained documentation](https://github.com/mobile-dev-inc/maestro-docs/blob/main/introduction/get-started/maestro-mcp.md)

Official Flutter/Dart agent resources are `flutter/agent-plugins` and `dart-lang/skills`. Use installed relevant skills; adding them is environment setup, not something every reconstruction must repeat. [Flutter agent setup](https://docs.flutter.dev/ai/get-started)

For Android, select a device explicitly. Set `ORIGINAL_SERIAL` from `adb devices -l`:

```bash
mkdir -p evidence/runtime/checkpoint-001
adb -s "$ORIGINAL_SERIAL" shell wm size > evidence/runtime/checkpoint-001/size.txt
adb -s "$ORIGINAL_SERIAL" shell wm density > evidence/runtime/checkpoint-001/density.txt
adb -s "$ORIGINAL_SERIAL" exec-out screencap -p > evidence/runtime/checkpoint-001/screen.png
```

Capture hierarchy through uiautomator2 when needed. In the Python environment with `uiautomator2` installed:

```python
import os
from pathlib import Path
import uiautomator2 as u2

device = u2.connect(os.environ['ORIGINAL_SERIAL'])
Path('evidence/runtime/checkpoint-001/hierarchy.xml').write_text(
    device.dump_hierarchy(), encoding='utf-8')
```

Export `ORIGINAL_SERIAL` for the Python process. The checkpoint must correspond to recorded setup/actions; a PNG alone does not prove a transition. [ADB](https://developer.android.com/tools/adb), [uiautomator2](https://github.com/openatx/uiautomator2)

Mobile MCP is a fallback for an already supported device configuration, especially when its screenshot/coordinate operations fill a gap. Check its actual exposed tools and platform prerequisites instead of installing a second driver automatically. [Mobile MCP](https://github.com/mobile-next/mobile-mcp)

## Network and runtime internals

Start a capture only after the test device is configured to reach the proxy and trust its inspection certificate in the authorized test environment:

```bash
mkdir -p private-captures
mitmdump --listen-host 127.0.0.1 --listen-port 8080 -w private-captures/original.mitm
```

Loopback binding requires a local route/tunnel for the device; otherwise bind the specific reachable test interface. Verify a known test request reaches the proxy before crawling. Retain raw capture privately and create sanitized fixtures for `evidence/runtime/`. `-w` writes flows; it does not configure Android/iOS trust or defeat pinning. [mitmproxy options](https://docs.mitmproxy.org/stable/concepts/options/)

For an authorized instrumentation environment, `frida-ps -U` is an initial process-list check. Match host/server versions and device ABI; a stock non-rooted Android app may require a permitted Gadget/repackaging workflow instead of server attachment. [Frida Android setup](https://frida.re/docs/android/)

Grapefruit provides SQLite/filesystem inspection and Flutter platform-channel monitoring through a web UI, backed by Frida. Its checked README requires Node.js 22.18+ for npm use and a Frida server on the device. Install `igf` only if this inspection is needed, then run `igf --host 127.0.0.1 --project private-captures/grapefruit --no-open`. Confirm attachment before promising database or channel data. [Grapefruit](https://github.com/ChiChou/grapefruit)

For each instrumentation question, record the hook target and the specific fact it can establish. Capturing TLS plaintext does not recover an HMAC secret, guarantee visibility into custom crypto, or validate bypassed authentication. Keep altered-run evidence distinct from the unmodified baseline.
