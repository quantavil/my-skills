#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["uiautomator2==3.7.0"]
# ///
"""Run one behaviour experiment against an app and record a golden trace.

Usage:
  experiment.py SCRIPT.py --package PKG --label original|clone --out traces/ [--serial S] [--state]

SCRIPT.py defines `run(lab)`. The same script runs unchanged against the original
and the clone; only --package and --label differ. Results land in
  traces/<script-name>/<label>/<NN-step>/{screen.png, ui.xml, texts.json}
  traces/<script-name>/<label>/notes.json   (values recorded with lab.note)

Data capture (state.json, a root pull of the app's files) is off by default because it is
the slow part: ask for it at key steps with lab.capture(name, state=True), or for every
step with --state.

A script may also define GRID = [{"age_weeks": 8}, {"age_weeks": 12}] and run(lab, **params).
It then runs once per entry in the same process, each as its own experiment
traces/<script-name>__<params>/<label>/ (so diff.py and parity.py work unchanged).
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import shutil
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from adbutil import Adb  # noqa: E402
import capture_state  # noqa: E402


def visible_texts(hierarchy_xml: str) -> list[str]:
    """Text and content-desc of every node, top-to-bottom, left-to-right.

    Flutter exposes its Semantics labels as content-desc, so this covers Flutter,
    native and React Native screens alike. The status bar is skipped.
    """
    items = []
    for node in ET.fromstring(hierarchy_xml).iter("node"):
        if node.get("package") == "com.android.systemui":
            continue
        bounds = re.findall(r"\d+", node.get("bounds", "")) or ["0", "0"]
        for attr in ("text", "content-desc"):
            value = (node.get(attr) or "").strip()
            if value:
                items.append((int(bounds[1]), int(bounds[0]), value))
    seen, ordered = set(), []
    for _, _, value in sorted(items):
        if value not in seen:
            seen.add(value)
            ordered.append(value)
    return ordered


class Lab:
    def __init__(self, serial: str, package: str, out: Path, state: bool):
        import uiautomator2

        self.adb = Adb(serial)
        self.package = package
        self.out = out
        self.capture_state = state
        self.d = uiautomator2.connect(serial)
        self.step = 0
        self.notes: dict = {}

    def begin(self, out: Path) -> None:
        """Start a fresh trace folder (used between GRID cases in one process)."""
        self.out, self.step, self.notes = out, 0, {}

    # --- device and app control -------------------------------------------
    def snapshot_load(self, name: str) -> None:
        """Restore an emulator snapshot (saved with snapshot_save). ~2 s."""
        self.adb.run("emu", "avd", "snapshot", "load", name)
        self.adb.run("wait-for-device", timeout=60)
        self.d = __import__("uiautomator2").connect(self.adb.serial)

    def snapshot_save(self, name: str) -> None:
        self.adb.run("emu", "avd", "snapshot", "save", name)

    def offline(self, on: bool = True) -> None:
        verb = "disable" if on else "enable"
        self.adb.shell(f"svc wifi {verb}; svc data {verb}")

    def set_time(self, when: str) -> None:
        """Set the device clock to a local time like '2026-10-01 07:00' (needs root).

        Only the wall clock moves: monotonic timers, AlarmManager/WorkManager and server
        time do not follow. Restart the app (stop, launch) after a jump if it caches time.
        The timezone is fixed when the emulator starts (-timezone); see SKILL.md.
        """
        moment = datetime.fromisoformat(when)
        self.adb.shell("settings put global auto_time 0")  # undone by restore() at the end of a run
        self.adb.root_shell(f"date {moment:%m%d%H%M%Y.%S}")
        self.adb.shell("am broadcast -a android.intent.action.TIME_SET", check=False)

    def restore(self) -> None:
        """Undo what experiments change on the device: network back on, clock back to real time."""
        self.adb.shell("svc wifi enable; svc data enable", check=False)
        self.adb.shell("settings put global auto_time 1", check=False)
        self.adb.root_shell(f"date {datetime.now():%m%d%H%M%Y.%S}", check=False)
        self.adb.shell("am broadcast -a android.intent.action.TIME_SET", check=False)

    def launch(self, wait: float = 2.0) -> None:
        self.d.app_start(self.package, wait=True)
        time.sleep(wait)

    def stop(self) -> None:
        self.d.app_stop(self.package)

    def clear(self) -> None:
        """Wipe the app's data (fresh install state)."""
        self.d.app_clear(self.package)

    def push_state(self, raw_dir: str | Path) -> None:
        """Restore app data captured earlier (OUT/raw/<package>), e.g. after editing a DB.

        Seeds exact records without tapping through the UI. Same package only.
        """
        import tarfile
        import tempfile

        raw_dir = Path(raw_dir)
        uid = self.adb.app_uid(self.package)
        self.stop()
        with tempfile.NamedTemporaryFile(suffix=".tar") as archive_file:
            with tarfile.open(archive_file.name, "w") as archive:
                for child in raw_dir.iterdir():
                    if child.name not in ("cache", "code_cache", "lib"):
                        archive.add(child, arcname=child.name)
            self.adb.run("push", archive_file.name, "/data/local/tmp/ditto_state.tar")
        base = f"/data/data/{self.package}"
        self.adb.root_shell(
            f"cd {base} && rm -rf shared_prefs databases files app_flutter no_backup && "
            f"tar -xf /data/local/tmp/ditto_state.tar && chown -R {uid}:{uid} {base} && "
            f"restorecon -R {base} && rm /data/local/tmp/ditto_state.tar"
        )

    # --- interaction --------------------------------------------------------
    def find(self, label: str, timeout: float = 5.0):
        """Element whose text or content-desc equals, then contains, `label`."""
        deadline = time.time() + timeout
        while True:
            for selector in ({"text": label}, {"description": label},
                             {"textContains": label}, {"descriptionContains": label}):
                element = self.d(**selector)
                if element.exists:
                    return element
            if time.time() > deadline:
                raise LookupError(f"'{label}' not on screen; visible: {self.texts()[:30]}")
            time.sleep(0.3)

    def tap(self, label: str, timeout: float = 5.0) -> None:
        self.find(label, timeout).click()

    def type(self, text: str) -> None:
        self.d.send_keys(text, clear=True)

    def back(self) -> None:
        self.d.press("back")

    def texts(self) -> list[str]:
        return visible_texts(self.d.dump_hierarchy())

    def read(self, pattern: str) -> str | None:
        """First visible text matching a regex; returns group 1 if present."""
        regex = re.compile(pattern, re.S)
        for value in self.texts():
            match = regex.search(value)
            if match:
                return match.group(1) if match.groups() else match.group(0)
        return None

    def wait_idle(self, timeout: float = 4.0, interval: float = 0.4) -> None:
        """Wait until the UI hierarchy stops changing (animations, loading)."""
        deadline, previous = time.time() + timeout, None
        while time.time() < deadline:
            current = self.d.dump_hierarchy()
            if current == previous:
                return
            previous = current
            time.sleep(interval)

    def notifications(self) -> str:
        """Posted notifications of the app (title, text, actions) from dumpsys."""
        return self.adb.root_shell(f"dumpsys notification --noredact | grep -A25 'pkg={self.package}'", check=False)

    def alarms(self) -> str:
        """Alarms the app has scheduled (AlarmManager) from dumpsys."""
        return self.adb.root_shell(f"dumpsys alarm | grep -B1 -A6 '{self.package}'", check=False)

    # --- recording ----------------------------------------------------------
    def note(self, key: str, value, allow_none: bool = False) -> None:
        """Record an observed output, e.g. lab.note('next_nap', lab.read(r'Next nap\\s*(\\S+)')).

        None means nothing was read (bad regex, wrong screen) and raises unless allow_none.
        """
        if value is None and not allow_none:
            raise ValueError(f"note '{key}' is None: nothing matched; screen has {self.texts()[:20]}")
        self.notes[key] = value
        (self.out / "notes.json").write_text(json.dumps(self.notes, indent=1, ensure_ascii=False) + "\n")

    def capture(self, name: str, state: bool | None = None) -> Path:
        self.step += 1
        folder = self.out / f"{self.step:02d}-{re.sub(r'[^a-zA-Z0-9_-]+', '-', name)}"
        folder.mkdir(parents=True, exist_ok=True)
        self.wait_idle()
        self.d.screenshot(str(folder / "screen.png"))
        xml = self.d.dump_hierarchy()
        (folder / "ui.xml").write_text(xml)
        (folder / "texts.json").write_text(json.dumps(visible_texts(xml), indent=1, ensure_ascii=False) + "\n")
        if self.capture_state if state is None else state:
            capture_state.capture(self.adb, self.package, folder)
        return folder


