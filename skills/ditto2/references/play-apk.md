# Acquire complete ARM64 and x86_64 inputs

Google Play URLs identify listings, not downloadable APK files. Install through Play on a compatible signed-in device, then pull the exact installed delivery:

```bash
skills/ditto2/scripts/download-play-apks.sh \
  'https://play.google.com/store/apps/details?id=com.example.app' \
  ./apks/example-x86_64 emulator-5556 x86_64

skills/ditto2/scripts/download-play-apks.sh \
  com.example.app ./apks/example-arm64 ARM64_DEVICE_SERIAL arm64-v8a
```

Arguments are URL/package, fresh output directory, explicit ADB serial, and expected primary ABI. Existing three-argument calls default to x86_64. An ARM64 pull needs a compatible ARM64 Play device; the x86_64 emulator does not automatically provide its other ABI delivery. A supplied original ARM64 APK/set is also supported. Do not fetch an unrelated release or use the old anonymous downloader as an automatic fallback.

If absent, the script opens the listing and exits; install through Play and rerun. It checks device state/ABI and reported installer metadata, pulls every installed APK, checks ZIP/native compatibility, and writes SHA-256 hashes plus acquisition.json. Installer metadata is recorded, not proof of a Play Integrity verdict. Native libraries for both ABIs are allowed in a complete universal base. Transport failures are reported separately from an absent app. Existing output APKs/metadata are never overwritten.

Retain the original signed base and required language/density/feature/ABI splits. A config split alone is incomplete. Do not merge/re-sign a delivery simply to obtain one file. Keep releases/ABIs in separate directories.

MCP examples for supplied split deliveries:

```text
analyze_apk(apk_path="/apks/arm64/base.apk",
            split_paths=["/apks/arm64/split_config.arm64_v8a.apk", ...],
            output_dir="/evidence/analysis")
explore_apk(apk_path="/apks/x86/base.apk",
            split_paths=["/apks/x86/split_config.x86_64.apk", ...],
            output_dir="/evidence/exploration", device_serial="emulator-5556",
            install_mode="reuse", script_path="/scripts/onboarding.json")
```

Replace the illustrated lists with every selected required split; for standalone APKs omit split_paths. The MCP validates manifest/signatures and hashes; matching version names alone are insufficient. Reuse first verifies the installed delivery's bytes. Install mode uses adb install/install-multiple without promising an installer flag fixes licensing or integrity.

Static and runtime bases can differ. Unification links matching package/version/signers, compares common DEX/assets, and records resource/ABI coverage limits in inputs.json and review.json. Preserve source APK files so their hashes can be checked again. Missing ARM64 permits finalized partial Android analysis, with r2Flutter explicitly unsupported.
