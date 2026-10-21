#!/usr/bin/env python3
"""Draft a feature catalog from an APK in seconds, without disassembly.

Usage: inventory.py BASE.apk [SPLIT.apk ...] -o OUT_DIR

Writes:
  OUT_DIR/catalog.md      draft catalog: app facts, storage stack, feature tree, manifest
  OUT_DIR/inventory.json  the same data, machine-readable
  OUT_DIR/strings.txt     candidate UI strings (all languages; English first)
  OUT_DIR/sources.txt     every app source path / class found
  OUT_DIR/apktool/        decoded manifest and resources (apktool -s, no smali)

Flutter: the AOT snapshot keeps every `package:<app>/...dart` path and string
literal, so the feature tree and UI text come straight out of libapp.so.
Native: class names come from the DEX string table and text from res/values.
React Native: text comes from the JS bundle.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path
from zipfile import ZipFile

ANDROID = "{http://schemas.android.com/apk/res/android}"

# Dart/Android libraries that reveal how the app stores, syncs and notifies.
SIGNALS = {
    "storage": ["sqflite", "sqflite_common", "drift", "hive", "hive_flutter", "isar", "objectbox",
                "realm", "shared_preferences", "flutter_secure_storage", "sembast", "floor",
                "androidx.room", "io.realm", "com.tencent.mmkv"],
    "cloud": ["cloud_firestore", "firebase_database", "firebase_auth", "supabase_flutter",
              "amplify_flutter", "com.google.firebase.firestore", "com.google.firebase.database"],
    "notifications": ["flutter_local_notifications", "awesome_notifications", "firebase_messaging"],
    "widgets": ["home_widget", "android.appwidget"],
    "payments": ["purchases_flutter", "in_app_purchase", "com.revenuecat", "com.android.billingclient",
                 "superwall", "adapty_flutter"],
    "charts": ["fl_chart", "syncfusion_flutter_charts", "charts_flutter", "com.github.mikephil"],
    "state": ["flutter_bloc", "bloc", "provider", "riverpod", "flutter_riverpod", "get", "mobx"],
}
UI_SCREEN = re.compile(r"(screen|page|dialog|sheet|tab|view|activity|fragment)s?$", re.I)
CODE_LIKE = re.compile(r"[_{}<>\[\]\\|=;$@#]|::|\.dart|https?:|^[a-z]+[A-Z]|\(\)|^\S+$")


# ------------------------------------------------------------ extraction --

def printable_runs(data: bytes, minimum: int = 4) -> list[str]:
    """Valid UTF-8 runs plus UTF-16LE runs (Dart two-byte strings)."""
    found = []
    utf8_char = rb"(?:[\x20-\x7e]|[\xc2-\xdf][\x80-\xbf]|[\xe0-\xef][\x80-\xbf]{2}|[\xf0-\xf4][\x80-\xbf]{3})"
    for match in re.finditer(utf8_char + rb"{%d,}" % minimum, data):
        found.append(match.group().decode("utf-8", errors="replace"))
    for match in re.finditer(rb"(?:[\x20-\x7e\xa0-\xff][\x00]|[\x00-\xff][\x01-\x30]){%d,}" % minimum, data):
        text = match.group().decode("utf-16-le", errors="ignore")
        if sum(ch.isalpha() for ch in text) > len(text) * 0.5:
            found.append(text)
    return found


def dex_strings(data: bytes) -> list[str]:
    """Every string in a DEX file's string table."""
    if not data.startswith(b"dex\n"):
        return []
    count = int.from_bytes(data[0x38:0x3C], "little")
    offset = int.from_bytes(data[0x3C:0x40], "little")
    out = []
    for index in range(count):
        position = int.from_bytes(data[offset + 4 * index: offset + 4 * index + 4], "little")
        while position < len(data) and data[position] & 0x80:  # skip uleb128 length
            position += 1
        end = data.find(b"\x00", position + 1)
        out.append(data[position + 1:end].decode("utf-8", errors="replace"))
    return out


