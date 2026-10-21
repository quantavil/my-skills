---
name: ditto
description: Use when cloning an Android app (APK or Play listing) by functional reverse engineering - cataloguing its features, recovering its data model, and recording its behaviour as golden traces that the rebuilt app must reproduce. Works for Flutter, native and React Native apps.
---

# Ditto: clone an app by its behaviour

Treat the original app as a **black box and test oracle**. Do not try to recover its source code. Find out what it has (catalog), what it stores (data model) and what it outputs for given inputs (experiments). Then build a clone that reproduces those outputs, and measure that it does.

Static disassembly is a **tie-breaker**: use it when experiments leave two candidate rules and you need one constant or branch. Experiments stay the main road; disassembly never decides a rule alone, a confirming experiment does.

Analysis and experiments use plain CLIs: `apktool`, `adb`, `sqlite3`, Python `uiautomator2` (pulled in by `uv run`). Scripts live in `scripts/` next to this file; call them by absolute path.

While building the clone (step 5), use two MCP servers when the client has them:
- **dart** (`dart mcp-server`): analyze, hot reload/restart, widget inspector and runtime errors for a Flutter clone. Its roots are the session's folders, so open the session in the clone folder.
- **codebase-memory**: index the clone once (`index_repository`), then `search_graph`/`trace_path` to find where a rule or screen lives before changing it.

Never wrap the analysis tools above in an MCP.

## One folder per clone

Everything for one app lives in **one folder**: `~/Documents/<name>-clone/`, where `<name>` is what the user calls it, else the app's short name (`baby-tracker-clone`). Never scatter APKs, captures or evidence into other folders under `~/Documents`.

```
<name>-clone/
  apk/            x86_64 Play delivery: base.apk + splits (gitignored)
  apk-arm64/      verified ARM64 build of the same version, for Blutter (gitignored)
  research/       inventory/ (catalog.md…), state/ captures (gitignored), data-model.md
  experiments/    *.py behaviour experiments (run(lab))
  traces/         golden traces: <experiment>/original|clone/ (raw/ gitignored)
  parity.md       scorecard
  lib/ or src/, test/, android/ …   the clone app, in its framework's normal layout
```

Run every command from that folder so relative paths land inside it. Gitignore `/apk/`, `/apk-arm64/`, `/research/state/`, `/traces/**/raw/` and `/traces/**/state.json` (they can hold account data and tokens).

## Setup (once per machine)

One emulator does everything: a **Google Play** image (so Play-protected apps run and APKs download) rooted with **Magisk via rootAVD** (so data capture, seeding and clock control work). Plain `google_apis` images can `adb root` but many apps refuse to run there ("Check that Google Play is enabled…" = Play automatic integrity protection), so don't use them.

```bash
sdkmanager "system-images;android-34;google_apis_playstore;x86_64"
avdmanager create avd -n ditto2_play_x86_64 -k "system-images;android-34;google_apis_playstore;x86_64" -d pixel_6
emulator -avd ditto2_play_x86_64 -port 5556 -timezone Asia/Kolkata -no-boot-anim &   # sign in to Play once
git clone --depth 1 https://gitlab.com/newbit/rootAVD.git ~/.local/share/ditto-toolchain/rootAVD
cd ~/.local/share/ditto-toolchain/rootAVD
ANDROID_SERIAL=emulator-5556 ./rootAVD.sh system-images/android-34/google_apis_playstore/x86_64/ramdisk.img
```

rootAVD patches the image's `ramdisk.img` (stock copy kept as `ramdisk.img.backup`; copy it back to unroot) and shuts the emulator down. Cold-boot it (`-no-snapshot-load`), open the Magisk app, accept "Requires additional setup" (it reboots), then run `adb shell su -c id` and, in Magisk › Superuser, switch **Shell** on. Use the current Magisk: if the bundled `Magisk.zip` is old, update the app from inside Magisk, pull its APK (`adb shell pm path com.topjohnwu.magisk`) over `Magisk.zip`, restore the stock ramdisk and rerun rootAVD. Old snapshots are invalid after patching.

The scripts get root through `su` automatically (or `adb root` where adbd allows it). Fix the timezone at launch (`-timezone`); experiments then set only the clock. Default serial is `emulator-5556`; add `-no-window` to run headless. Never patch the target APK to get past a check.

## 1. Get the APK

From Play, on the signed-in Play emulator:

```bash
scripts/download-play-apks.sh 'https://play.google.com/store/apps/details?id=PKG' apk emulator-5556 x86_64
```

It copies what Play installed on the emulator (it never talks to Play itself), so install the app from the listing first. Keep base + splits together; experiments run on this emulator, against the Play-installed app. Play delivers the build matching the emulator's ABI, so this is the x86_64 build; an ARM64 emulator cannot run on an x86_64 host (the Android emulator refuses it). Step 1b gets the ARM64 build.

