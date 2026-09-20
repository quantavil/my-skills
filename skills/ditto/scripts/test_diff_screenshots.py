"""Unit test for diff_screenshots.py."""
import json
import importlib.util
from unittest.mock import patch
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


spec = importlib.util.spec_from_file_location('diff_tool', SCRIPT)
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)


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

    def test_small_difference_within_allowance_passes(self):
        # pixelmatch returns 66 for any difference, even below our allowance.
        changed = self.root / 'one.png'
        subprocess.run(['magick', str(self.img_red), '-fill', 'blue',
                        '-draw', 'point 10,10', str(changed)], check=True)
        passed, result = tool.diff_screenshots(self.img_red, changed, self.root / 'small',
                                               max_diff_ratio=0.01)
        self.assertTrue(passed)
        self.assertEqual(result['changed_pixels'], 1)
        self.assertEqual(result['compared_pixels'], 400)

    def test_mask_excludes_pixels_from_denominator(self):
        passed, result = tool.diff_screenshots(self.img_red, self.img_blue, self.root / 'mask',
                                               mask_system_bars=True, top_mask=5, bottom_mask=5)
        self.assertFalse(passed)
        self.assertEqual(result['compared_pixels'], 200)
        self.assertEqual(result['changed_pixels'], 200)
        self.assertEqual(result['changed_ratio'], 1.0)

    def test_unknown_output_cannot_pass(self):
        fake = subprocess.CompletedProcess([], 0, stdout='done', stderr='')
        with patch.object(tool.subprocess, 'run', return_value=fake):
            with self.assertRaisesRegex(RuntimeError, 'metric'):
                tool.diff_screenshots(self.img_red, self.img_red_copy, self.root / 'unknown')

    def test_mask_failure_is_explicit(self):
        with patch.object(tool.shutil, 'which', return_value=None):
            with self.assertRaises(RuntimeError):
                tool.apply_system_bar_mask(self.img_red, self.root / 'masked.png')

    def test_empty_mask_area_rejected(self):
        with self.assertRaises(ValueError):
            tool.diff_screenshots(self.img_red, self.img_blue, self.root / 'empty',
                                  mask_system_bars=True, top_mask=10, bottom_mask=10)

    def test_mismatched_dimensions_rejected(self):
        other = self.root / 'other.png'
        other.write_bytes(create_test_png(21, 20, [255, 0, 0]))
        with self.assertRaises(ValueError):
            tool.diff_screenshots(self.img_red, other, self.root / 'dimensions')

    def test_invalid_rerun_removes_previous_success(self):
        out = self.root / 'rerun'
        tool.diff_screenshots(self.img_red, self.img_red_copy, out)
        self.img_red_copy.unlink()
        with self.assertRaises(FileNotFoundError):
            tool.diff_screenshots(self.img_red, self.img_red_copy, out)
        self.assertFalse((out / 'result.json').exists())

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

    def test_composite_montage_generated_when_magick_available(self):
        out_dir = self.root / 'out_composite'
        res = subprocess.run([sys.executable, str(SCRIPT), str(self.img_red), str(self.img_blue),
                              '--output-dir', str(out_dir)],
                             capture_output=True, text=True)
        data = json.loads((out_dir / 'result.json').read_text(encoding='utf-8'))
        # If ImageMagick is present, composite_image is created
        if data.get('composite_image'):
            self.assertTrue(Path(data['composite_image']).is_file())

    def test_xml_hierarchy_bounding_box_comparison(self):
        xml_o = self.root / 'oracle.xml'
        xml_c = self.root / 'cand.xml'
        xml_o.write_text(
            '<hierarchy><node text="Title" bounds="[10,20][100,60]" class="android.widget.TextView"/></hierarchy>',
            encoding='utf-8'
        )
        xml_c.write_text(
            '<hierarchy><node text="Title" bounds="[10,28][100,68]" class="android.widget.TextView"/></hierarchy>',
            encoding='utf-8'
        )

        out_dir = self.root / 'out_xml'
        res = subprocess.run([
            sys.executable, str(SCRIPT), str(self.img_red), str(self.img_red_copy),
            '--output-dir', str(out_dir),
            '--xml-original', str(xml_o),
            '--xml-candidate', str(xml_c)
        ], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, res.stderr)
        data = json.loads((out_dir / 'result.json').read_text(encoding='utf-8'))
        self.assertEqual(data['layout_deltas_count'], 1)
        delta = data['layout_deltas'][0]
        self.assertEqual(delta['identifier'], 'Title')
        self.assertEqual(delta['delta_y'], 8)
        self.assertEqual(delta['delta_x'], 0)


if __name__ == '__main__':
    unittest.main()
