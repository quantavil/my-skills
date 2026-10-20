"""Small adb helpers shared by the Ditto scripts. Stdlib only."""

from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import time
from pathlib import Path


def adb_bin() -> str:
    if os.environ.get("DITTO_ADB_BIN"):
        return os.environ["DITTO_ADB_BIN"]
    found = shutil.which("adb")
    if found:
        return found
    sdk = Path(os.environ.get("ANDROID_HOME", Path.home() / "Android/Sdk"))
    candidate = sdk / "platform-tools/adb"
    if candidate.exists():
        return str(candidate)
    raise SystemExit("adb not found; install Android platform-tools")


class Adb:
    def __init__(self, serial: str):
        self.serial = serial
        self.bin = adb_bin()
        self.via_su: bool | None = None  # None until ensure_root() decides

    def run(self, *args: str, check: bool = True, binary: bool = False, timeout: int = 120):
        result = subprocess.run(
            [self.bin, "-s", self.serial, *args],
            capture_output=True,
            timeout=timeout,
        )
        if check and result.returncode != 0:
            raise RuntimeError(
                f"adb {' '.join(args)} failed ({result.returncode}): "
                f"{result.stderr.decode(errors='replace').strip()}"
            )
        return result.stdout if binary else result.stdout.decode(errors="replace")

    def shell(self, command: str, check: bool = True) -> str:
        return self.run("shell", command, check=check).replace("\r\n", "\n")

    def ensure_root(self) -> None:
        """Get root: adbd root (google_apis images) or Magisk su (rooted Play images)."""
        if self.via_su is not None:
            return
        if self.shell("id -u").strip() == "0":
            self.via_su = False
            return
        if self.shell("su -c 'id -u'", check=False).strip() == "0":
            self.via_su = True
            return
        if "production" not in self.run("root", check=False):
            time.sleep(1)
            self.run("wait-for-device", timeout=60)
            if self.shell("id -u").strip() == "0":
                self.via_su = False
                return
        raise SystemExit(
            f"{self.serial} has no root. Root the Play emulator with Magisk and allow "
            "Shell in Magisk > Superuser; see SKILL.md > Setup."
        )

    def root_command(self, command: str) -> str:
        """`command` wrapped so it runs as root on this device."""
        self.ensure_root()
        return f"su -c {shlex.quote(command)}" if self.via_su else command

    def root_shell(self, command: str, check: bool = True) -> str:
        return self.shell(self.root_command(command), check=check)

    def app_uid(self, package: str) -> str:
        uid = self.root_shell(f"stat -c %u /data/data/{package}", check=False).strip()
        if not uid.isdigit():
            raise SystemExit(f"{package} is not installed on {self.serial}")
        return uid
