#!/usr/bin/env bash
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Pick up a fresh Bun install that isn't on PATH yet.
[ -x "$HOME/.bun/bin/bun" ] && export PATH="$HOME/.bun/bin:$PATH"

if ! command -v bun >/dev/null 2>&1; then
  echo "my-skills requires Bun (https://bun.sh), which was not found." >&2
  echo "Install it, then re-run:" >&2
  echo "  Arch/CachyOS: sudo pacman -S bun" >&2
  echo "  macOS:        brew install bun" >&2
  echo "  Any OS:       curl -fsSL https://bun.sh/install | bash" >&2
  exit 1
fi

exec bun "$SCRIPT_DIR/index.ts" "$@"
