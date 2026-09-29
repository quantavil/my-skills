#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 || $# -gt 2 || "$1" == "--help" ]]; then
  echo "Usage: $0 PLAY_URL_OR_PACKAGE [OUTPUT_DIR]" >&2
  exit 2
fi

package=$(python3 - "$1" <<'PY'
import re
import sys
from urllib.parse import parse_qs, urlparse

value = sys.argv[1]
if value.startswith("https://"):
    url = urlparse(value)
    if url.hostname != "play.google.com" or url.path != "/store/apps/details":
        sys.exit("Expected a Google Play app details URL")
    value = parse_qs(url.query).get("id", [""])[0]
if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)+", value):
    sys.exit("Invalid Android package ID")
print(value)
PY
)

output_dir=${2:-"./play-apks/$package"}
mkdir -p "$output_dir"
stage_dir=$(mktemp -d "$output_dir/.download.XXXXXX")
trap 'rm -rf "$stage_dir"' EXIT

# This pinned release supports anonymous Play delivery without a Google account.
# Keep all splits: the base APK often lacks ABI libraries and cannot install alone.
uvx --no-build --from 'gplaydl==2.1.3' gplaydl download "$package" -o "$stage_dir"

python3 - "$package" "$stage_dir" <<'PY'
import hashlib
import sys
from pathlib import Path
from zipfile import ZipFile

package, directory = sys.argv[1], Path(sys.argv[2])
apks = sorted(directory.glob(f"{package}-*.apk"))
if not apks:
    sys.exit("Download returned no APK files")
base = [p for p in apks if "-config." not in p.name and "-asset." not in p.name]
if not base:
    sys.exit("Download returned no base APK")

for apk in apks:
    with ZipFile(apk) as archive:
        damaged = archive.testzip()
        if damaged:
            sys.exit(f"Corrupt APK {apk}: {damaged}")
    with apk.open("rb") as source:
        digest = hashlib.file_digest(source, "sha256").hexdigest()
    print(f"{digest}  {apk.name}")
PY

mv "$stage_dir"/*.apk "$output_dir"/
echo "Saved verified APKs to $output_dir"
