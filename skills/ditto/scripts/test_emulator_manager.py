"""Check emulator selection without starting or stopping real devices."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).with_name('emulator_manager.sh')


class EmulatorManagerTests(unittest.TestCase):
    def test_wrong_avd_cannot_be_stopped(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            adb = root / 'adb'
            marker = root / 'killed'
            adb.write_text('#!/bin/sh\ncase "$*" in\n*"avd name"*) echo another_avd;;\n*kill*) touch "$KILL_MARKER";;\nesac\n')
            adb.chmod(0o755)
            result = subprocess.run(['bash', str(SCRIPT), 'stop'], capture_output=True,
                                    text=True, env={**os.environ, 'DITTO_ADB': str(adb),
                                                   'DITTO_AVD': 'expected_avd',
                                                   'KILL_MARKER': str(marker)})
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('Refusing to stop', result.stderr)
            self.assertFalse(marker.exists())

    def test_existing_matching_avd_is_reused(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            adb = root / 'adb'
            emulator = root / 'emulator'
            marker = root / 'launched'
            adb.write_text('#!/bin/sh\ncase "$*" in\ndevices) printf "List of devices attached\\nemulator-5554\\tdevice\\n";;\n*"avd name"*) echo expected_avd;;\n*sys.boot_completed*) echo 1;;\nesac\n')
            emulator.write_text('#!/bin/sh\ntouch "$LAUNCH_MARKER"\n')
            adb.chmod(0o755)
            emulator.chmod(0o755)
            result = subprocess.run(['bash', str(SCRIPT), 'start-headless'], capture_output=True,
                                    text=True, env={**os.environ, 'DITTO_ADB': str(adb),
                                                   'DITTO_EMULATOR': str(emulator),
                                                   'DITTO_AVD': 'expected_avd',
                                                   'DITTO_EMULATOR_PORT': '5554',
                                                   'LAUNCH_MARKER': str(marker)})
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('Reusing emulator-5554', result.stdout)
            self.assertFalse(marker.exists())


if __name__ == '__main__':
    unittest.main()
