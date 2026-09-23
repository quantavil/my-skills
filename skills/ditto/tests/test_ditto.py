"""Hermetic regression tests. No device, SDK, Node, or external image tools required.

See references/commands.md for test invocation.
"""
import json
import os
from pathlib import Path
import random
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

HERE = Path(__file__).resolve().parent.parent / 'scripts'
sys.path.insert(0, str(HERE))

import diff_screenshots as diff  # noqa: E402
import inventory  # noqa: E402
import pngtool  # noqa: E402
import theme_extract  # noqa: E402


def solid(width, height, rgb):
    return bytes(rgb) * (width * height)


class Temp(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='ditto-test-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)


# --------------------------------------------------------------------------

class PngTests(Temp):
    def test_round_trip_is_exact(self):
        random.seed(3)
        width, height = 37, 23
        pixels = bytes(random.randrange(256) for _ in range(width * height * 3))
        path = self.root / 'a.png'
        pngtool.encode(path, width, height, pixels)
        self.assertEqual(pngtool.decode(path), (width, height, pixels))
        self.assertEqual(pngtool.read_header(path), (width, height))

    def test_non_png_is_rejected(self):
        path = self.root / 'fake.png'
        path.write_bytes(b'not a png at all')
        with self.assertRaises(pngtool.PngError):
            pngtool.read_header(path)
        with self.assertRaises(pngtool.PngError):
            pngtool.decode(path)

    def test_transparency_is_composited_on_white(self):
        from PIL import Image
        for mode in ('RGBA', 'P'):
            with self.subTest(mode=mode):
                path = self.root / 'transparent.png'
                image = Image.new('RGBA', (1, 1), (255, 0, 0, 0))
                image.convert(mode).save(path)
                self.assertEqual(pngtool.decode(path), (1, 1, b'\xff\xff\xff'))

    def test_16bit_grey_keeps_high_byte(self):
        import numpy as np
        from PIL import Image
        path = self.root / 'grey.png'
        Image.fromarray(np.array([[0, 32768, 65535]], dtype=np.uint16)).save(path)
        self.assertEqual(pngtool.decode(path)[2], bytes((0, 0, 0, 128, 128, 128, 255, 255, 255)))

    def test_buffer_length_must_match_dimensions(self):
        with self.assertRaises(pngtool.PngError):
            pngtool.encode(self.root / 'b.png', 4, 4, b'\x00' * 10)


# --------------------------------------------------------------------------

class DiffTests(Temp):
    def setUp(self):
        super().setUp()
        self.width, self.height = 40, 60
        self.a = self.root / 'a.png'
        self.b = self.root / 'b.png'
        pngtool.encode(self.a, self.width, self.height, solid(self.width, self.height, (10, 20, 30)))
        pixels = bytearray(solid(self.width, self.height, (10, 20, 30)))
        for y in range(0, 10):            # 10 rows of noise at the top
            for x in range(self.width):
                o = (y * self.width + x) * 3
                pixels[o:o + 3] = b'\xff\xff\xff'
        for y in range(30, 32):           # a real 2x5 defect in the body
            for x in range(5, 10):
                o = (y * self.width + x) * 3
                pixels[o:o + 3] = b'\xff\x00\x00'
        pngtool.encode(self.b, self.width, self.height, bytes(pixels))

    def test_exclusion_leaves_the_denominator(self):
        _, result = diff.diff_screenshots(self.a, self.b, self.root / 'o',
                                          top_mask=10, max_diff_ratio=1.0)
        self.assertEqual(result['changed_pixels'], 10)
        self.assertEqual(result['compared_pixels'], self.width * (self.height - 10))
        self.assertEqual(result['excluded_pixels'], self.width * 10)

    def test_default_triptych_has_labeled_native_resolution_panels(self):
        out = self.root / 'triptych'
        _, result = diff.diff_screenshots(self.a, self.a, out)
        triptych = out / 'triptych.png'
        self.assertTrue(triptych.is_file())
        width, height, pixels = pngtool.decode(triptych)
        self.assertEqual(width, self.width * 3 + diff.PANEL_GAP * 4)
        self.assertEqual(height, diff.HEADER_HEIGHT + self.height + diff.PANEL_GAP)
        _, _, diff_pixels = pngtool.decode(out / 'diff.png')
        panel_x = [diff.PANEL_GAP + index * (self.width + diff.PANEL_GAP)
                   for index in range(3)]
        for x, expected in zip(panel_x, (b'\x0a\x14\x1e', b'\x0a\x14\x1e',
                                         diff_pixels[:3])):
            offset = (diff.HEADER_HEIGHT * width + x) * 3
            self.assertEqual(pixels[offset:offset + 3], expected)
        self.assertEqual(result['triptych_image'], str(triptych.resolve()))
        self.assertEqual(result['visual_metric_status'], 'pass')
        self.assertEqual(result['layout_comparison_status'], 'not_run')
        self.assertEqual(result['layout_reason'], 'paired XML not supplied')

    def test_paired_xml_reports_compared_layout_counts(self):
        original = self.root / 'original.xml'
        clone = self.root / 'clone.xml'
        original.write_text('<hierarchy><node text="Save" bounds="[0,0][10,10]"/>'
                            '</hierarchy>')
        clone.write_text('<hierarchy><node text="Save" bounds="[2,0][12,10]"/>'
                         '</hierarchy>')
        _, result = diff.diff_screenshots(
            self.a, self.a, self.root / 'layout',
            xml_original=original, xml_candidate=clone)
        self.assertEqual(result['layout_comparison_status'], 'compared')
        self.assertEqual(result['layout_delta_count'], 1)
        self.assertEqual(result['only_in_original_count'], 0)
        self.assertEqual(result['only_in_clone_count'], 0)

    def test_threshold_matches_pixelmatch_semantics(self):
        """maxDelta = 35215 * t^2; a uniform +25 step sits just under t=0.1."""
        near = self.root / 'near.png'
        pngtool.encode(near, self.width, self.height, solid(self.width, self.height, (35, 45, 55)))
        _, loose = diff.diff_screenshots(self.a, near, self.root / 'l',
                                         threshold=0.1, max_diff_ratio=1.0)
        _, tight = diff.diff_screenshots(self.a, near, self.root / 't',
                                         threshold=0.05, max_diff_ratio=1.0)
        self.assertEqual(loose['changed_pixels'], 0)
        self.assertEqual(tight['changed_pixels'], self.width * self.height)

    def test_mismatched_dimensions_are_refused(self):
        other = self.root / 'other.png'
        pngtool.encode(other, self.width + 1, self.height, solid(self.width + 1, self.height, (0, 0, 0)))
        with self.assertRaisesRegex(ValueError, 'dimensions differ'):
            diff.diff_screenshots(self.a, other, self.root / 'd')

    def test_full_exclusion_is_refused(self):
        with self.assertRaisesRegex(ValueError, 'whole image'):
            diff.diff_screenshots(self.a, self.b, self.root / 'x',
                                  top_mask=30, bottom_mask=30)

    def test_failed_rerun_does_not_leave_a_stale_pass(self):
        out = self.root / 'rerun'
        diff.diff_screenshots(self.a, self.a, out)
        self.assertTrue((out / 'result.json').is_file())
        self.b.unlink()
        with self.assertRaises(FileNotFoundError):
            diff.diff_screenshots(self.a, self.b, out)
        self.assertFalse((out / 'result.json').exists())

    def test_output_may_not_overwrite_input(self):
        out = self.root / 'collide'
        out.mkdir()
        shutil.copy(self.a, out / 'diff.png')
        with self.assertRaisesRegex(ValueError, 'overwrite input'):
            diff.diff_screenshots(out / 'diff.png', self.b, out)

    def test_cli_reports_unavailable_rather_than_a_verdict(self):
        proc = subprocess.run(
            [sys.executable, str(HERE / 'diff_screenshots.py'),
             str(self.a), str(self.root / 'missing.png'), '--output-dir', str(self.root / 'z')],
            capture_output=True, text=True)
        self.assertEqual(proc.returncode, 2)
        self.assertIn('not a pass and not a mismatch', proc.stderr)

    def test_repeated_hierarchy_labels_are_not_matched(self):
        original = self.root / 'o.xml'
        candidate = self.root / 'c.xml'
        original.write_text('<hierarchy>'
                            '<node text="Item" bounds="[0,0][10,10]"/>'
                            '<node text="Item" bounds="[0,20][10,30]"/>'
                            '<node text="Only" bounds="[0,40][10,50]"/>'
                            '</hierarchy>')
        candidate.write_text('<hierarchy>'
                             '<node text="Item" bounds="[0,5][10,15]"/>'
                             '<node text="Item" bounds="[0,25][10,35]"/>'
                             '<node text="Only" bounds="[0,48][10,58]"/>'
                             '</hierarchy>')
        result = diff.compare_hierarchies(original, candidate)
        self.assertEqual([d['identifier'] for d in result['deltas']], ['Only'])
        self.assertIn('Item', result['ambiguous_identifiers'])


# --------------------------------------------------------------------------

class InventoryTests(Temp):
    def archive(self, name, members):
        path = self.root / name
        with zipfile.ZipFile(path, 'w') as handle:
            for member in members:
                handle.writestr(member, b'x')
        return path

    def test_member_list_is_not_dumped_by_default(self):
        path = self.archive('big.apk', [f'res/drawable/a{i}.png' for i in range(500)])
        report = inventory.inventory(path)
        self.assertNotIn('members', report['archive'])
        self.assertEqual(report['archive']['member_count'], 500)
        self.assertEqual(report['archive']['top_level'], {'res': 500})
        rendered = json.dumps(report)
        self.assertLess(len(rendered), 20000, 'summary output must stay small')

    def test_members_flag_writes_a_separate_file(self):
        path = self.archive('app.apk', ['classes.dex', 'AndroidManifest.xml'])
        target = self.root / 'members.txt'
        code = inventory.main([str(path), '--output', str(self.root / 'r.json'),
                               '--members', str(target)])
        self.assertEqual(code, 0)
        self.assertEqual(sorted(target.read_text().split()),
                         ['AndroidManifest.xml', 'classes.dex'])

    def test_flutter_wrapper_dex_is_explained(self):
        path = self.archive('f.apk', ['classes.dex', 'lib/arm64-v8a/libapp.so',
                                      'lib/arm64-v8a/libflutter.so',
                                      'assets/flutter_assets/FontManifest.json'])
        report = inventory.inventory(path)
        self.assertEqual(report['android_abis'], ['arm64-v8a'])
        self.assertTrue(any('wrapper' in note for note in report['framework_guess']))
        self.assertEqual(report['assets']['flutter_font_manifest']['count'], 1)

    def test_unsafe_members_reported_not_extracted(self):
        link = zipfile.ZipInfo('link')
        link.create_system = 3
        link.external_attr = 0o120777 << 16
        path = self.root / 'unsafe.apk'
        with zipfile.ZipFile(path, 'w') as handle:
            handle.writestr('../escape', b'x')
            handle.writestr('C:\\escape', b'x')
            handle.writestr(link, b'/etc/passwd')
        report = inventory.inventory(path)
        self.assertEqual(len(report['archive']['unsafe_members']), 3)
        self.assertEqual(sorted(p.name for p in self.root.iterdir()), ['unsafe.apk'])

    def test_refuses_overwrite_without_force(self):
        path = self.archive('a.apk', ['classes.dex'])
        out = self.root / 'r.json'
        self.assertEqual(inventory.main([str(path), '--output', str(out)]), 0)
        self.assertEqual(inventory.main([str(path), '--output', str(out)]), 2)
        self.assertEqual(inventory.main([str(path), '--output', str(out), '--force']), 0)

    def test_bad_input_exits_cleanly(self):
        bad = self.root / 'not-a-zip.apk'
        bad.write_text('nope')
        for target in (bad, self.root / 'missing.apk', self.root):
            self.assertEqual(inventory.main([str(target)]), 2)


# --------------------------------------------------------------------------

class ThemeTests(Temp):
    def test_exact_flat_colours_survive_clustering(self):
        for rgb in ((0, 0, 0), (255, 255, 255), (30, 136, 229)):
            path = self.root / 'flat.png'
            pngtool.encode(path, 2, 2, solid(2, 2, rgb))
            colours, _ = theme_extract.extract_colours([path])
            self.assertEqual(colours[0]['rgb'], list(rgb))
    def test_colours_are_ranked_by_coverage(self):
        width, height = 40, 40
        pixels = bytearray(solid(width, height, (255, 255, 255)))
        for y in range(0, 10):
            for x in range(width):
                o = (y * width + x) * 3
                pixels[o:o + 3] = bytes((0x1E, 0x88, 0xE5))
        path = self.root / 's.png'
        pngtool.encode(path, width, height, bytes(pixels))
        colours, total = theme_extract.extract_colours([path])
        self.assertEqual(total, width * height)
        self.assertGreater(colours[0]['coverage'], 0.7)
        roles = theme_extract.classify(colours)
        self.assertEqual(len({c['hex'] for c in roles.values()}), len(roles),
                         'a colour must not be assigned to two roles')

    def test_spacing_uses_nearest_neighbours_only(self):
        """Three stacked items 16px apart are a 16px rhythm, not 16 and 32."""
        path = self.root / 'h.xml'
        path.write_text('<hierarchy>'
                        '<node bounds="[0,0][100,20]"/>'
                        '<node bounds="[0,36][100,56]"/>'
                        '<node bounds="[0,72][100,92]"/>'
                        '</hierarchy>')
        spacing = theme_extract.extract_spacing([path], dpr=2.0)
        self.assertEqual([g['dp'] for g in spacing['gaps_dp']], [8])
        self.assertEqual(spacing['inferred_base_unit_dp'], 8)

    def test_contrast_ratio_matches_wcag(self):
        self.assertEqual(theme_extract.contrast_ratio((0, 0, 0), (255, 255, 255)), 21.0)

    def test_dp_conversion_requires_density(self):
        shot = self.root / 's.png'
        pngtool.encode(shot, 4, 4, solid(4, 4, (1, 1, 1)))
        hier = self.root / 'h.xml'
        hier.write_text('<hierarchy><node bounds="[0,0][10,10]"/></hierarchy>')
        self.assertEqual(theme_extract.main([str(shot), '--hierarchy', str(hier)]), 2)


# --------------------------------------------------------------------------

class DartExampleTests(Temp):
    @unittest.skipUnless(shutil.which('dart'), 'Dart SDK is not installed')
    def test_documented_refresh_is_bounded_and_shared(self):
        doc = (HERE.parent / 'references/flutter-build.md').read_text()
        section = doc.split('### Bounded session refresh example', 1)[1]
        example = section.split('```dart\n', 1)[1].split('```', 1)[0]
        program = self.root / 'refresh_test.dart'
        program.write_text("import 'dart:async';\n" + example + r'''
void check(bool condition, String message) {
  if (!condition) throw StateError(message);
}
Future<void> main() async {
  var calls = 0;
  var refreshes = 0;
  final failing = SessionReader<int>(token: 'old',
    read: (token) async { calls++; throw Unauthorized(); },
    refresh: () async { refreshes++; return 'new'; });
  try { await failing.read(); throw StateError('expected Unauthorized'); }
  on Unauthorized { }
  check(calls == 2 && refreshes == 1, '401 retry must be bounded');

  final gate = Completer<String>();
  refreshes = 0;
  final sent = <String>[];
  final shared = SessionReader<int>(token: 'old',
    read: (token) async {
      sent.add(token);
      if (token == 'old') throw Unauthorized();
      return 7;
    },
    refresh: () { refreshes++; return gate.future; });
  final results = Future.wait([shared.read(), shared.read()]);
  await Future<void>.delayed(Duration.zero);
  check(refreshes == 1, 'concurrent refresh must be shared');
  gate.complete('new');
  check((await results).every((v) => v == 7), 'both reads must finish');
  check(sent.where((v) => v == 'new').length == 2, 'new token must be applied');

  final brokenGate = Completer<String>();
  refreshes = 0;
  final broken = SessionReader<int>(token: 'old',
    read: (_) async => throw Unauthorized(),
    refresh: () { refreshes++; return brokenGate.future; });
  Future<bool> fails() async {
    try { await broken.read(); return false; }
    on StateError { return true; }
  }
  final failures = Future.wait([fails(), fails()]);
  await Future<void>.delayed(Duration.zero);
  brokenGate.completeError(StateError('refresh failed'));
  check((await failures).every((v) => v), 'refresh error must reach every waiter');
  check(refreshes == 1, 'failed refresh must also be shared');
}
''')
        result = subprocess.run(['dart', 'run', str(program)],
                                capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