def ui_strings(candidates: list[str]) -> list[str]:
    keep = []
    for text in candidates:
        text = text.strip()
        words = text.split()
        if len(words) < 2 or len(text) > 400 or CODE_LIKE.search(text):
            continue
        if sum(ch.isalpha() for ch in text) < len(text) * 0.6:
            continue
        keep.append(text)
    unique = list(dict.fromkeys(keep))
    # ASCII (usually English) first, then everything else.
    return sorted(unique, key=lambda s: (not s.isascii(), s.lower()))


HERMES_MAGIC = bytes.fromhex("c61fbc03c1031919")  # little-endian 0x1F1903C103BC1FC6
JS_STRING = re.compile(r"\"([^\"\\\n]{4,300})\"|'([^'\\\n]{4,300})'")
JS_MODULE = re.compile(r"[\"']((?:\./|src/|app/|screens?/|components?/)[\w/.-]+?)\.(?:jsx?|tsx?)[\"']")
RN_COMPONENT = re.compile(r"\b([A-Z][A-Za-z0-9]{2,}(?:Screen|Dialog|Modal|Sheet|Tab|Page|Form|Card|Picker|Navigator))\b")


def bundle_info(data: bytes) -> tuple[str, list[str], list[str]]:
    """React Native bundle -> (kind, UI text candidates, source names).

    Hermes bytecode keeps its string table as plain UTF-8/UTF-16, so printable runs find the
    text and component names. A plain Metro bundle also has string literals and module paths.
    Component and module names become feature-tree entries under `rn.`.
    """
    hermes = data.startswith(HERMES_MAGIC)
    texts = printable_runs(data)
    sources = {f"rn.{m}" for run in texts for m in RN_COMPONENT.findall(run)}
    if not hermes:
        text = data.decode("utf-8", errors="replace")
        texts += [a or b for a, b in JS_STRING.findall(text)]
        sources |= {"rn." + m.lstrip("./").replace("/", ".") for m in JS_MODULE.findall(text)}
        sources |= {f"rn.{m}" for m in RN_COMPONENT.findall(text)}
    return ("hermes" if hermes else "js"), texts, sorted(sources)


def apktool_version(path: Path) -> tuple[str | None, str | None]:
    """(versionName, versionCode) from apktool.yml; the decoded manifest often lacks versionName."""
    if not path.exists():
        return None, None
    text = path.read_text()
    name, code = re.search(r"versionName: *(\S+)", text), re.search(r"versionCode: *(\d+)", text)
    return (name.group(1).strip("'\"") if name else None, code.group(1) if code else None)


GENERATED = re.compile(r"\.(g|mapper|freezed|gr|gen|config)$")


def class_name(descriptor: str) -> str:
    """'Lcom/app/Foo$Bar;' -> 'com.app.Foo': inner and lambda classes count as their outer class."""
    return descriptor[1:-1].replace("/", ".").split("$")[0]


def own_prefix(package: str, sources: list[str]) -> str:
    """Package prefix that selects the app's own classes: the full package, else its first two parts."""
    if sum(s.startswith(package + ".") for s in sources) >= 10:
        return package + "."
    return ".".join(package.split(".")[:2]) + "."


def parse_manifest(path: Path) -> dict:
    root = ET.parse(path).getroot()
    app = root.find("application")
    info: dict = {
        "package": root.get("package"),
        "version": root.get(f"{ANDROID}versionName") or root.get("platformBuildVersionName"),
        "permissions": sorted({e.get(f"{ANDROID}name") for e in root.iter("uses-permission")}),
        "activities": [], "deep_links": [], "receivers": [], "services": [], "widgets": [],
    }
    if app is None:
        return info
    for activity in app.iter("activity"):
        name = activity.get(f"{ANDROID}name")
        info["activities"].append(name)
        for data in activity.iter("data"):
            scheme, host = data.get(f"{ANDROID}scheme"), data.get(f"{ANDROID}host")
            if scheme:
                info["deep_links"].append(f"{scheme}://{host or ''}{data.get(f'{ANDROID}pathPrefix') or ''}")
    for receiver in app.iter("receiver"):
        name = receiver.get(f"{ANDROID}name")
        info["receivers"].append(name)
        if any(m.get(f"{ANDROID}name") == "android.appwidget.provider" for m in receiver.iter("meta-data")):
            info["widgets"].append(name)
    info["services"] = [s.get(f"{ANDROID}name") for s in app.iter("service")]
    info["deep_links"] = sorted(set(info["deep_links"]))
    return info


