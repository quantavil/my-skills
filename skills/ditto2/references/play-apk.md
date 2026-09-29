# Get x86_64 APKs from Google Play

The Play Store page is metadata; its URL does not serve an APK. Use the signed-in
`ditto2_play_x86_64` Google Play emulator. Install the app there through the
Play Store, then pull the exact base and config splits that Play delivered:

```bash
skills/ditto2/scripts/download-play-apks.sh \
  'https://play.google.com/store/apps/details?id=com.example.app&hl=en_IN' \
  ./apks/com.example.app-x86_64 \
  emulator-5556
```

The package ID may replace the URL. If the app is not installed, the script
opens its Play listing and exits; install it there and rerun the command. The
third argument is the ADB serial and defaults to `emulator-5556`. The script
requires Python 3 and `adb`, checks that the device's primary ABI is x86_64 and
that Google Play installed the app, pulls every installed split, rejects ARM
and 32-bit x86 native APKs, checks ZIP integrity, and prints SHA-256 hashes.
Use a fresh output directory for each version. A universal app may have only a
base APK; a Flutter app normally has `split_config.x86_64.apk` with
`lib/x86_64/libapp.so` and `lib/x86_64/libflutter.so`.

This acquisition path deliberately collects **only x86_64-compatible APKs**.
Do not use anonymous `gplaydl` for this path: its older ARM device profile
returned `config.arm64_v8a` even when asked for x86_64. Google Play chooses
the app version and splits for the emulator. Record the version and keep
different versions separate. Install a saved split set with
`adb install-multiple` and all APKs from that set.

The current Ditto2 `analyze_apk` r2Flutter stage requires an ARM64
`libapp.so`, so an x86_64-only download cannot complete static Flutter AOT
analysis. Mark that phase incompatible; do not silently fetch ARM64 or claim a
complete Ditto2 evidence set. Current `analyze_apk` and `explore_apk` also
accept one APK path rather than an installed split set, so keep all original
signed APKs and report that integration gap before invoking those tools.
