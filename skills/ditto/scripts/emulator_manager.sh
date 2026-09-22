#!/usr/bin/env bash
# Compatibility entry point. Windows callers use emulator_manager.py directly.
set -euo pipefail
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
if command -v python3 >/dev/null 2>&1; then
  exec python3 "$script_dir/emulator_manager.py" "$@"
elif command -v python >/dev/null 2>&1; then
  exec python "$script_dir/emulator_manager.py" "$@"
else
  echo "Python 3 is required; install it and run emulator_manager.py." >&2
  exit 2
fi
