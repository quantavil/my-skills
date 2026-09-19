"""Unit test for diff_screenshots.py."""
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib

SCRIPT = Path(__file__).with_name('diff_screenshots.py')


def create_test_png(width, height, rgb):
    raw = b''.join(b'\x00' + bytes(rgb) * width for _ in range(height))
    ihdr_data = struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0)
    ihdr = b'\x00\x00\x00\rIHDR' + ihdr_data + struct.pack('>I', zlib.crc32(b'IHDR' + ihdr_data))
    comp = zlib.compress(raw)
    idat = struct.pack('>I', len(comp)) + b'IDAT' + comp + struct.pack('>I', zlib.crc32(b'IDAT' + comp))
    iend = b'\x00\x00\x00\x00IEND\xae\x42\x60\x82'
    return b'\x89PNG\r\n\x1a\n' + ihdr + idat + iend


class DiffScreenshotsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='ditto-diff-test-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

        self.img_red = self.root / 'red.png'
        self.img_red.write_bytes(create_test_png(20, 20, [255, 0, 0]))

        self.img_red_copy = self.root / 'red2.png'
        self.img_red_copy.write_bytes(create_test_png(20, 20, [255, 0, 0]))

        self.img_blue = self.root / 'blue.png'
        self.img_blue.write_bytes(create_test_png(20, 20, [0, 0, 255]))

    def test_identical_images_pass(self):
        out_dir = self.root / 'out1'
        res = subprocess.run([sys.executable, str(SCRIPT), str(self.img_red), str(self.img_red_copy),
                              '--output-dir', str(out_dir)],
                             capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("Visual parity comparison: PASS", res.stdout)
        self.assertTrue((out_dir / 'result.json').is_file())

    def test_different_images_fail(self):
        out_dir = self.root / 'out2'
        res = subprocess.run([sys.executable, str(SCRIPT), str(self.img_red), str(self.img_blue),
                              '--output-dir', str(out_dir)],
                             capture_output=True, text=True)
        self.assertEqual(res.returncode, 1)
        self.assertIn("Visual parity comparison: FAIL", res.stdout)
        self.assertTrue((out_dir / 'result.json').is_file())


if __name__ == '__main__':
    unittest.main()
