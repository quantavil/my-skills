"""Hermetic launcher regression tests: no real emulator or ADB is invoked."""
import json
import os
import shutil
from pathlib import Path
import subprocess
import tempfile
import unittest


SCRIPT = Path(__file__).with_name("emulator_manager.sh")


@unittest.skipIf(os.name == "nt" or not shutil.which("bash"), "Bash compatibility tests require POSIX and Bash")
class EmulatorRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.env = os.environ.copy()
        for key in tuple(self.env):
            if key.startswith("DITTO_"):
                del self.env[key]
        self.env.update(
            PATH=f"{self.bin}:{self.env['PATH']}",
            TEST_ROOT=str(self.root),
            TEST_STATE="",
            TEST_IDENTITY="test-avd",
            DITTO_AVD="test-avd",
            DITTO_ADB=str(self.bin / "adb"),
            DITTO_EMULATOR=str(self.bin / "emulator"),
            DITTO_EMULATOR_LOG=str(self.root / "emulator.log"),
            DITTO_BOOT_TIMEOUT="5",
        )
        self.executable("adb", """#!/usr/bin/env python3
import os, sys, pathlib, time
args = sys.argv[1:]
root = pathlib.Path(os.environ['TEST_ROOT'])
with (root / 'adb.calls').open('a') as out:
    out.write(' '.join(args) + '\\n')
if args == ['devices']:
    if os.environ.get('TEST_ADB_FAIL'):
        sys.exit(1)
    print('List of devices attached')
    if os.environ['TEST_STATE']:
        print('emulator-5554\\t' + os.environ['TEST_STATE'])
elif args[2:] == ['emu', 'avd', 'name']:
    print(os.environ['TEST_IDENTITY'])
elif args[2:] == ['shell', 'getprop', 'sys.boot_completed']:
    # Synchronize with the background mock launcher before the temp dir closes.
    if not os.environ['TEST_STATE']:
        end = time.monotonic() + 3
        while not (root / 'launch.json').exists() and time.monotonic() < end:
            time.sleep(0.01)
    print('1')
""")
        self.executable("emulator", """#!/usr/bin/env python3
import json, os, pathlib, sys
if sys.argv[1:] == ['-list-avds']:
    print('test-avd')
else:
    pathlib.Path(os.environ['TEST_ROOT'], 'launch.json').write_text(json.dumps(sys.argv[1:]))
""")

    def executable(self, name, contents):
        path = self.bin / name
        path.write_text(contents)
        path.chmod(0o755)

    def run_launcher(self, command="start", **env):
        return subprocess.run(
            ["bash", str(SCRIPT), command], env={**self.env, **env},
            text=True, capture_output=True, timeout=10,
        )

    def test_auto_default_for_windowed_and_headless(self):
        for command in ("start", "start-headless"):
            with self.subTest(command=command):
                launch = self.root / "launch.json"
                launch.unlink(missing_ok=True)
                result = self.run_launcher(command)
                self.assertEqual(result.returncode, 0, result.stderr)
                args = json.loads(launch.read_text())
                self.assertEqual(args[args.index("-gpu") + 1], "auto")
                self.assertEqual("-no-window" in args, command == "start-headless")
                calls = (self.root / "adb.calls").read_text()
                self.assertLess(calls.rfind("getprop sys.boot_completed"), calls.rfind("emu avd name"))

    def test_explicit_gpu_override_is_preserved(self):
        result = self.run_launcher("start-headless", DITTO_GPU="host")
        self.assertEqual(result.returncode, 0, result.stderr)
        args = json.loads((self.root / "launch.json").read_text())
        self.assertEqual(args[args.index("-gpu") + 1], "host")

    def test_nonready_serial_never_launches_another_emulator(self):
        for state in ("offline", "unauthorized"):
            with self.subTest(state=state):
                result = self.run_launcher(TEST_STATE=state)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(state, result.stderr)
                self.assertFalse((self.root / "launch.json").exists())

    def test_adb_failure_does_not_look_like_absent_device(self):
        result = self.run_launcher(TEST_ADB_FAIL="1")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.root / "launch.json").exists())

    def test_booted_wrong_avd_is_not_reported_ready(self):
        result = self.run_launcher(TEST_IDENTITY="other-avd")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("expected 'test-avd'", result.stderr)
        self.assertNotIn("Ready:", result.stdout)

    def test_existing_matching_avd_is_reused(self):
        result = self.run_launcher(TEST_STATE="device")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Reusing", result.stdout)
        self.assertFalse((self.root / "launch.json").exists())


if __name__ == "__main__":
    unittest.main()
