#!/usr/bin/env python3
"""Screenshot visual diffing and layout parity helper for Ditto reconstruction.
Uses pixelmatch CLI to compute pixel-level differences, ImageMagick for masking and
composite 3-panel montages, and parses UI Automator XML hierarchies for layout mapping.
"""
import argparse
import json
from pathlib import Path
import re
import shutil
import struct
import math
import subprocess
import sys
import xml.etree.ElementTree as ET


def parse_bounds(bounds_str):
    """Parse Android UI Automator bounds string format: '[x1,y1][x2,y2]'."""
    m = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', bounds_str)
    if not m:
        return None
    x1, y1, x2, y2 = map(int, m.groups())
    return {
        "x": x1,
        "y": y1,
        "width": x2 - x1,
        "height": y2 - y1,
        "x2": x2,
        "y2": y2
    }


def compare_xml_hierarchies(oracle_xml_path, candidate_xml_path):
    """Compare two UI Automator XML dumps and identify bounding-box/layout deltas."""
    oracle_tree = ET.parse(oracle_xml_path)
    cand_tree = ET.parse(candidate_xml_path)

    def extract_nodes(root):
        nodes = []
        for elem in root.iter('node'):
            text = elem.get('text', '').strip()
            res_id = elem.get('resource-id', '').strip()
            content_desc = elem.get('content-desc', '').strip()
            bounds_raw = elem.get('bounds', '')
            bounds = parse_bounds(bounds_raw) if bounds_raw else None
            identifier = text or content_desc or res_id
            if identifier and bounds and bounds['width'] > 0 and bounds['height'] > 0:
                nodes.append({
                    "identifier": identifier,
                    "class": elem.get('class', ''),
                    "text": text,
                    "content_desc": content_desc,
                    "resource_id": res_id,
                    "bounds": bounds
                })
        return nodes

    oracle_nodes = extract_nodes(oracle_tree.getroot())
    cand_nodes = extract_nodes(cand_tree.getroot())

    deltas = []
    # Match candidate nodes against oracle nodes by identifier (text or content-desc)
    oracle_lookup = {}
    for node in oracle_nodes:
        if node["identifier"] not in oracle_lookup:
            oracle_lookup[node["identifier"]] = node

    for cand_node in cand_nodes:
        ident = cand_node["identifier"]
        if ident in oracle_lookup:
            o_bounds = oracle_lookup[ident]["bounds"]
            c_bounds = cand_node["bounds"]
            dx = c_bounds["x"] - o_bounds["x"]
            dy = c_bounds["y"] - o_bounds["y"]
            dw = c_bounds["width"] - o_bounds["width"]
            dh = c_bounds["height"] - o_bounds["height"]
            if dx != 0 or dy != 0 or dw != 0 or dh != 0:
                deltas.append({
                    "identifier": ident,
                    "class": cand_node["class"],
                    "oracle_bounds": o_bounds,
                    "candidate_bounds": c_bounds,
                    "delta_x": dx,
                    "delta_y": dy,
                    "delta_width": dw,
                    "delta_height": dh
                })

    return deltas


def png_dimensions(path):
    with Path(path).open('rb') as stream:
        header = stream.read(24)
    if len(header) != 24 or header[:8] != b'\x89PNG\r\n\x1a\n' or header[12:16] != b'IHDR':
        raise ValueError(f'Not a PNG image: {path}')
    width, height = struct.unpack('>II', header[16:24])
    if width == 0 or height == 0:
        raise ValueError('Empty PNG dimensions')
    return width, height


def apply_system_bar_mask(image_path, output_path, top_mask=110, bottom_mask=80):
    """Mask exactly the requested rows; never silently compare unmasked input."""
    magick_bin = shutil.which('magick') or shutil.which('convert')
    if not magick_bin:
        raise RuntimeError('ImageMagick is required for requested system-bar masking')
    width, height = png_dimensions(image_path)
    if top_mask < 0 or bottom_mask < 0 or top_mask + bottom_mask >= height:
        raise ValueError('Masks must leave a nonempty comparison area')
    cmd = [magick_bin, str(image_path), '-fill', 'black']
    if top_mask:
        cmd += ['-draw', f'rectangle 0,0 {width - 1},{top_mask - 1}']
    if bottom_mask:
        cmd += ['-draw', f'rectangle 0,{height - bottom_mask} {width - 1},{height - 1}']
    cmd.append(str(output_path))
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0 or not Path(output_path).is_file():
        raise RuntimeError(f'System-bar masking failed: {proc.stderr.strip()}')
    return output_path


