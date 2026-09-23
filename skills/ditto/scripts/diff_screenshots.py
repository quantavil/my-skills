#!/usr/bin/env python3
"""Visual parity comparison for one checkpoint. Pillow images and NumPy comparisons.

Uses the pixelmatch YIQ colour-delta metric, so --threshold keeps the same
meaning as the pixelmatch CLI and existing baselines stay comparable.
NumPy provides one vectorized implementation; uv installs the locked dependencies.

Excluded regions are removed from the comparison, not painted over: their
pixels leave both the numerator and the denominator. Masking a region hides
any real layout error inside it, so exclude only measured, documented
nondeterminism (clock, battery, carrier text).

A tool error is an unavailable comparison, not a pass and not a mismatch.
"""
import argparse
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

import numpy
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pngtool  # noqa: E402

MAX_YIQ_DELTA = 35215.0
MAX_LAYOUT_DELTAS = 40          # keep result.json readable in an agent context
EXCLUDED_INK = (32, 64, 120)    # excluded pixels in diff.png
DIFF_INK = (255, 0, 96)         # changed pixels in diff.png
PANEL_GAP = 12
HEADER_HEIGHT = 19
CANVAS_INK = (24, 24, 28)
LABEL_INK = (245, 245, 247)
# --------------------------------------------------------------------------
# geometry
# --------------------------------------------------------------------------

def parse_rect(value):
    """Parse an 'x,y,w,h' exclusion rectangle."""
    parts = value.split(',')
    if len(parts) != 4:
        raise ValueError(f"exclusion must be 'x,y,w,h': {value!r}")
    try:
        x, y, w, h = (int(p) for p in parts)
    except ValueError:
        raise ValueError(f'exclusion values must be integers: {value!r}') from None
    if w <= 0 or h <= 0 or x < 0 or y < 0:
        raise ValueError(f'exclusion must have positive size and nonnegative origin: {value!r}')
    return {'x': x, 'y': y, 'width': w, 'height': h}


def build_exclusions(width, height, rects, top_mask, bottom_mask):
    out = []
    if top_mask:
        out.append({'x': 0, 'y': 0, 'width': width, 'height': top_mask, 'source': 'top-mask'})
    if bottom_mask:
        out.append({'x': 0, 'y': height - bottom_mask, 'width': width,
                    'height': bottom_mask, 'source': 'bottom-mask'})
    for rect in rects or []:
        out.append({**rect, 'source': 'explicit'})
    for rect in out:
        if (rect['x'] + rect['width'] > width) or (rect['y'] + rect['height'] > height):
            raise ValueError(f'exclusion {rect} falls outside the {width}x{height} image')
    return out


def excluded_mask(width, height, exclusions):
    """Return a per-pixel boolean exclusion mask plus the excluded pixel count."""
    mask = numpy.zeros((height, width), dtype=bool)
    for rect in exclusions:
        mask[rect['y']:rect['y'] + rect['height'],
             rect['x']:rect['x'] + rect['width']] = True
    return mask, int(mask.sum())


# --------------------------------------------------------------------------
# colour delta (pixelmatch-compatible)
# --------------------------------------------------------------------------

def compare_pixels(width, height, a_rgb, b_rgb, mask, cutoff):
    """Return (changed_count, changed_bitmap) over non-excluded pixels."""
    a = numpy.frombuffer(a_rgb, dtype=numpy.uint8).reshape(height, width, 3).astype(numpy.float32)
    b = numpy.frombuffer(b_rgb, dtype=numpy.uint8).reshape(height, width, 3).astype(numpy.float32)
    d = a - b
    y = d[..., 0] * 0.29889531 + d[..., 1] * 0.58662247 + d[..., 2] * 0.11448223
    i = d[..., 0] * 0.59597799 - d[..., 1] * 0.27417610 - d[..., 2] * 0.32180189
    q = d[..., 0] * 0.21147017 - d[..., 1] * 0.52261711 + d[..., 2] * 0.31114694
    delta = 0.5053 * y * y + 0.299 * i * i + 0.1957 * q * q
    changed = (delta > cutoff) & (~mask)
    return int(changed.sum()), changed


