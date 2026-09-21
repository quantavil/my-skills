#!/usr/bin/env python3
"""Derive design tokens from captured evidence, once, for the whole clone.

Cloning screen by screen re-derives the same colours and spacing every time.
This reads the screenshots and hierarchy dumps you already captured and
produces one token set, so every later screen is a cheap lookup.

  colours  quantised from screenshot pixels, ranked by screen coverage,
           with WCAG contrast against the dominant surface
  spacing  exact gaps between adjacent sibling bounds in the UI hierarchy,
           converted to logical pixels using the capture density

Everything emitted is a measurement of rendered output, not the original
app's declared theme. Constants are written with a VERIFY marker because a
sampled colour can be a blend, a shadow, or a compressed artefact.

Standard library only; NumPy is used when importable, purely for speed.
"""
import argparse
from collections import Counter
import json
import math
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pngtool  # noqa: E402

BOUNDS_RE = re.compile(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]')
COMMON_SCALE = (2, 4, 6, 8, 12, 16, 20, 24, 32, 40, 48, 56, 64)


def _load_numpy():
    try:
        import numpy
        return numpy
    except ImportError:
        return None


# --------------------------------------------------------------------------
# colour
# --------------------------------------------------------------------------

def relative_luminance(rgb):
    channels = []
    for value in rgb:
        srgb = value / 255
        channels.append(srgb / 12.92 if srgb <= 0.04045
                        else ((srgb + 0.055) / 1.055) ** 2.4)
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]


def contrast_ratio(a, b):
    la, lb = relative_luminance(a), relative_luminance(b)
    lighter, darker = max(la, lb), min(la, lb)
    return round((lighter + 0.05) / (darker + 0.05), 2)


def saturation(rgb):
    high, low = max(rgb), min(rgb)
    return 0.0 if high == 0 else (high - low) / high


def hex_of(rgb):
    return '#{:02X}{:02X}{:02X}'.format(*rgb)


def _histogram(paths, numpy, bits=5):
    """Count colours bucketed to `bits` per channel across every screenshot."""
    shift = 8 - bits
    counts = Counter()
    exact = Counter()
    total = 0
    for path in paths:
        width, height, rgb = pngtool.decode(path)
        total += width * height
        if numpy is not None:
            pixels = numpy.frombuffer(rgb, dtype=numpy.uint8).reshape(-1, 3)
            keys = (pixels[:, 0].astype(numpy.int32) << 16) \
                | (pixels[:, 1].astype(numpy.int32) << 8) | pixels[:, 2]
            values, freq = numpy.unique(keys, return_counts=True)
            for value, count in zip(values.tolist(), freq.tolist()):
                exact[value] += count
        else:
            for offset in range(0, len(rgb), 3):
                key = (rgb[offset] << 16) | (rgb[offset + 1] << 8) | rgb[offset + 2]
                exact[key] += 1
    representatives = {}
    for value, count in exact.items():
        colour = ((value >> 16) & 255, (value >> 8) & 255, value & 255)
        key = ((colour[0] >> shift) << (2 * bits)) \
            | ((colour[1] >> shift) << bits) | (colour[2] >> shift)
        counts[key] += count
        if key not in representatives or count > representatives[key][1]:
            representatives[key] = (colour, count)
    return counts, total, representatives


def extract_colours(paths, limit=12, merge_distance=24):
    numpy = _load_numpy()
    counts, total, representatives = _histogram(paths, numpy)
    if not total:
        raise ValueError('no pixels were read')

    ranked = []
    for key, count in counts.most_common(600):
        rgb = representatives[key][0]
        merged = False
        for entry in ranked:
            if math.dist(entry['rgb'], rgb) < merge_distance:
                entry['count'] += count
                merged = True
                break
        if not merged:
            ranked.append({'rgb': rgb, 'count': count})
        if len(ranked) >= limit * 4:
            break

    ranked.sort(key=lambda e: -e['count'])
    ranked = ranked[:limit]
    surface = ranked[0]['rgb'] if ranked else (255, 255, 255)
    out = []
    for entry in ranked:
        rgb = entry['rgb']
        out.append({
            'hex': hex_of(rgb),
            'argb': '0xFF{:02X}{:02X}{:02X}'.format(*rgb),
            'rgb': list(rgb),
            'coverage': round(entry['count'] / total, 5),
            'saturation': round(saturation(rgb), 3),
            'luminance': round(relative_luminance(rgb), 4),
            'contrast_vs_surface': contrast_ratio(rgb, surface),
        })
    return out, total