def generate_composite_montage(original_path, candidate_path, diff_path, output_path):
    """Generate a 3-panel side-by-side composite: [ORIGINAL | CANDIDATE | DIFF HEATMAP]."""
    magick_bin = shutil.which('magick') or shutil.which('montage')
    if not magick_bin:
        return None

    if magick_bin.endswith('magick'):
        cmd = [
            magick_bin, "montage",
            "-geometry", "540x1200+10+10",
            "-tile", "3x1",
            "-label", "ORIGINAL (Oracle)", str(original_path),
            "-label", "CANDIDATE (Floww)", str(candidate_path),
            "-label", "DIFF HEATMAP", str(diff_path),
            str(output_path)
        ]
    else:
        cmd = [
            magick_bin,
            "-geometry", "540x1200+10+10",
            "-tile", "3x1",
            "-label", "ORIGINAL (Oracle)", str(original_path),
            "-label", "CANDIDATE (Floww)", str(candidate_path),
            "-label", "DIFF HEATMAP", str(diff_path),
            str(output_path)
        ]

    proc = subprocess.run(cmd, capture_output=True, text=True)
    return output_path if proc.returncode == 0 and output_path.exists() else None


def diff_screenshots(original, candidate, output_dir, threshold=0.1, max_diff_ratio=0.01,
                     mask_system_bars=False, top_mask=110, bottom_mask=80,
                     generate_composite=True, xml_original=None, xml_candidate=None, include_aa=False):
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    diff_path = output_dir / 'diff.png'
    result_path = output_dir / 'result.json'
    composite_path = output_dir / 'composite_side_by_side.png'
    artifacts = (diff_path, result_path, composite_path,
                 output_dir / 'masked_orig.png', output_dir / 'masked_cand.png')
    inputs = [Path(p).resolve() for p in (original, candidate, xml_original, xml_candidate) if p]
    if any(p in inputs for p in artifacts):
        raise ValueError('Output artifacts must not overwrite input evidence')
    for stale in artifacts:
        stale.unlink(missing_ok=True)
    original = Path(original).resolve(strict=True)
    candidate = Path(candidate).resolve(strict=True)
    if bool(xml_original) != bool(xml_candidate):
        raise ValueError('Provide both original and candidate XML files')

    if not all(math.isfinite(v) and 0 <= v <= 1 for v in (threshold, max_diff_ratio)):
        raise ValueError('Threshold and maximum difference ratio must be between 0 and 1')
    width, height = png_dimensions(original)
    if png_dimensions(candidate) != (width, height):
        raise ValueError('Image dimensions do not match; do not resize parity evidence')
    excluded_rows = top_mask + bottom_mask if mask_system_bars else 0
    if mask_system_bars and (top_mask < 0 or bottom_mask < 0 or excluded_rows >= height):
        raise ValueError('Masks must leave a nonempty comparison area')
    compared_pixels = width * (height - excluded_rows)

    pixelmatch_bin = shutil.which('pixelmatch')
    if not pixelmatch_bin:
        raise RuntimeError("pixelmatch executable not found on PATH. Install via 'bun add -g pixelmatch pngjs'.")

    orig_to_compare = original
    cand_to_compare = candidate

    if mask_system_bars:
        masked_orig = output_dir / 'masked_orig.png'
        masked_cand = output_dir / 'masked_cand.png'
        orig_to_compare = apply_system_bar_mask(original, masked_orig, top_mask, bottom_mask)
        cand_to_compare = apply_system_bar_mask(candidate, masked_cand, top_mask, bottom_mask)

    # Command: pixelmatch image1.png image2.png [diff.png] [threshold] [includeAA]
    cmd = [pixelmatch_bin, str(orig_to_compare), str(cand_to_compare), str(diff_path), str(threshold), str(include_aa).lower()]
    proc = subprocess.run(cmd, capture_output=True, text=True)

    output = proc.stdout + proc.stderr
    match_pixels = re.search(r'different pixels:\s*(\d+)', output, re.IGNORECASE)
    if proc.returncode not in (0, 66):
        raise RuntimeError(f'pixelmatch failed ({proc.returncode}): {output.strip()}')
    if not match_pixels:
        raise RuntimeError(f'pixelmatch returned no readable changed-pixel metric: {output.strip()}')
    changed_pixels = int(match_pixels.group(1))
    if changed_pixels > compared_pixels or not diff_path.is_file():
        raise RuntimeError('Invalid changed-pixel metric or missing diff image')
    changed_ratio = changed_pixels / compared_pixels
    passed = changed_ratio <= max_diff_ratio

    composite_file = None
    if generate_composite and diff_path.exists():
        composite_file = generate_composite_montage(original, candidate, diff_path, composite_path)

    layout_deltas = []
    if xml_original and xml_candidate:
        xml_o = Path(xml_original).resolve(strict=True)
        xml_c = Path(xml_candidate).resolve(strict=True)
        layout_deltas = compare_xml_hierarchies(xml_o, xml_c)

    result = {
        "original": str(original),
        "candidate": str(candidate),
        "diff_image": str(diff_path) if diff_path.exists() else None,
        "composite_image": str(composite_file) if composite_file else None,
        "threshold": threshold,
        "include_aa": include_aa,
        "width": width,
        "height": height,
        "compared_pixels": compared_pixels,
        "excluded_pixels": width * excluded_rows,
        "top_mask": top_mask if mask_system_bars else 0,
        "bottom_mask": bottom_mask if mask_system_bars else 0,
        "changed_pixels": changed_pixels,
        "changed_ratio": round(changed_ratio, 6),
        "max_allowed_ratio": max_diff_ratio,
        "status": "pass" if passed else "fail",
        "masked_system_bars": mask_system_bars,
        "layout_deltas_count": len(layout_deltas),
        "layout_deltas": layout_deltas,
        "raw_output": output.strip()
    }

    result_path.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    return passed, result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('original', type=Path, help='Path to baseline original screenshot (PNG)')
    parser.add_argument('candidate', type=Path, help='Path to candidate implementation screenshot (PNG)')
    parser.add_argument('--output-dir', type=Path, default=Path('validation/diff'),
                        help='Directory to store diff.png and result.json (default: validation/diff)')
    parser.add_argument('--threshold', type=float, default=0.1,
                        help='Per-pixel color sensitivity threshold 0.0 - 1.0 (default: 0.1)')
    parser.add_argument('--max-diff-ratio', type=float, default=0.01,
                        help='Maximum allowed fraction of changed pixels (default: 0.01 for 1%%)')
    parser.add_argument('--mask-system-bars', action='store_true',
                        help='Mask top status bar and bottom navigation bar before diffing')
    parser.add_argument('--top-mask', type=int, default=110,
                        help='Height in pixels of the top status bar mask (default: 110)')
    parser.add_argument('--bottom-mask', type=int, default=80,
                        help='Height in pixels of the bottom navigation bar mask (default: 80)')
    parser.add_argument('--include-aa', action='store_true', help='Count antialiasing differences')
    parser.add_argument('--no-composite', action='store_true',
                        help='Disable 3-panel composite image generation')
    parser.add_argument('--xml-original', type=Path, default=None,
                        help='Optional path to Oracle UI Automator XML hierarchy dump')
    parser.add_argument('--xml-candidate', type=Path, default=None,
                        help='Optional path to Candidate UI Automator XML hierarchy dump')

    args = parser.parse_args()
    try:
        passed, res = diff_screenshots(
            args.original, args.candidate, args.output_dir,
            threshold=args.threshold, max_diff_ratio=args.max_diff_ratio,
            mask_system_bars=args.mask_system_bars,
            top_mask=args.top_mask, bottom_mask=args.bottom_mask,
            generate_composite=not args.no_composite,
            xml_original=args.xml_original, xml_candidate=args.xml_candidate,
            include_aa=args.include_aa
        )
        print(f"Visual parity comparison: {res['status'].upper()}")
        print(f"Changed pixels: {res['changed_pixels']} ({res['changed_ratio'] * 100:.2f}%) [allowed: {res['max_allowed_ratio'] * 100:.2f}%]")
        if res.get('composite_image'):
            print(f"3-Panel Composite: {res['composite_image']}")
        if res.get('layout_deltas_count', 0) > 0:
            print(f"Layout offsets identified: {res['layout_deltas_count']} elements shifted")
        print(f"Result written to: {args.output_dir / 'result.json'}")
        return 0 if passed else 1
    except Exception as e:
        print(f"Error during visual diff: {e}", file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
