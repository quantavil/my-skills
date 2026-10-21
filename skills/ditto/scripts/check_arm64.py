#!/usr/bin/env python3
"""Verify an ARM64 copy of the app against the Play-installed reference, then record it.

Usage: check_arm64.py REFERENCE_DIR ARM64_DIR [--source phone|apkmirror|apkpure|uptodown|other]

REFERENCE_DIR is the Play delivery from download-play-apks.sh (apk/). ARM64_DIR holds the
ARM64 base.apk and splits, from a phone (`adb pull`) or a mirror (unzip .apkm/.xapk first).
Checks, each of which must pass:
  package and versionCode equal the reference
  signing certificate SHA-256 equals the reference (so the file is the developer's build)
  lib/arm64-v8a/libapp.so is present (Flutter), or lib/arm64-v8a/*.so for other apps
Writes ARM64_DIR/acquisition-arm64.json (sha256 of every file, source, versions).
Exit 1 on any failure. Nothing is installed or executed from the downloaded files.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from zipfile import ZipFile


def tool(name: str) -> str:
    found = shutil.which(name)
    if found:
        return found
    root = Path(os.environ.get("ANDROID_HOME", Path.home() / "Android/Sdk")) / "build-tools"
    for version in sorted(root.glob("*"), reverse=True):
        if (version / name).exists():
            return str(version / name)
    raise SystemExit(f"{name} not found; install Android build-tools")


def parse_badging(text: str) -> dict:
    match = re.search(r"package: name='([^']+)' versionCode='(\d+)' versionName='([^']*)'", text)
    if not match:
        raise ValueError("no package line in aapt2 output")
    return {"package": match.group(1), "versionCode": match.group(2), "versionName": match.group(3)}


def parse_cert(text: str) -> str | None:
    match = re.search(r"certificate SHA-256 digest: ([0-9a-f]{64})", text)
    return match.group(1) if match else None


def apk_info(apk: Path) -> dict:
    badging = subprocess.run([tool("aapt2"), "dump", "badging", str(apk)], capture_output=True, text=True, check=True).stdout
    certs = subprocess.run([tool("apksigner"), "verify", "--print-certs", str(apk)], capture_output=True, text=True)
    return {**parse_badging(badging), "cert": parse_cert(certs.stdout)}


def native_libs(apks: list[Path]) -> set[str]:
    found: set[str] = set()
    for apk in apks:
        with ZipFile(apk) as archive:
            found.update(n for n in archive.namelist() if n.startswith("lib/arm64-v8a/") and n.endswith(".so"))
    return found


def sha256(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def problems(reference: dict, candidate: dict, libs: set[str]) -> list[str]:
    out = []
    for key in ("package", "versionCode"):
        if reference[key] != candidate[key]:
            out.append(f"{key}: Play copy {reference[key]} != ARM64 copy {candidate[key]}")
    if not candidate["cert"] or candidate["cert"] != reference["cert"]:
        out.append(f"signing certificate differs or is unreadable: {reference['cert']} vs {candidate['cert']}")
    if not libs:
        out.append("no lib/arm64-v8a/*.so in any APK (is the split_config.arm64_v8a.apk missing?)")
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("reference", type=Path)
    parser.add_argument("arm64", type=Path)
    parser.add_argument("--source", default="other")
    args = parser.parse_args()

    reference_apk, candidate_apk = args.reference / "base.apk", args.arm64 / "base.apk"
    for apk in (reference_apk, candidate_apk):
        if not apk.exists():
            raise SystemExit(f"missing {apk}")
    apks = sorted(args.arm64.glob("*.apk"))
    reference, candidate, libs = apk_info(reference_apk), apk_info(candidate_apk), native_libs(apks)
    found = problems(reference, candidate, libs)
    framework_hint = "libapp.so" if any(n.endswith("/libapp.so") for n in libs) else "no libapp.so (not Flutter, or missing split)"
    if found:
        print("ARM64 copy REJECTED:\n- " + "\n- ".join(found), file=sys.stderr)
        sys.exit(1)
    record = {"source": args.source, "package": candidate["package"], "versionCode": candidate["versionCode"],
              "versionName": candidate["versionName"], "cert_sha256": candidate["cert"],
              "native_libs": sorted(libs), "files": {apk.name: sha256(apk) for apk in apks}}
    (args.arm64 / "acquisition-arm64.json").write_text(json.dumps(record, indent=1) + "\n")
    print(f"ARM64 copy accepted ({args.source}): {candidate['package']} {candidate['versionName']} "
          f"({candidate['versionCode']}); {len(libs)} native libs; {framework_hint}")


if __name__ == "__main__":
    main()