def resource_strings(apktool_dir: Path) -> dict[str, str]:
    path = apktool_dir / "res/values/strings.xml"
    if not path.exists():
        return {}
    return {e.get("name"): "".join(e.itertext()) for e in ET.parse(path).getroot().iter("string")}


# --------------------------------------------------------------- analysis --

def analyse(apks: list[Path], out: Path) -> dict:
    framework, app_sources, packages, raw_strings, assets = "native", [], Counter(), [], []
    rn_kind, code_strings = "", []
    for apk in apks:
        with ZipFile(apk) as archive:
            for name in archive.namelist():
                if name.endswith("/libapp.so"):
                    framework = "flutter"
                    data = archive.read(name)
                    for uri in re.findall(rb"package:([a-z0-9_]+)/([A-Za-z0-9_/.]+?\.dart)", data):
                        packages[uri[0].decode()] += 1
                        app_sources.append(f"{uri[0].decode()}/{uri[1].decode()}")
                    raw_strings += printable_runs(data)
                elif name == "assets/index.android.bundle":
                    framework = "react-native"
                    kind, texts, sources = bundle_info(archive.read(name))
                    rn_kind = kind
                    raw_strings += texts
                    app_sources += sources
                elif re.fullmatch(r"classes\d*\.dex", name) and framework != "flutter":
                    for value in dex_strings(archive.read(name)):
                        if value.startswith("L") and value.endswith(";"):
                            app_sources.append(class_name(value))
                        else:
                            code_strings.append(value)
                elif name.startswith(("assets/flutter_assets/", "assets/")) and not name.endswith("/"):
                    assets.append(name)

    apktool_dir = out / "apktool"
    manifest: dict = {}
    if shutil.which("apktool"):
        subprocess.run(["apktool", "d", "-s", "-f", "-o", str(apktool_dir), str(apks[0])],
                       check=True, capture_output=True)
        manifest = parse_manifest(apktool_dir / "AndroidManifest.xml")
        name, code = apktool_version(apktool_dir / "apktool.yml")
        manifest["version"] = name or manifest.get("version")
        manifest["version_code"] = code
        res = resource_strings(apktool_dir)
        raw_strings += list(res.values())
    else:
        print("warning: apktool not found; manifest, permissions, widgets and resources are skipped", file=sys.stderr)
        res = {}

    app_package = manifest.get("package") or ""
    if framework == "flutter" and packages:
        # The app's own Dart package is the one with the most source files.
        own = max(packages, key=lambda p: (p not in ("flutter",), packages[p]))
        app_sources = sorted({s for s in app_sources if s.startswith(own + "/")})
        libraries = sorted(p for p in packages if p != own)
    else:
        own = app_package
        prefix = own_prefix(app_package, app_sources) if app_package else ""
        libraries = sorted({".".join(s.split(".")[:3]) for s in app_sources if not s.startswith((prefix, "rn."))})
        app_sources = sorted({s for s in app_sources if s.startswith((prefix, "rn."))})

    def uses(name: str) -> bool:
        return any(lib == name or lib.startswith(name + ".") for lib in libraries)

    signals = {kind: sorted(n for n in names if uses(n)) for kind, names in SIGNALS.items()}
    if manifest.get("widgets"):
        signals["widgets"].append("android.appwidget")
    firebase = {k: v for k, v in res.items() if k in ("project_id", "google_app_id", "firebase_database_url", "gcm_defaultSenderId")}

    return {
        "package": app_package, "version": manifest.get("version"), "framework": framework, "bundle": rn_kind,
        "source_package": own, "signals": signals, "libraries": libraries, "firebase": firebase,
        "manifest": manifest, "sources": app_sources, "assets": sorted(assets),
        "strings": ui_strings(raw_strings),
        "code_strings": ui_strings(code_strings),
    }