def complete_trace(out: Path) -> bool:
    """A trace folder from a run that finished without error."""
    meta = out / "run.json"
    return meta.exists() and "error" not in json.loads(meta.read_text())


def case_name(stem: str, params: dict) -> str:
    """Experiment folder name for one GRID entry: stem__key-value__key-value."""
    if not params:
        return stem
    parts = (re.sub(r"[^a-zA-Z0-9._-]+", "-", f"{key}-{value}") for key, value in params.items())
    return stem + "__" + "__".join(parts)


def load_script(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not hasattr(module, "run"):
        raise SystemExit(f"{path} must define run(lab)")
    return module


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("script", type=Path)
    parser.add_argument("--package", required=True)
    parser.add_argument("--label", required=True, help="original or clone")
    parser.add_argument("--out", type=Path, default=Path("traces"))
    parser.add_argument("--serial", default="emulator-5556")
    parser.add_argument("--state", action="store_true", help="capture app data at every step (slow; needs root)")
    args = parser.parse_args()

    module = load_script(args.script)
    cases = getattr(module, "GRID", None) or [{}]
    outs = [args.out / case_name(args.script.stem, params) / args.label for params in cases]
    for out in outs:
        if complete_trace(out):
            raise SystemExit(f"{out} already has a finished trace; delete it or use another --label")
        if out.exists():  # left by a failed run: start over
            shutil.rmtree(out)
    lab = Lab(args.serial, args.package, outs[0], state=args.state)
    version, failures = None, []
    for params, out in zip(cases, outs):
        out.mkdir(parents=True, exist_ok=True)
        lab.begin(out)
        started, error = time.time(), None
        try:
            module.run(lab, **params)
        except Exception as exc:  # keep going: one bad case must not hide the others
            error = f"{type(exc).__name__}: {exc}"
            failures.append((out, error))
        if version is None:
            version = " ".join(lab.adb.shell(
                f"dumpsys package {args.package} | grep -E 'versionName|versionCode'", check=False).split())
        meta = {"script": str(args.script), "params": params, "package": args.package, "label": args.label,
                "serial": args.serial, "steps": lab.step, "seconds": round(time.time() - started, 1),
                "version": version, "started": datetime.now().isoformat(timespec="seconds")}
        if error:
            meta["error"] = error
        (out / "run.json").write_text(json.dumps(meta, indent=1) + "\n")
        print(f"{'FAILED' if error else 'ok'}: {lab.step} steps, notes={lab.notes} → {out}")
    lab.restore()
    if failures:
        for out, error in failures:
            print(f"  {out}: {error}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
