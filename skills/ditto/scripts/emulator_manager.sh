#!/usr/bin/env bash
# Reuse one explicitly selected Android emulator. App data is never reset here.
#
#   start | start-headless | stop | status | install <apk> [package] [--grant-permissions] | check
#
# Env: DITTO_AVD (required for start/stop), DITTO_EMULATOR_PORT, DITTO_BOOT_TIMEOUT,
#      DITTO_GPU, DITTO_ADB, DITTO_EMULATOR, DITTO_EMULATOR_LOG
set -euo pipefail

sdk_root="${ANDROID_HOME:-${ANDROID_SDK_ROOT:-$HOME/Android/Sdk}}"
adb_bin="${DITTO_ADB:-$sdk_root/platform-tools/adb}"
emulator_bin="${DITTO_EMULATOR:-$sdk_root/emulator/emulator}"
avd_name="${DITTO_AVD:-}"
port="${DITTO_EMULATOR_PORT:-5554}"
serial="emulator-$port"
boot_timeout="${DITTO_BOOT_TIMEOUT:-300}"
log_path="${DITTO_EMULATOR_LOG:-${TMPDIR:-/tmp}/ditto-emulator-$port.log}"

die() { echo "$*" >&2; exit "${2:-2}"; }

[[ "$port" =~ ^[0-9]+$ ]] || die "Invalid DITTO_EMULATOR_PORT: $port"
[[ "$boot_timeout" =~ ^[1-9][0-9]*$ ]] || die "Invalid DITTO_BOOT_TIMEOUT: $boot_timeout"
[[ -x "$adb_bin" ]] || die "ADB missing or not executable: $adb_bin"

require_avd() {
  if [[ -z "$avd_name" ]]; then
    echo "Set DITTO_AVD. Available AVDs:" >&2
    [[ -x "$emulator_bin" ]] && "$emulator_bin" -list-avds >&2 || echo "  (emulator binary not found)" >&2
    exit 2
  fi
}

# Confirm the serial really is the AVD we were told to use before touching it.
assert_identity() {
  local actual
  actual=$(timeout 10 "$adb_bin" -s "$serial" emu avd name 2>/dev/null | head -n 1 | tr -d '\r' || true)
  [[ "$actual" == "$avd_name" ]] || die "$serial is running '$actual', expected '$avd_name'" 1
}

attached() {
  "$adb_bin" devices | awk 'NR>1 && $2=="device" {print $1}' | grep -Fxq "$serial"
}

wait_for_boot() {
  local deadline=$((SECONDS + boot_timeout)) state=''
  until [[ "$state" == 1 ]]; do
    (( SECONDS < deadline )) || die "Boot timed out after ${boot_timeout}s; inspect $log_path" 1
    sleep 2
    state=$(timeout 5 "$adb_bin" -s "$serial" shell getprop sys.boot_completed 2>/dev/null | tr -d '\r' || true)
  done
  # boot_completed fires before the launcher is interactive; settle before capturing.
  timeout 60 "$adb_bin" -s "$serial" wait-for-device shell 'while [ "$(getprop init.svc.bootanim)" != stopped ]; do sleep 1; done' >/dev/null 2>&1 || true
}

case "${1:-status}" in
  start|start-headless)
    require_avd
    [[ -x "$emulator_bin" ]] || die "Emulator binary missing: $emulator_bin"
    if attached; then
      assert_identity
      echo "Reusing $serial ($avd_name)"
    else
      "$emulator_bin" -list-avds | grep -Fxq "$avd_name" || die "AVD not found: $avd_name"
      # -gpu host needs a real display. Headless runs must not inherit it.
      if [[ "$1" == start-headless ]]; then
        gpu="${DITTO_GPU:-swiftshader_indirect}"
      else
        gpu="${DITTO_GPU:-host}"
      fi
      args=(-avd "$avd_name" -port "$port" -gpu "$gpu")
      [[ -r /dev/kvm && -w /dev/kvm ]] && args+=(-accel on) || {
        echo "No writable /dev/kvm; falling back to software acceleration (slow)." >&2
        args+=(-accel off)
      }
      [[ "$1" != start-headless ]] || args+=(-no-window -no-audio -no-boot-anim)
      nohup setsid "$emulator_bin" "${args[@]}" >"$log_path" 2>&1 </dev/null &
      echo "Starting $serial ($avd_name, gpu=$gpu); log: $log_path"
    fi
    wait_for_boot
    echo "Ready: $serial"
    "$adb_bin" -s "$serial" shell wm size | tr -d '\r'
    "$adb_bin" -s "$serial" shell wm density | tr -d '\r'
    ;;

  stop)
    require_avd
    assert_identity
    "$adb_bin" -s "$serial" emu kill
    echo "Stopped $serial ($avd_name)"
    ;;

  install)
    require_avd
    apk="${2:-}"
    [[ -f "$apk" ]] || die "Usage: $0 install <apk> [package]"
    attached || die "$serial is not attached" 1
    assert_identity
    # -r keeps existing data; original and candidate must keep distinct package ids.
    install_args=(-r)
    package=''
    for option in "${@:3}"; do
      if [[ "$option" == --grant-permissions ]]; then
        install_args+=(-g)
      elif [[ "$option" =~ ^[A-Za-z0-9_]+(\.[A-Za-z0-9_]+)+$ && -z "$package" ]]; then
        package="$option"
      else
        die "Unknown install argument: $option"
      fi
    done
    "$adb_bin" -s "$serial" install "${install_args[@]}" "$apk"
    if [[ -n "$package" ]]; then
      "$adb_bin" -s "$serial" shell pm path "$package" | tr -d '\r'
    fi
    ;;

  check)
    echo "adb:      $adb_bin"
    echo "emulator: $emulator_bin"
    echo "avd:      ${avd_name:-<unset: set DITTO_AVD>}"
    echo -n "kvm:      "; [[ -r /dev/kvm && -w /dev/kvm ]] && echo "available" || echo "unavailable (emulation will be slow)"
    echo "attached:"; "$adb_bin" devices -l
    ;;

  status)
    "$adb_bin" devices -l
    ;;

  *)
    die "Usage: $0 {start|start-headless|stop|status|check|install <apk> [package]}"
    ;;
esac
