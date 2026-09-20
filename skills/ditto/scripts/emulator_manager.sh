#!/usr/bin/env bash
# Reuse one explicitly selected Android emulator. No app data is reset.
set -euo pipefail
sdk_root="${ANDROID_HOME:-${ANDROID_SDK_ROOT:-$HOME/Android/Sdk}}"
adb_bin="${DITTO_ADB:-$sdk_root/platform-tools/adb}"
emulator_bin="${DITTO_EMULATOR:-$sdk_root/emulator/emulator}"
avd_name="${DITTO_AVD:-floww_parity}"
port="${DITTO_EMULATOR_PORT:-5554}"
serial="emulator-$port"
boot_timeout="${DITTO_BOOT_TIMEOUT:-180}"
log_path="${DITTO_EMULATOR_LOG:-${TMPDIR:-/tmp}/ditto-emulator-$port.log}"
[[ "$port" =~ ^[0-9]+$ && "$boot_timeout" =~ ^[1-9][0-9]*$ ]] || { echo 'Invalid port or timeout' >&2; exit 2; }
[[ -x "$adb_bin" ]] || { echo "ADB missing: $adb_bin" >&2; exit 2; }
case "${1:-status}" in
  start|start-headless)
    [[ -x "$emulator_bin" ]] || { echo "Emulator missing: $emulator_bin" >&2; exit 2; }
    if "$adb_bin" devices | awk 'NR>1 {print $1}' | grep -Fxq "$serial"; then
      actual_avd=$(timeout 10 "$adb_bin" -s "$serial" emu avd name | head -n 1 | tr -d '\r')
      [[ "$actual_avd" == "$avd_name" ]] || { echo "$serial belongs to $actual_avd, expected $avd_name" >&2; exit 1; }
      echo "Reusing $serial ($avd_name)"
    else
      "$emulator_bin" -list-avds | grep -Fxq "$avd_name" || { echo "AVD missing: $avd_name" >&2; exit 2; }
      args=(-avd "$avd_name" -port "$port" -gpu host -accel on)
      [[ "$1" != start-headless ]] || args+=(-no-window -no-audio)
      nohup setsid "$emulator_bin" "${args[@]}" >"$log_path" 2>&1 </dev/null &
      echo "Starting $serial ($avd_name); log: $log_path"
    fi
    deadline=$((SECONDS + boot_timeout))
    until [[ "$(timeout 5 "$adb_bin" -s "$serial" shell getprop sys.boot_completed 2>/dev/null | tr -d '\r' || true)" == 1 ]]; do
      (( SECONDS < deadline )) || { echo "Boot timed out; inspect $log_path" >&2; exit 1; }
      sleep 1
    done
    echo "Ready: $serial"
    ;;
  stop)
    actual_avd=$(timeout 10 "$adb_bin" -s "$serial" emu avd name | head -n 1 | tr -d '\r')
    [[ "$actual_avd" == "$avd_name" ]] || { echo "Refusing to stop $actual_avd; expected $avd_name" >&2; exit 1; }
    "$adb_bin" -s "$serial" emu kill
    ;;
  status)
    "$adb_bin" devices -l
    ;;
  *) echo "Usage: $0 {start|start-headless|stop|status}" >&2; exit 2 ;;
esac
