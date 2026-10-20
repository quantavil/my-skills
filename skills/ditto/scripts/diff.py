#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["pillow==11.3.0"]
# ///
"""Compare the clone's trace of an experiment with the original's.

Usage: diff.py traces/<experiment>  [--original original] [--clone clone] [--pixel-threshold 2.0]

Compares, step by step (matched by step name):
  notes   recorded output values: must be equal (this is the behaviour verdict)
  texts   visible text in reading order: unified diff
  screen  percentage of differing pixels; writes diff.png next to the clone's step
Writes traces/<experiment>/report.md. Exit 1 when notes or texts differ.
"""

from __future__ import annotations

import argparse
import difflib
import json
import sys
from pathlib import Path


def steps(folder: Path) -> dict[str, Path]:
    """Step folders keyed by name without the NN- prefix."""
    return {p.name.split("-", 1)[-1]: p for p in sorted(folder.iterdir()) if p.is_dir()}


def load(path: Path, default):
    return json.loads(path.read_text()) if path.exists() else default


def compare_notes(original: dict, clone: dict) -> list[str]:
    problems = []
    for key in sorted(set(original) | set(clone)):
        if key not in clone:
            problems.append(f"`{key}`: missing in clone (original {original[key]!r})")
        elif key not in original:
            problems.append(f"`{key}`: clone-only value {clone[key]!r}")
        elif original[key] != clone[key]:
            problems.append(f"`{key}`: original {original[key]!r} ≠ clone {clone[key]!r}")
    return problems


def compare_texts(original: list[str], clone: list[str]) -> list[str]:
    return [line for line in difflib.unified_diff(original, clone, "original", "clone", lineterm="", n=1)]


def compare_screens(original: Path, clone: Path, out: Path) -> float | None:
    from PIL import Image, ImageChops

    if not original.exists() or not clone.exists():
        return None
    a = Image.open(original).convert("RGB")
    b = Image.open(clone).convert("RGB")
    if a.size != b.size:
        return 100.0
    delta = ImageChops.difference(a, b).convert("L").point(lambda v: 255 if v > 24 else 0)
    changed = sum(1 for v in delta.getdata() if v)
    Image.composite(Image.new("RGB", a.size, (255, 0, 64)), b, delta).save(out)
    return 100.0 * changed / (a.size[0] * a.size[1])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("experiment", type=Path)
    parser.add_argument("--original", default="original")
    parser.add_argument("--clone", default="clone")
    parser.add_argument("--pixel-threshold", type=float, default=2.0, help="percent of pixels")
    args = parser.parse_args()

    original_dir, clone_dir = args.experiment / args.original, args.experiment / args.clone
    for folder in (original_dir, clone_dir):
        if not folder.is_dir():
            raise SystemExit(f"missing trace {folder}")

    report = [f"# {args.experiment.name}: {args.original} vs {args.clone}", ""]
    failed = False

    note_problems = compare_notes(load(original_dir / "notes.json", {}), load(clone_dir / "notes.json", {}))
    report += ["## Recorded values", ""]
    report += [f"- ✗ {p}" for p in note_problems] or ["- ✓ all equal"]
    failed |= bool(note_problems)

    original_steps, clone_steps = steps(original_dir), steps(clone_dir)
    report += ["", "## Steps", "", "| Step | Text | Pixels differing | Diff image |", "|---|---|---:|---|"]
    details = []
    for name in list(original_steps) + [n for n in clone_steps if n not in original_steps]:
        a, b = original_steps.get(name), clone_steps.get(name)
        if a is None or b is None:
            report.append(f"| {name} | ✗ only in {'clone' if a is None else 'original'} | | |")
            failed = True
            continue
        text_diff = compare_texts(load(a / "texts.json", []), load(b / "texts.json", []))
        pixels = compare_screens(a / "screen.png", b / "screen.png", b / "diff.png")
        pixel_cell = "n/a" if pixels is None else f"{pixels:.1f}%" + (" ✗" if pixels > args.pixel_threshold else "")
        image = f"`{(b / 'diff.png').relative_to(args.experiment)}`" if pixels is not None else ""
        report.append(f"| {name} | {'✗' if text_diff else '✓'} | {pixel_cell} | {image} |")
        if text_diff:
            failed = True
            details += [f"### {name}", "", "```diff", *text_diff, "```", ""]

    if details:
        report += ["", "## Text differences", "", *details]
    report_path = args.experiment / "report.md"
    report_path.write_text("\n".join(report) + "\n")
    print("\n".join(report[:40]))
    print(f"→ {report_path}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