## 1b. Get the ARM64 build (required for Flutter apps)

Do this for every Flutter app **before step 2 ends**, and for other apps when you may need a disassembler. It is not optional and not "later": the x86_64 build cannot be read by Blutter, and the version must match what experiments run, so fetch it now. Obtain it by any of these, in this order:

1. **A real ARM64 phone** with the app from Play: `adb -s PHONE shell pm path PKG`, then `adb -s PHONE pull` each path into `apk-arm64/` (base + `split_config.arm64_v8a.apk`).
2. **A mirror**: APKMirror, APKPure or Uptodown. Pick the **same versionName and versionCode** as the Play copy and the arm64-v8a variant. Bundles (`.apkm`, `.xapk`) are zip files: unzip each into its own new, empty directory `apk-arm64/` and keep only the `.apk` files. Treat the download as untrusted: never install it, open it only with the scripts here, and pass `-I` to any Python that reads it.
3. Another source of the developer's own build.

Then verify it, always:

```bash
python3 -I scripts/check_arm64.py apk apk-arm64 --source phone    # or apkmirror / apkpure / uptodown
```

It rejects the copy unless the package and versionCode equal the Play copy, the signing certificate SHA-256 equals it (so the file is the developer's build, not a repack), and an `lib/arm64-v8a/*.so` exists. On success it writes `apk-arm64/acquisition-arm64.json` with file hashes and the source. Do not start step 2 without that file for a Flutter app; if no source works, stop and tell the user which versionCode is missing. Gitignore `/apk-arm64/`.

## 2. Catalog: what exists

```bash
python3 -I scripts/inventory.py apk/base.apk apk/split_*.apk -o research/inventory
```

Seconds, no disassembly. For native apps the dex string constants feed the UI text list, and for React Native the bundle's string literals, module paths and `*Screen`/`*Dialog`/`*Modal` component names (Hermes bytecode keeps them as plain strings) feed the feature tree. `catalog.md` lists framework, storage and cloud stack, notifications, widgets, payments, deep links, permissions, and a **feature tree**. For Flutter, every `package:<app>/...dart` path survives in `libapp.so`, so folders like `domain/schedule/` and files like `skip_nap_dialog` name the features. `strings.txt` holds the UI text (all languages, ASCII first), including error messages that hint at rules.

Then use the original app (drive it with `experiment.py` or by hand) and confirm each catalog item. Add what is only visible at runtime: onboarding, empty states, notifications, settings effects. The confirmed list becomes the rows of `parity.md` (step 6).

## 3. Data model: what it stores

Create a few real records in the original, then:

```bash
python3 -I scripts/capture_state.py PKG research/state/after-first-records
```

It pulls `/data/data/PKG` (needs root) to `raw/` and decodes to `state.json`: shared_prefs, every SQLite table (schema + rows), the **Firestore offline cache** (documents, pending writes and overlays decoded from protobuf), plus a size list of other files (Hive, Isar, ObjectBox: inspect those by hand). Capture before and after one action to see exactly what it writes. Write the recovered schema, units, enums and defaults into the clone's `research/data-model.md`.

Use the app **offline** or with a disposable account. Cloud writes cannot be undone by an emulator snapshot, so never experiment on the user's real account.

## 4. Experiments: how inputs become outputs

An experiment is a small Python file with `run(lab)`:

```python
# experiments/next_nap_after_short_nap.py
def run(lab):
    lab.snapshot_load("onboarded")          # known state in ~2 s
    lab.offline()
    lab.set_time("2026-10-01 07:00")
    lab.launch()
    lab.tap("Woke up")
    lab.set_time("2026-10-01 09:00"); lab.tap("Start nap")
    lab.set_time("2026-10-01 09:20"); lab.tap("Stop")
    lab.capture("after-short-nap")          # screen.png, ui.xml, texts.json, state.json
    lab.note("next_nap", lab.read(r"Next nap\s*(\d{1,2}:\d{2})"))
```

```bash
uv run scripts/experiment.py experiments/next_nap_after_short_nap.py --package ORIGINAL_PKG --label original --out traces
```

`Lab` API: `snapshot_save/load`, `offline`, `set_time`, `launch`, `stop`, `clear`, `push_state(raw_dir)` (seed exact records: capture, edit the pulled DB locally with sqlite3, push back), `tap(label)` (text or content-desc, exact then contains), `find`, `type`, `back`, `texts()`, `read(regex)`, `wait_idle()`, `notifications()`, `alarms()`, `capture(name)`, `note(key, value)`, and `lab.d` for raw uiautomator2.

Rules the tools enforce:
- `note()` raises on `None` (the regex found nothing), so a broken read cannot pass. `diff.py` also fails on empty notes.
- `set_time` moves only the wall clock (plus a `TIME_SET` broadcast). Monotonic timers, AlarmManager/WorkManager and server time do not follow: restart the app after a jump, check `lab.alarms()`, and treat server-timestamped output as untestable offline.
- `capture()` waits for the UI to settle; `diff.py` ignores the status and nav bars.
- Data capture (`state.json`, a root pull) is **off by default** because it is the slow part. Ask for it where it matters: `lab.capture("after-short-nap", state=True)`, or `--state` for every step. The pull checks the app's file listing before and after and retries only if something was written meanwhile.
- **Seed instead of tapping.** Build a fixture once (onboarded, with a few records), `capture_state.py` it, and begin each experiment with `lab.push_state("research/state/fixture/raw/PKG")`. Edit the pulled database with `sqlite3` to set up exact records.
- **Grids.** For a rule that depends on numbers, define `GRID = [{"age_weeks": 8}, {"age_weeks": 12}]` and `def run(lab, age_weeks):` in the experiment file. One command runs every entry in one process, each saved as its own experiment (`traces/<name>__age_weeks-8/...`), so `diff.py` and `parity.py` work unchanged.
- Backend-driven rules (computed on a server) are out of reach offline. Say so in `parity.md` rather than guessing; a proxy (mitmproxy) works only where the app does not pin certificates, and the APK is never patched to change that.

Design experiments like a scientist:
- **Vary one input at a time** from a fixed snapshot: empty vs accumulated history, settings toggles, short/late/skipped/overlapping entries, edit, delete, kill and reopen, midnight and overnight boundaries, invalid input.
- For a computed output, write the hypothesis first ("next nap = wake + window(age)"), then choose inputs whose outputs differ between candidate rules. Run a **grid** in a loop when the rule depends on numbers.
- `note()` every value the clone must reproduce. Notes, not screenshots, are the behaviour verdict.
- Name experiments by behaviour, not by screen. Keep traces; never overwrite an `original` trace (the script refuses).

## 5. Build the clone to be testable the same way

- Pure domain core (models, rules, persistence) separate from UI, with an **injectable clock**.
- Reuse the original's visible labels or accessibility labels, so the same experiment file drives both apps.
- A debug-only hook to seed and dump state, or use `push_state` with the clone's own captured data.
- Implement from the data model and the traces. Each rule cites the experiments that pinned it. Unit tests use the original's noted values as expected results, never the clone's current output.
- Clean-room: redraw icons and artwork and use licensed fonts. Do not ship the original's code or assets unless the user explicitly accepts that.

Then replay and compare:

```bash
uv run scripts/experiment.py experiments/X.py --package CLONE_PKG --label clone --out traces
uv run scripts/diff.py traces/X        # notes must match; texts diff; pixel % + diff.png
```

## 6. Scorecard: measure, never estimate

Generate `parity.md`; do not type it. List the confirmed catalog items in `research/features.json` (`{"Next nap prediction": {"present": true, "experiments": ["next_nap_short"]}}`), then:

```bash
uv run scripts/parity.py .
```

It reads every `traces/<experiment>/{original,clone}`, writes `parity.md` and `parity.json`, and exits 1 if any count is lower than the previous `parity.json`. The table looks like:

| Feature | Experiments | Status |
|---|---|---|
| Next nap prediction | next_nap_* (14) | 12/14 match |

Report three numbers separately: **breadth** (catalog items present), **behaviour** (experiments whose notes match), **visual** (steps under the pixel threshold). Never lower a number already reached; rerun affected experiments after every change. Passing clone-only tests or a matching screenshot are not parity. The generator enforces the never-lower rule.

## When to use static analysis

Use it for a specific question that experiments cannot settle cheaply (an exact threshold, a hidden branch, a constant, a server endpoint), or to narrow candidate rules before designing a grid. Read `strings.txt`/`sources.txt` first.

- **Flutter:** the x86_64 `libapp.so` is enough for strings, the feature tree and the Dart package layout (the catalog already uses it). Blutter reads only ARM64 `libapp.so`, which Play delivers only to an ARM64 device, and the emulator cannot be ARM64 on an x86_64 host. The ARM64 copy in `apk-arm64/` (step 1b, verified by `check_arm64.py`) is required, so run Blutter on its `lib/arm64-v8a/libapp.so` (a source build under `~/.local/share/ditto-toolchain/blutter`: ask the user before building) and write the output to `research/blutter/`. Take the one constant, then confirm it with an experiment and cite that experiment next to the rule.
- **Native:** `jadx` on the specific class.
- **React Native (Hermes):** decompile with `hbc-decompiler` only for the specific function, then confirm with an experiment.