def feature_tree(sources: list[str], framework: str) -> list[str]:
    """Group source files by directory; mark UI files."""
    groups: dict[str, list[str]] = defaultdict(list)
    for source in sources:
        if framework == "flutter":
            parts = source.split("/")[1:]
            if any(p in ("l10n", "generated", "gen") for p in parts):
                continue
            directory, stem = "/".join(parts[:-1]) or ".", parts[-1].removesuffix(".dart")
            if GENERATED.search(stem):
                continue
        else:
            directory, _, stem = source.rpartition(".")
        groups[directory].append(stem)
    lines = []
    for directory in sorted(groups):
        stems = sorted(set(groups[directory]))
        marked = [f"**{s}**" if UI_SCREEN.search(s) else s for s in stems]
        lines.append(f"- `{directory}/` ({len(stems)}): {', '.join(marked)}")
    return lines


def write_catalog(data: dict, out: Path) -> None:
    m = data["manifest"]
    english = [s for s in data["strings"] if s.isascii()]
    lines = [
        f"# Catalog draft: {data['package']} {data['version'] or ''}", "",
        "Generated by `inventory.py`. A **draft**: confirm every item by using the original app,",
        "then turn each into a row of the clone's `parity.md`.", "",
        "## App", "",
        f"- Framework: **{data['framework']}** (source package `{data['source_package']}`)",
        *[f"- {kind.title()}: {', '.join(names)}" for kind, names in data["signals"].items() if names],
        *([f"- Firebase project: `{data['firebase'].get('project_id')}`"] if data["firebase"] else []),
        f"- Third-party libraries: {len(data['libraries'])} (see inventory.json)",
        f"- UI strings: {len(data['strings'])} candidates, {len(english)} ASCII (strings.txt)",
        f"- Strings inside code (dex): {len(data['code_strings'])} (strings_code.txt; mostly library messages)", "",
        "## Feature tree (bold = screens, dialogs, sheets, tabs)", "",
        *feature_tree(data["sources"], data["framework"]), "",
        "## Platform surface", "",
        f"- Activities: {', '.join(m.get('activities', [])) or 'n/a'}",
        f"- Deep links: {', '.join(m.get('deep_links', [])) or 'none'}",
        f"- Home-screen widgets: {', '.join(m.get('widgets', [])) or 'none'}",
        f"- Services: {', '.join(m.get('services', [])) or 'none'}",
        f"- Permissions: {', '.join(p.replace('android.permission.', '') for p in m.get('permissions', []))}", "",
    ]
    (out / "catalog.md").write_text("\n".join(lines))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("apks", nargs="+", type=Path, help="base APK first, then its splits")
    parser.add_argument("-o", "--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    data = analyse(args.apks, args.out)
    (args.out / "strings.txt").write_text("\n".join(data["strings"]) + "\n")
    (args.out / "strings_code.txt").write_text("\n".join(data["code_strings"]) + "\n")
    (args.out / "sources.txt").write_text("\n".join(data["sources"]) + "\n")
    (args.out / "inventory.json").write_text(json.dumps({k: v for k, v in data.items() if k not in ("strings", "code_strings")}, indent=1) + "\n")
    write_catalog(data, args.out)
    print(f"{data['framework']}: {len(data['sources'])} sources, {len(data['strings'])} strings, "
          f"storage={data['signals']['storage']}, cloud={data['signals']['cloud']}")
    print(f"→ {args.out / 'catalog.md'}")


if __name__ == "__main__":
    main()
