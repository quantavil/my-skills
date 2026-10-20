#!/usr/bin/env bash
# Create an ARM64 Google Play emulator, only to fetch an app's ARM64 delivery
# (Blutter needs an ARM64 libapp.so). Downloads a ~1.5 GB system image; runs slowly on x86 hosts.
# Not needed for catalog, data model or experiments: those use the x86_64 Play emulator, whose
# libapp.so already gives the full catalog. Run this only when Blutter is the last resort.
set -euo pipefail
image="system-images;android-34;google_apis_playstore;arm64-v8a"
sdkmanager "$image"
avdmanager create avd -n ditto_arm64_play -k "$image" -d pixel_6 --force
cat <<'MSG'
Created ditto_arm64_play. Then:
  emulator -avd ditto_arm64_play -port 5558 -timezone Asia/Kolkata -no-snapshot-load &
  (sign in to Play, install the app from its listing)
  scripts/download-play-apks.sh PKG apk-arm64 emulator-5558 arm64-v8a
Delete the AVD afterwards: avdmanager delete avd -n ditto_arm64_play
MSG
