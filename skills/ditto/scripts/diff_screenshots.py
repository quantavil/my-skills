#!/usr/bin/env python3
"""Visual parity comparison for one checkpoint. No external binaries required.

Uses the pixelmatch YIQ colour-delta metric, so --threshold keeps the same
meaning as the pixelmatch CLI and existing baselines stay comparable.
NumPy is used when importable and is only an accelerator; the pure-standard-
library path produces identical numbers.

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

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pngtool  # noqa: E402

MAX_YIQ_DELTA = 35215.0
MAX_LAYOUT_DELTAS = 40          # keep result.json readable in an agent context
EXCLUDED_INK = (32, 64, 120)    # excluded pixels in diff.png
DIFF_INK = (255, 0, 96)         # changed pixels in diff.png


def _load_numpy():
    try:
        import numpy
        return numpy
    except ImportError:
        return None


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


def excluded_mask(width, height, exclusions, numpy):
    """Return a per-pixel boolean exclusion mask plus the excluded pixel count."""
    if numpy is not None:
        mask = numpy.zeros((height, width), dtype=bool)
        for rect in exclusions:
            mask[rect['y']:rect['y'] + rect['height'],
                 rect['x']:rect['x'] + rect['width']] = True
        return mask, int(mask.sum())
    mask = bytearray(width * height)
    for rect in exclusions:
        for row in range(rect['y'], rect['y'] + rect['height']):
            base = row * width
            mask[base + rect['x']:base + rect['x'] + rect['width']] = b'\x01' * rect['width']
    return mask, sum(mask)


# --------------------------------------------------------------------------
# colour delta (pixelmatch-compatible)
# --------------------------------------------------------------------------

def _delta_scalar(r1, g1, b1, r2, g2, b2):
    y = (r1 - r2) * 0.29889531 + (g1 - g2) * 0.58662247 + (b1 - b2) * 0.11448223
    i = (r1 - r2) * 0.59597799 - (g1 - g2) * 0.27417610 - (b1 - b2) * 0.32180189
    q = (r1 - r2) * 0.21147017 - (g1 - g2) * 0.52261711 + (b1 - b2) * 0.31114694
    return 0.5053 * y * y + 0.299 * i * i + 0.1957 * q * q


def compare_pixels(width, height, a_rgb, b_rgb, mask, cutoff, numpy):
    """Return (changed_count, changed_bitmap) over non-excluded pixels."""
    if numpy is not None:
        a = numpy.frombuffer(a_rgb, dtype=numpy.uint8).reshape(height, width, 3).astype(numpy.float32)
        b = numpy.frombuffer(b_rgb, dtype=numpy.uint8).reshape(height, width, 3).astype(numpy.float32)
        d = a - b
        y = d[..., 0] * 0.29889531 + d[..., 1] * 0.58662247 + d[..., 2] * 0.11448223
        i = d[..., 0] * 0.59597799 - d[..., 1] * 0.27417610 - d[..., 2] * 0.32180189
        q = d[..., 0] * 0.21147017 - d[..., 1] * 0.52261711 + d[..., 2] * 0.31114694
        delta = 0.5053 * y * y + 0.299 * i * i + 0.1957 * q * q
        changed = (delta > cutoff) & (~mask)
        return int(changed.sum()), changed

    changed = bytearray(width * height)
    count = 0
    row_bytes = width * 3
    for row in range(height):
        start = row * row_bytes
        a_row = a_rgb[start:start + row_bytes]
        b_row = b_rgb[start:start + row_bytes]
        if a_row == b_row:
            continue  # identical rows dominate a passing checkpoint
        base = row * width
        for col in range(width):
            if mask[base + col]:
                continue
            o = col * 3
            if a_row[o:o + 3] == b_row[o:o + 3]:
                continue
            if _delta_scalar(a_row[o], a_row[o + 1], a_row[o + 2],
                             b_row[o], b_row[o + 1], b_row[o + 2]) > cutoff:
                changed[base + col] = 1
                count += 1
    return count, changed


# --------------------------------------------------------------------------
# outputs
# --------------------------------------------------------------------------

def write_diff_image(path, width, height, base_rgb, changed, mask, numpy):
    """Dimmed candidate with changed pixels inked and excluded regions tinted."""
    if numpy is not None:
        img = (numpy.frombuffer(base_rgb, dtype=numpy.uint8)
               .reshape(height, width, 3).astype(numpy.uint16))
        img = ((img * 45) // 100).astype(numpy.uint8)
        img[changed] = DIFF_INK
        img[mask] = EXCLUDED_INK
        return pngtool.encode(path, width, height, img.tobytes())

    out = bytearray(len(base_rgb))
    for index in range(width * height):
        o = index * 3
        if mask[index]:
            out[o:o + 3] = bytes(EXCLUDED_INK)
        elif changed[index]:
            out[o:o + 3] = bytes(DIFF_INK)
        else:
            out[o] = base_rgb[o] * 45 // 100
            out[o + 1] = base_rgb[o + 1] * 45 // 100
            out[o + 2] = base_rgb[o + 2] * 45 // 100
    return pngtool.encode(path, width, height, bytes(out))


def write_montage(path, width, height, panels, gap=12):
    """Three panels side by side on a dark background, pure PNG."""
    total = width * len(panels) + gap * (len(panels) + 1)
    canvas = bytearray(b'\x18\x18\x1c' * (total * (height + gap * 2)))
    row_bytes = total * 3
    for index, panel in enumerate(panels):
        x0 = gap + index * (width + gap)
        for row in range(height):
            dest = (row + gap) * row_bytes + x0 * 3
            src = row * width * 3
            canvas[dest:dest + width * 3] = panel[src:src + width * 3]
    return pngtool.encode(path, total, height + gap * 2, bytes(canvas))


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
                           'original_bounds': o, 'candidate_bounds': c,
                           'delta_x': dx, 'delta_y': dy,
                           'delta_width': dw, 'delta_height': dh})
    deltas.sort(key=lambda d: -(abs(d['delta_x']) + abs(d['delta_y'])
                                + abs(d['delta_width']) + abs(d['delta_height'])))
    return {
        'deltas': deltas,
        'only_in_original': sorted(set(original) - set(candidate)),
        'only_in_candidate': sorted(set(candidate) - set(original)),
        'ambiguous_identifiers': sorted(set(amb_o) | set(amb_c)),
    }


# --------------------------------------------------------------------------
# driver
# --------------------------------------------------------------------------

def diff_screenshots(original, candidate, output_dir, threshold=0.1, max_diff_ratio=0.01,
                     exclusions=None, top_mask=0, bottom_mask=0, montage=False,
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
    montage_path = output_dir / 'composite_side_by_side.png'
    artifacts = (diff_path, result_path, montage_path)
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

    numpy = _load_numpy()
    regions = build_exclusions(width, height, exclusions, top_mask, bottom_mask)
    mask, excluded_pixels = excluded_mask(width, height, regions, numpy)
    compared_pixels = width * height - excluded_pixels
    if compared_pixels <= 0:
        raise ValueError('exclusions cover the whole image; nothing would be compared')

    cutoff = MAX_YIQ_DELTA * threshold * threshold
    changed_pixels, changed = compare_pixels(width, height, a_rgb, b_rgb, mask, cutoff, numpy)
    changed_ratio = changed_pixels / compared_pixels
    passed = changed_ratio <= max_diff_ratio

    write_diff_image(diff_path, width, height, b_rgb, changed, mask, numpy)
    montage_file = None
    if montage:
        _, _, diff_rgb = pngtool.decode(diff_path)
        montage_file = write_montage(montage_path, width, height, [a_rgb, b_rgb, diff_rgb])

    layout = {'deltas': [], 'only_in_original': [], 'only_in_candidate': [],
              'ambiguous_identifiers': []}
    if xml_original:
        layout = compare_hierarchies(Path(xml_original).resolve(strict=True),
                                     Path(xml_candidate).resolve(strict=True))

    result = {
        'schema_version': 1,
        'case_id': case_id,
        'original': str(original),
        'candidate': str(candidate),
        'diff_image': str(diff_path),
        'composite_image': str(montage_file) if montage_file else None,
        'width': width, 'height': height,
        'threshold': threshold,
        'metric': 'pixelmatch YIQ colour delta',
        'compared_pixels': compared_pixels,
        'excluded_pixels': excluded_pixels,
        'exclusions': regions,
        'changed_pixels': changed_pixels,
        'changed_ratio': round(changed_ratio, 6),
        'max_allowed_ratio': max_diff_ratio,
        'status': 'pass' if passed else 'fail',
        'layout_delta_count': len(layout['deltas']),
        'layout_deltas': layout['deltas'][:MAX_LAYOUT_DELTAS],
        'layout_deltas_truncated': max(0, len(layout['deltas']) - MAX_LAYOUT_DELTAS),
        'only_in_original': layout['only_in_original'][:MAX_LAYOUT_DELTAS],
        'only_in_candidate': layout['only_in_candidate'][:MAX_LAYOUT_DELTAS],
        'ambiguous_identifiers': layout['ambiguous_identifiers'][:MAX_LAYOUT_DELTAS],
        'limitations': [
            'Visual only. This is not behaviour, persistence, network or accessibility evidence.',
            'A still frame cannot establish animation timing.',
            'Hierarchy deltas are hints: absent nodes do not prove a control is missing.',
        ],
    }
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
    montage_options = parser.add_mutually_exclusive_group()
    montage_options.add_argument('--montage', action='store_true',
                                 help='also write a 3-panel composite for visual review')
    montage_options.add_argument('--no-montage', action='store_true',
                                 help='omit the composite (the default)')
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
            montage=args.montage,
            xml_original=args.xml_original, xml_candidate=args.xml_candidate,
            case_id=args.case_id)
    except (OSError, ValueError, pngtool.PngError) as error:
        print(f'diff_screenshots: {error}', file=sys.stderr)
        print('Comparison unavailable. This is not a pass and not a mismatch.', file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"visual: {result['status'].upper()}  "
              f"{result['changed_pixels']}/{result['compared_pixels']} px "
              f"({result['changed_ratio'] * 100:.3f}%, allowed {result['max_allowed_ratio'] * 100:.3f}%)")
        if result['excluded_pixels']:
            print(f"excluded: {result['excluded_pixels']} px in {len(result['exclusions'])} region(s)")
        if result['layout_delta_count']:
            top = result['layout_deltas'][0]
            print(f"layout: {result['layout_delta_count']} shifted element(s); "
                  f"largest {top['identifier']} dx={top['delta_x']} dy={top['delta_y']} "
                  f"dw={top['delta_width']} dh={top['delta_height']}")
        if result['only_in_original']:
            print(f"missing in candidate: {', '.join(result['only_in_original'][:5])}")
        print(f"artifacts: {args.output_dir}")
    return 0 if passed else 1


if __name__ == '__main__':
    sys.exit(main())
