# Get APKs from Google Play

The Play Store page is metadata; its URL does not serve an APK. Extract the `id`
query parameter as the Android package name. For a free app, use the bundled
script, which runs pinned `gplaydl` in an isolated `uvx` environment. It obtains
the APKs from Google Play delivery via Aurora's anonymous token service and
keeps the base and all config splits. Anonymous delivery can stop working, and
availability depends on region, device profile, and account entitlements.

```bash
skills/ditto2/scripts/download-play-apks.sh \
  'https://play.google.com/store/apps/details?id=com.example.app&hl=en_IN' \
  ./apks/com.example.app
```

Use the package ID instead of the URL when convenient. The script validates the
package name and each APK archive, then prints SHA-256 hashes. It needs `uv`,
Python 3, and network access. Do not use `--no-splits`: Play often puts native
libraries in an ABI split, so the base alone can neither install nor supply
Ditto2's Flutter AOT input. Install a set with `adb install-multiple` and all of
that version's APKs. Keep sets from different versions in separate directories.

If anonymous delivery is unavailable, install the app from the official Play
Store on a connected, compatible Android device under an account entitled to
it. Then pull **every** path listed by the package manager:

```bash
package=com.example.app
serial=YOUR_ADB_SERIAL
mkdir -p "./apks/$package"
adb -s "$serial" shell pm path "$package" |
  tr -d '\r' |
  while IFS= read -r line; do
    apk_path=${line#package:}
    adb -s "$serial" pull "$apk_path" "./apks/$package/$(basename "$apk_path")"
  done
```

For Ditto2, inspect all APKs for `lib/arm64-v8a/libapp.so`. Current
`analyze_apk` and `explore_apk` take a single APK path, so a Play split set is
not directly accepted as complete input. Preserve the original signed splits.
If a merged APK is needed, use an APK split merger, verify the merged package,
version, ARM64 Flutter library, and installability, and record that it was
modified and re-signed. Do not treat a base-only APK as a complete Play build.
