#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 || $# -gt 4 || "$1" == "--help" ]]; then
  echo "Usage: $0 PLAY_URL_OR_PACKAGE [OUTPUT_DIR] [PLAY_DEVICE_SERIAL] [EXPECTED_ABI]" >&2
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
serial=${3:-emulator-5556}
expected_abi=${4:-x86_64}
if [[ $expected_abi != x86_64 && $expected_abi != arm64-v8a ]]; then
  echo "EXPECTED_ABI must be x86_64 or arm64-v8a" >&2
  exit 2
fi
if [[ -n ${DITTO2_ADB_BIN:-} ]]; then
  adb_bin=$DITTO2_ADB_BIN
elif command -v adb >/dev/null 2>&1; then
  adb_bin=$(command -v adb)
elif [[ -x ${ANDROID_HOME:-$HOME/Android/Sdk}/platform-tools/adb ]]; then
  adb_bin=${ANDROID_HOME:-$HOME/Android/Sdk}/platform-tools/adb
else
  echo "adb not found; install Android platform-tools" >&2
  exit 1
fi

if [[ $("$adb_bin" -s "$serial" get-state 2>/dev/null) != device ]]; then
  echo "Play emulator $serial is not online" >&2
  exit 1
fi
abi=$("$adb_bin" -s "$serial" shell getprop ro.product.cpu.abi | tr -d '\r')
if [[ $abi != "$expected_abi" ]]; then
  echo "Expected a $expected_abi Play device; $serial reports $abi" >&2
  exit 1
fi
play_path=$("$adb_bin" -s "$serial" shell pm path com.android.vending)
if [[ $play_path != package:* ]]; then
  echo "$serial has no Google Play Store" >&2
  exit 1
fi

diagnostic_file=$(mktemp)
trap 'rm -f -- "$diagnostic_file"' EXIT
if raw_paths=$("$adb_bin" -s "$serial" shell pm path "$package" 2>"$diagnostic_file"); then
  paths=$(tr -d '\r' <<< "$raw_paths")
else
  status=$?
  if [[ $status != 1 || -n $raw_paths || -s $diagnostic_file ]]; then
    [[ -z $raw_paths ]] || printf '%s\n' "$raw_paths" >&2
    cat "$diagnostic_file" >&2
    echo "pm path failed for $package (exit $status)" >&2
    exit 1
  fi
  paths=""
fi
if [[ -z $paths ]]; then
  "$adb_bin" -s "$serial" shell am start -a android.intent.action.VIEW \
    -d "market://details?id=$package" com.android.vending >/dev/null
  echo "Install $package from the opened Play Store listing, then rerun this command" >&2
  exit 1
fi
package_details=$("$adb_bin" -s "$serial" shell dumpsys package "$package")
if [[ $package_details != *installerPackageName=com.android.vending* ]]; then
  echo "$package was not installed by Google Play; install it from Play first" >&2
  exit 1
fi

mkdir -p "$output_dir"
if [[ -e $output_dir/acquisition.json ]] || find "$output_dir" -maxdepth 1 -type f -name '*.apk' -print -quit | grep -q .; then
  echo "Output already contains APKs; use a fresh directory for this Play delivery" >&2
  exit 1
fi
stage_dir=$(mktemp -d "$output_dir/.download.XXXXXX")
trap 'rm -r -- "$stage_dir"; rm -f -- "$diagnostic_file"' EXIT

while IFS= read -r line; do
  if [[ $line != package:* ]]; then
    echo "Unexpected package path: $line" >&2
    exit 1
  fi
  apk_path=${line#package:}
  "$adb_bin" -s "$serial" pull "$apk_path" "$stage_dir/$(basename "$apk_path")"
done <<< "$paths"

python3 - "$stage_dir" "$expected_abi" "$abi" "$package" "$paths" <<'PY'
import hashlib
import json
import sys
from pathlib import Path
from zipfile import ZipFile

directory = Path(sys.argv[1])
apks = sorted(directory.glob("*.apk"))
if not any(apk.name == "base.apk" for apk in apks):
    sys.exit("Play delivery did not contain base.apk")

expected = sys.argv[2]
native_abis = set()
artifacts = []
for apk in apks:
    abi_names = {'arm64_v8a': 'arm64-v8a', 'armeabi_v7a': 'armeabi-v7a', 'x86_64': 'x86_64', 'x86.apk': 'x86'}
    if apk.name != 'base.apk' and any(marker in apk.name and abi != expected for marker, abi in abi_names.items()):
        sys.exit(f"Incompatible ABI split delivered: {apk.name}")
    with ZipFile(apk) as archive:
        damaged = archive.testzip()
        if damaged:
            sys.exit(f"Corrupt APK {apk.name}: {damaged}")
        native_abis.update(
            name.split("/", 2)[1]
            for name in archive.namelist()
            if name.startswith("lib/") and name.endswith(".so")
        )
    with apk.open("rb") as source:
        digest = hashlib.file_digest(source, "sha256").hexdigest()
    print(f"{digest}  {apk.name}")
    artifacts.append({"filename": apk.name, "sha256": digest})

if native_abis and expected not in native_abis:
    sys.exit(f"Input has no {expected} native libraries: {sorted(native_abis)}")
(directory / 'acquisition.json').write_text(json.dumps({
    'schema_version': 1, 'package': sys.argv[4], 'requested_abi': expected,
    'device_abi': sys.argv[3], 'installed_paths': sys.argv[5].splitlines(),
    'reported_installer': 'com.android.vending', 'artifacts': artifacts,
    'native_abis': sorted(native_abis)
}, indent=2) + '\n')
print(f"Native ABIs: {', '.join(sorted(native_abis)) or 'none (universal APK)'}")
PY

mv "$stage_dir"/*.apk "$output_dir"/
mv "$stage_dir/acquisition.json" "$output_dir/"
echo "Saved $expected_abi Play APK set to $output_dir"
