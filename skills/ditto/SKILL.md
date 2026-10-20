---
name: ditto
description: Use when cloning an Android app (APK or Play listing) by functional reverse engineering - cataloguing its features, recovering its data model, and recording its behaviour as golden traces that the rebuilt app must reproduce. Works for Flutter, native and React Native apps.
---

# Ditto: clone an app by its behaviour

Treat the original app as a **black box and test oracle**. Do not try to recover its source code. Find out what it has (catalog), what it stores (data model) and what it outputs for given inputs (experiments). Then build a clone that reproduces those outputs, and measure that it does.

Static disassembly is a **tie-breaker only**: use it when experiments leave two candidate rules and you need one constant or branch. Never make it the main road.

All tools are plain CLIs (no MCP server): `apktool`, `adb`, `sqlite3`, Python `uiautomator2` (pulled in by `uv run`). Scripts live in `scripts/` next to this file; call them by absolute path.

## Setup (once per machine)

Data capture and seeding need **root**, so experiments run on a `google_apis` image. Play Store images refuse `adb root`; use them only to download APKs.

```bash
sdkmanager "system-images;android-34;google_apis;x86_64"
avdmanager create avd -n ditto_root_x86_64 -k "system-images;android-34;google_apis;x86_64" -d pixel_6
emulator -avd ditto_root_x86_64 -port 5558 -timezone Asia/Kolkata -no-boot-anim &
adb -s emulator-5558 root
```

Fix the timezone at launch (`-timezone`); experiments then set only the clock. Default serial in the scripts is `emulator-5558`. Add `-no-window` to run headless.

## 1. Get the APK

From Play, on a signed-in Play emulator:

```bash
scripts/download-play-apks.sh 'https://play.google.com/store/apps/details?id=PKG' ./apks/PKG-x86_64 emulator-5556 x86_64
```

It opens the listing if the app is absent; install it there and rerun. Keep base + splits together. Install on the root emulator with `adb -s emulator-5558 install-multiple base.apk split_*.apk`.

**If the app shows "Check that Google Play is enabled…" on the root emulator**, it uses Play's automatic integrity protection and runs only where the Play Store is present. Do not patch the APK. Either run experiments on the Play emulator with `--no-state` (no data capture or seeding), or root the Play emulator (for example with Magisk via rootAVD) after the user approves that download.

## 2. Catalog: what exists

```bash
python3 -I scripts/inventory.py base.apk split_*.apk -o research/inventory
```

Seconds, no disassembly. `catalog.md` lists framework, storage and cloud stack, notifications, widgets, payments, deep links, permissions, and a **feature tree**. For Flutter, every `package:<app>/...dart` path survives in `libapp.so`, so folders like `domain/schedule/` and files like `skip_nap_dialog` name the features. `strings.txt` holds the UI text (all languages, ASCII first), including error messages that hint at rules.

Then use the original app (drive it with `experiment.py` or by hand) and confirm each catalog item. Add what is only visible at runtime: onboarding, empty states, notifications, settings effects. The confirmed list becomes the rows of `parity.md` (step 6).

## 3. Data model: what it stores

Create a few real records in the original, then:

```bash
python3 -I scripts/capture_state.py PKG research/state/after-first-records
```

It pulls `/data/data/PKG` (needs root) to `raw/` and decodes to `state.json`: shared_prefs, every SQLite table (schema + rows), the **Firestore offline cache** (documents, pending writes and overlays decoded from protobuf), plus a size list of other files (Hive, Isar, ObjectBox: inspect those by hand). Capture before and after one action to see exactly what it writes. Write the recovered schema, units, enums and defaults into the clone's `docs/data-model.md`.

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

`Lab` API: `snapshot_save/load`, `offline`, `set_time`, `launch`, `stop`, `clear`, `push_state(raw_dir)` (seed exact records: capture, edit the pulled DB locally with sqlite3, push back), `tap(label)` (text or content-desc, exact then contains), `find`, `type`, `back`, `texts()`, `read(regex)`, `capture(name)`, `note(key, value)`, and `lab.d` for raw uiautomator2.

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

Keep `parity.md` in the clone repo: one row per catalog item.

| Feature | Experiments | Status |
|---|---|---|
| Next nap prediction | next_nap_* (14) | 12/14 match |

Report three numbers separately: **breadth** (catalog items present), **behaviour** (experiments whose notes match), **visual** (steps under the pixel threshold). Never lower a number already reached; rerun affected experiments after every change. Passing clone-only tests or a matching screenshot are not parity.

## When to use static analysis

Only for a specific question that experiments cannot settle cheaply (an exact threshold, a hidden branch, a server endpoint). Read `strings.txt`/`sources.txt` first. For Flutter AOT, Blutter (ARM64 `libapp.so`) dumps the object pool and annotated functions. Look up the one function, take the constant, and confirm it with an experiment. For native apps, `jadx` on the specific class.
