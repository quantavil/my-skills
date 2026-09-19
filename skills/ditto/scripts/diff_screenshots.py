#!/usr/bin/env python3
"""Screenshot visual diffing helper for Ditto differential parity testing.
Uses pixelmatch CLI to compute pixel-level differences and produces a standard result.json.
"""
import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys


def diff_screenshots(original, candidate, output_dir, threshold=0.1, max_diff_ratio=0.01):
    original = Path(original).resolve(strict=True)
    candidate = Path(candidate).resolve(strict=True)
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    diff_path = output_dir / 'diff.png'
    result_path = output_dir / 'result.json'

    pixelmatch_bin = shutil.which('pixelmatch')
    if not pixelmatch_bin:
        raise RuntimeError("pixelmatch executable not found on PATH. Install via 'bun add -g pixelmatch pngjs'.")

    # Command: pixelmatch image1.png image2.png [diff.png] [threshold] [includeAA]
    cmd = [pixelmatch_bin, str(original), str(candidate), str(diff_path), str(threshold)]
    proc = subprocess.run(cmd, capture_output=True, text=True)

    # pixelmatch outputs changed pixel count, e.g. "different pixels: 42 (0.12%)" or "0"
    output = proc.stdout + proc.stderr
    match = re.search(r'different pixels:\s*(\d+)(?:\s*\(([0-9.]+)%\))?', output, re.IGNORECASE)
    
    changed_pixels = 0
    changed_ratio = 0.0
    if match:
        changed_pixels = int(match.group(1))
        if match.group(2):
            changed_ratio = float(match.group(2)) / 100.0

    passed = changed_ratio <= max_diff_ratio and proc.returncode == 0

    result = {
        "original": str(original),
        "candidate": str(candidate),
        "diff_image": str(diff_path) if diff_path.exists() else None,
        "threshold": threshold,
        "changed_pixels": changed_pixels,
        "changed_ratio": round(changed_ratio, 6),
        "max_allowed_ratio": max_diff_ratio,
        "status": "pass" if passed else "fail",
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

    args = parser.parse_args()
    try:
        passed, res = diff_screenshots(
            args.original, args.candidate, args.output_dir,
            threshold=args.threshold, max_diff_ratio=args.max_diff_ratio
        )
        print(f"Visual parity comparison: {res['status'].upper()}")
        print(f"Changed pixels: {res['changed_pixels']} ({res['changed_ratio'] * 100:.2f}%) [allowed: {res['max_allowed_ratio'] * 100:.2f}%]")
        print(f"Result written to: {args.output_dir / 'result.json'}")
        return 0 if passed else 1
    except Exception as e:
        print(f"Error during visual diff: {e}", file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