def classify(colours):
    """Suggest roles. These are hypotheses to check against the app, not facts."""
    if not colours:
        return {}
    roles = {'surface': colours[0]}
    taken = {colours[0]['hex']}

    def claim(role, candidates, key):
        pool = [c for c in candidates if c['hex'] not in taken]
        if not pool:
            return
        chosen = max(pool, key=key)
        roles[role] = chosen
        taken.add(chosen['hex'])

    rest = colours[1:]
    # Body text first: it is the most reliably identifiable non-surface colour.
    claim('onSurface', [c for c in rest if c['contrast_vs_surface'] >= 4.5],
          lambda c: c['coverage'])
    claim('primary', [c for c in rest if c['saturation'] >= 0.35 and c['coverage'] < 0.35],
          lambda c: c['saturation'] * c['coverage'])
    claim('onSurfaceVariant', [c for c in rest if 2.0 <= c['contrast_vs_surface'] < 4.5],
          lambda c: c['coverage'])
    return roles


# --------------------------------------------------------------------------
# spacing
# --------------------------------------------------------------------------

def _rects(path):
    out = []
    for element in ET.parse(path).getroot().iter('node'):
        match = BOUNDS_RE.match(element.get('bounds') or '')
        if not match:
            continue
        x1, y1, x2, y2 = (int(v) for v in match.groups())
        if x2 > x1 and y2 > y1:
            out.append((x1, y1, x2, y2))
    return out


def extract_spacing(paths, dpr, min_count=2, limit=12, max_gap_px=400):
    """Gaps between *nearest* neighbours only, in dp.

    Every pair would also count A-to-C whenever B sits between them, which
    turns one 8 dp rhythm into a spray of 8, 16, 24. Only the closest
    neighbour in each direction is a real gap.
    """
    gaps = Counter()
    starts = Counter()
    for path in paths:
        rects = _rects(path)
        for a in rects:
            below = min((b[1] - a[3] for b in rects
                         if b is not a and b[1] >= a[3]
                         and min(a[2], b[2]) - max(a[0], b[0]) > 0),
                        default=None)
            if below is not None and 0 < below <= max_gap_px:
                gaps[round(below / dpr)] += 1
            right = min((b[0] - a[2] for b in rects
                         if b is not a and b[0] >= a[2]
                         and min(a[3], b[3]) - max(a[1], b[1]) > 0),
                        default=None)
            if right is not None and 0 < right <= max_gap_px:
                gaps[round(right / dpr)] += 1
        # Start inset only. A trailing edge follows content width, so it is
        # not evidence of padding.
        for x1, _, _, _ in rects:
            if x1 > 0:
                starts[round(x1 / dpr)] += 1

    common = [{'dp': dp, 'occurrences': count}
              for dp, count in gaps.most_common(limit) if count >= min_count and dp > 0]
    gutters = [{'dp': dp, 'occurrences': count}
               for dp, count in starts.most_common(4) if count >= min_count and dp > 0]
    base = _infer_base([g['dp'] for g in common])
    return {'gaps_dp': common, 'start_insets_dp': gutters, 'inferred_base_unit_dp': base}