# --------------------------------------------------------------------------
# outputs
# --------------------------------------------------------------------------

def write_diff_image(path, width, height, base_rgb, changed, mask):
    """Dimmed candidate with changed pixels inked and excluded regions tinted."""
    img = (numpy.frombuffer(base_rgb, dtype=numpy.uint8)
           .reshape(height, width, 3).astype(numpy.uint16))
    img = ((img * 45) // 100).astype(numpy.uint8)
    img[changed] = DIFF_INK
    img[mask] = EXCLUDED_INK
    return pngtool.encode(path, width, height, img.tobytes())


def write_triptych(path, width, height, panels, gap=PANEL_GAP):
    """Write labeled original, clone, and diff panels without scaling."""
    if len(panels) != 3:
        raise ValueError('triptych requires exactly three panels')
    canvas = Image.new('RGB', (width * 3 + gap * 4, HEADER_HEIGHT + height + gap), CANVAS_INK)
    font = ImageFont.load_default(size=10)
    for index, (panel, label) in enumerate(zip(panels, ('ORIGINAL APK', 'CLONE APK', 'DIFF'))):
        x = gap + index * (width + gap)
        canvas.paste(Image.frombytes('RGB', (width, height), panel), (x, HEADER_HEIGHT))
        # Clip a label to its panel on tiny test images, never into neighbouring panels.
        header = Image.new('RGB', (width, HEADER_HEIGHT), CANVAS_INK)
        ImageDraw.Draw(header).text((width / 2, 4), label, font=font, fill=LABEL_INK, anchor='mt')
        canvas.paste(header, (x, 0))
    canvas.save(path, format='PNG')
    return path


# --------------------------------------------------------------------------
# hierarchy deltas
# --------------------------------------------------------------------------

def parse_bounds(value):
    if not value or not value.startswith('['):
        return None
    try:
        first, second = value.replace('][', '|').strip('[]').split('|')
        x1, y1 = (int(v) for v in first.split(','))
        x2, y2 = (int(v) for v in second.split(','))
    except ValueError:
        return None
    if x2 <= x1 or y2 <= y1:
        return None
    return {'x': x1, 'y': y1, 'width': x2 - x1, 'height': y2 - y1}


def _nodes(path):
    nodes = {}
    ambiguous = set()
    for element in ET.parse(path).getroot().iter('node'):
        text = (element.get('text') or '').strip()
        desc = (element.get('content-desc') or '').strip()
        res = (element.get('resource-id') or '').strip()
        identifier = res or text or desc
        bounds = parse_bounds(element.get('bounds') or '')
        if not identifier or not bounds:
            continue
        if identifier in nodes:
            ambiguous.add(identifier)   # repeated labels cannot be matched reliably
            continue
        nodes[identifier] = {'identifier': identifier, 'class': element.get('class') or '',
                             'bounds': bounds}
    for identifier in ambiguous:
        nodes.pop(identifier, None)
    return nodes, sorted(ambiguous)


def compare_hierarchies(original_xml, candidate_xml):
    original, amb_o = _nodes(original_xml)
    candidate, amb_c = _nodes(candidate_xml)
    deltas = []
    for identifier, node in candidate.items():
        if identifier not in original:
            continue
        o, c = original[identifier]['bounds'], node['bounds']
        dx, dy = c['x'] - o['x'], c['y'] - o['y']
        dw, dh = c['width'] - o['width'], c['height'] - o['height']
        if dx or dy or dw or dh:
            deltas.append({'identifier': identifier, 'class': node['class'],
                           'original_bounds': o, 'clone_bounds': c,
                           'delta_x': dx, 'delta_y': dy,
                           'delta_width': dw, 'delta_height': dh})
    deltas.sort(key=lambda d: -(abs(d['delta_x']) + abs(d['delta_y'])
                                + abs(d['delta_width']) + abs(d['delta_height'])))
    return {
        'deltas': deltas,
        'only_in_original': sorted(set(original) - set(candidate)),
        'only_in_clone': sorted(set(candidate) - set(original)),
        'ambiguous_identifiers': sorted(set(amb_o) | set(amb_c)),
    }


# --------------------------------------------------------------------------
# driver
# --------------------------------------------------------------------------

def diff_screenshots(original, candidate, output_dir, threshold=0.1, max_diff_ratio=0.01,
                     exclusions=None, top_mask=0, bottom_mask=0, triptych=True,
                     xml_original=None, xml_candidate=None, case_id=None):
    # Paths are resolved leniently first so that stale artifacts are cleared
    # before anything can raise. Otherwise a rerun against a missing input
    # fails while last run's result.json still sits there reading "pass".
    original = Path(original).resolve()
    candidate = Path(candidate).resolve()
    output_dir = Path(output_dir).resolve()

    if bool(xml_original) != bool(xml_candidate):
        raise ValueError('provide both --xml-original and --xml-candidate, or neither')
    if not (0.0 <= threshold <= 1.0) or not (0.0 <= max_diff_ratio <= 1.0):
        raise ValueError('threshold and max-diff-ratio must be between 0 and 1')

    diff_path = output_dir / 'diff.png'
    result_path = output_dir / 'result.json'
    triptych_path = output_dir / 'triptych.png'
    artifacts = (diff_path, result_path, triptych_path)
    inputs = {Path(p).resolve() for p in (original, candidate, xml_original, xml_candidate) if p}
    if inputs & set(artifacts):
        raise ValueError('output artifacts must not overwrite input evidence')

    output_dir.mkdir(parents=True, exist_ok=True)
    for stale in artifacts:
        stale.unlink(missing_ok=True)

    for required in (original, candidate):
        if not required.is_file():
            raise FileNotFoundError(f'input evidence not found: {required}')

    width, height, a_rgb = pngtool.decode(original)
    c_width, c_height, b_rgb = pngtool.decode(candidate)
    if (c_width, c_height) != (width, height):
        raise ValueError(
            f'dimensions differ ({width}x{height} vs {c_width}x{c_height}); '
            're-capture in a matched environment rather than resizing parity evidence')

    regions = build_exclusions(width, height, exclusions, top_mask, bottom_mask)
    mask, excluded_pixels = excluded_mask(width, height, regions)
    compared_pixels = width * height - excluded_pixels
    if compared_pixels <= 0:
        raise ValueError('exclusions cover the whole image; nothing would be compared')

    cutoff = MAX_YIQ_DELTA * threshold * threshold
    changed_pixels, changed = compare_pixels(width, height, a_rgb, b_rgb, mask, cutoff)
    changed_ratio = changed_pixels / compared_pixels
    passed = changed_ratio <= max_diff_ratio

    write_diff_image(diff_path, width, height, b_rgb, changed, mask)
    triptych_file = None
    if triptych:
        _, _, diff_rgb = pngtool.decode(diff_path)
        triptych_file = write_triptych(triptych_path, width, height, [a_rgb, b_rgb, diff_rgb])

    layout = {'deltas': [], 'only_in_original': [], 'only_in_clone': [],
              'ambiguous_identifiers': []}
    if xml_original:
        layout = compare_hierarchies(Path(xml_original).resolve(strict=True),
                                     Path(xml_candidate).resolve(strict=True))

    result = {
        'schema_version': 1,
        'case_id': case_id,
        'original': str(original),
        'clone': str(candidate),
        'diff_image': str(diff_path),
        'triptych_image': str(triptych_file) if triptych_file else None,
        'width': width, 'height': height,
        'threshold': threshold,
        'metric': 'pixelmatch YIQ colour delta',
        'compared_pixels': compared_pixels,
        'excluded_pixels': excluded_pixels,
        'exclusions': regions,
        'changed_pixels': changed_pixels,
        'changed_ratio': round(changed_ratio, 6),
        'max_allowed_ratio': max_diff_ratio,
        'visual_metric_status': 'pass' if passed else 'fail',
        'layout_comparison_status': 'compared' if xml_original else 'not_run',
        'layout_reason': None if xml_original else 'paired XML not supplied',
        'layout_deltas': layout['deltas'][:MAX_LAYOUT_DELTAS],
        'layout_deltas_truncated': max(0, len(layout['deltas']) - MAX_LAYOUT_DELTAS),
        'only_in_original': layout['only_in_original'][:MAX_LAYOUT_DELTAS],
        'only_in_clone': layout['only_in_clone'][:MAX_LAYOUT_DELTAS],
        'ambiguous_identifiers': layout['ambiguous_identifiers'][:MAX_LAYOUT_DELTAS],
        'limitations': [
            'Visual only. This is not behaviour, persistence, network or accessibility evidence.',
            'A still frame cannot establish animation timing.',
            'Hierarchy deltas are hints: absent nodes do not prove a control is missing.',
        ],
    }
    if xml_original:
        result.update({
            'layout_delta_count': len(layout['deltas']),
            'only_in_original_count': len(layout['only_in_original']),
            'only_in_clone_count': len(layout['only_in_clone']),
        })
    result_path.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    return passed, result


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('original', type=Path, help='original (oracle) screenshot PNG')
    parser.add_argument('candidate', type=Path, help='candidate build screenshot PNG')
    parser.add_argument('--output-dir', type=Path, default=Path('validation/diff'))
    parser.add_argument('--threshold', type=float, default=0.1,
                        help='per-pixel colour sensitivity 0-1 (default 0.1). This is NOT '
                             'an allowance for 10%% of the screen to differ.')
    parser.add_argument('--max-diff-ratio', type=float, default=0.01,
                        help='allowed fraction of compared pixels that may change (default 0.01)')
    parser.add_argument('--exclude', action='append', default=[], metavar='X,Y,W,H',
                        help='exclusion rectangle, repeatable; excluded pixels leave the denominator')
    parser.add_argument('--top-mask', type=int, default=0,
                        help='exclude N rows at the top. Measure it; there is no safe default.')
    parser.add_argument('--bottom-mask', type=int, default=0,
                        help='exclude N rows at the bottom. Measure it.')
    parser.add_argument('--no-triptych', action='store_true',
                        help='omit the default labeled original/clone/diff triptych')
    parser.add_argument('--xml-original', type=Path, default=None)
    parser.add_argument('--xml-candidate', type=Path, default=None)
    parser.add_argument('--case-id', default=None, help='coverage case this checkpoint belongs to')
    parser.add_argument('--json', action='store_true', help='print result JSON to stdout')

    args = parser.parse_args()
    try:
        passed, result = diff_screenshots(
            args.original, args.candidate, args.output_dir,
            threshold=args.threshold, max_diff_ratio=args.max_diff_ratio,
            exclusions=[parse_rect(v) for v in args.exclude],
            top_mask=args.top_mask, bottom_mask=args.bottom_mask,
            triptych=not args.no_triptych,
            xml_original=args.xml_original, xml_candidate=args.xml_candidate,
            case_id=args.case_id)
    except (OSError, ValueError, pngtool.PngError) as error:
        print(f'diff_screenshots: {error}', file=sys.stderr)
        print('Comparison unavailable. This is not a pass and not a mismatch.', file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"visual: {result['visual_metric_status'].upper()}  "
              f"{result['changed_pixels']}/{result['compared_pixels']} px "
              f"({result['changed_ratio'] * 100:.3f}%, allowed {result['max_allowed_ratio'] * 100:.3f}%)")
        if result['excluded_pixels']:
            print(f"excluded: {result['excluded_pixels']} px in {len(result['exclusions'])} region(s)")
        if result.get('layout_delta_count'):
            top = result['layout_deltas'][0]
            print(f"layout: {result['layout_delta_count']} shifted element(s); "
                  f"largest {top['identifier']} dx={top['delta_x']} dy={top['delta_y']} "
                  f"dw={top['delta_width']} dh={top['delta_height']}")
        if result['only_in_original']:
            print(f"missing in clone: {', '.join(result['only_in_original'][:5])}")
        print(f"artifacts: {args.output_dir}")
    return 0 if passed else 1


if __name__ == '__main__':
    sys.exit(main())