def _infer_base(values):
    """Largest common unit that divides most observed gaps."""
    if not values:
        return None
    best, best_score = None, 0
    for unit in (8, 4, 6, 2):
        score = sum(1 for v in values if v % unit == 0)
        if score > best_score:
            best, best_score = unit, score
    return best if best_score >= max(1, len(values) // 2) else None


# --------------------------------------------------------------------------
# Dart output
# --------------------------------------------------------------------------

def _dart_name(role):
    return role[0].lower() + role[1:]


def render_dart(colours, roles, spacing, sources):
    lines = [
        '// GENERATED by ditto theme_extract.py from captured evidence.',
        '// Every value below is measured from rendered pixels or hierarchy bounds.',
        '// A sampled colour can be a blend, a shadow, or a compression artefact,',
        '// so confirm each one against the app before treating it as the token.',
        '//',
        '// Evidence:',
    ]
    lines += [f'//   {source}' for source in sources]
    lines += ['', "import 'package:flutter/material.dart';", '', 'abstract final class AppColors {']
    for role, colour in roles.items():
        lines.append(f'  /// {colour["coverage"] * 100:.2f}% of sampled pixels, '
                     f'contrast {colour["contrast_vs_surface"]}:1 vs surface. VERIFY')
        lines.append(f'  static const Color {_dart_name(role)} = '
                     f'Color({colour["argb"]});')
    lines.append('')
    lines.append('  /// Every sampled colour, ranked by coverage. Promote what you confirm.')
    lines.append('  static const List<Color> sampled = <Color>[')
    for colour in colours:
        lines.append(f'    Color({colour["argb"]}), // {colour["hex"]} '
                     f'{colour["coverage"] * 100:.2f}%')
    lines.append('  ];')
    lines.append('}')

    if spacing and spacing.get('gaps_dp'):
        base = spacing.get('inferred_base_unit_dp')
        lines += ['', 'abstract final class AppSpacing {']
        if base:
            lines.append(f'  /// Most observed gaps are multiples of {base} dp.')
            lines.append(f'  static const double unit = {base}.0;')
        for gap in spacing['gaps_dp'][:8]:
            lines.append(f'  /// seen {gap["occurrences"]}x in the hierarchy dumps')
            lines.append(f'  static const double gap{gap["dp"]} = {gap["dp"]}.0;')
        for inset in spacing.get('start_insets_dp', [])[:3]:
            lines.append(f'  /// start inset, seen {inset["occurrences"]}x')
            lines.append(f'  static const double inset{inset["dp"]} = {inset["dp"]}.0;')
        lines.append('}')
    return '\n'.join(lines) + '\n'


# --------------------------------------------------------------------------

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('screenshot', nargs='+', type=Path, help='captured original screenshots')
    parser.add_argument('--hierarchy', nargs='*', type=Path, default=[],
                        help='matching UI Automator XML dumps for the spacing scale')
    parser.add_argument('--dpi', type=int, default=None,
                        help='capture density in dpi (e.g. 420). Required for dp conversion.')
    parser.add_argument('--colours', type=int, default=12, help='how many colours to rank')
    parser.add_argument('--dart', type=Path, default=None, help='write a Dart token file here')
    parser.add_argument('--json', type=Path, default=None, help='write the raw measurements here')
    parser.add_argument('--force', action='store_true')
    args = parser.parse_args(argv)

    try:
        colours, sampled = extract_colours(args.screenshot, limit=args.colours)
        roles = classify(colours)
        spacing = None
        if args.hierarchy:
            if not args.dpi:
                raise ValueError('--dpi is required to convert hierarchy pixels to dp; '
                                 'read it from the evidence record or "adb shell wm density"')
            spacing = extract_spacing(args.hierarchy, args.dpi / 160)
    except (OSError, ValueError, ET.ParseError, pngtool.PngError) as error:
        print(f'theme_extract: {error}', file=sys.stderr)
        return 2

    payload = {
        'schema_version': 1,
        'sampled_pixels': sampled,
        'sources': [str(p) for p in list(args.screenshot) + list(args.hierarchy)],
        'density_dpi': args.dpi,
        'device_pixel_ratio': round(args.dpi / 160, 4) if args.dpi else None,
        'colours': colours,
        'suggested_roles': {k: v['hex'] for k, v in roles.items()},
        'spacing': spacing,
        'limitations': [
            'Colours are sampled from rendered output, including blends and shadows.',
            'Role suggestions are hypotheses, not the app\'s declared theme.',
            'Spacing comes from hierarchy bounds; custom-drawn UI reports few nodes.',
            'Text sizes cannot be recovered from these inputs; measure them separately.',
        ],
    }

    for target, text in ((args.json, json.dumps(payload, indent=2) + '\n'),
                         (args.dart, render_dart(colours, roles, spacing, payload['sources']))):
        if not target:
            continue
        if target.exists() and not args.force:
            print(f'theme_extract: {target} exists; pass --force to replace it', file=sys.stderr)
            return 2
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding='utf-8')
        print(f'wrote {target}')

    if not args.json and not args.dart:
        print(json.dumps(payload, indent=2))
    else:
        top = ', '.join(f'{c["hex"]} {c["coverage"] * 100:.1f}%' for c in colours[:4])
        print(f'{len(colours)} colours from {sampled} px: {top}')
        if spacing and spacing['gaps_dp']:
            print('spacing dp: ' + ', '.join(str(g['dp']) for g in spacing['gaps_dp'][:8])
                  + f" (base {spacing['inferred_base_unit_dp']})")
    return 0


if __name__ == '__main__':
    sys.exit(main())
