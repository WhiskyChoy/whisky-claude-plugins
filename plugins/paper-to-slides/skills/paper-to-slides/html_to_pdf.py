#!/usr/bin/env python3
"""
html_to_pdf.py — One-shot HTML slides → PDF.

Snapshots each slide via snapshot_slides.py, then stitches the PNG frames into
a single PDF with Pillow. Replaces the previous manual two-step:

    1. python snapshot_slides.py <html> -o frames/ --scale 2 --format png
    2. python -c "from PIL import Image; ..."

Usage:
    python html_to_pdf.py slides.html
    python html_to_pdf.py slides.html --output slides.pdf
    python html_to_pdf.py slides.html --scale 3 --keep-frames
    python html_to_pdf.py slides.html --slides 1-5,8

Notes:
- Page counters (.slide-counter, .page-number, etc.) update per frame — see
  snapshot_slides.py for the sync logic.
- Frames are written to a temp directory by default and deleted after the PDF
  is built. Use --keep-frames (or --frames-dir) to keep them for inspection.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def ensure_pillow():
    try:
        import PIL  # noqa: F401
    except ImportError:
        subprocess.check_call(
            [sys.executable, '-m', 'pip', 'install', 'Pillow'],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )


ensure_pillow()

# snapshot_slides lives next to this file — import rather than shell out so
# ensure_playwright() and the in-browser counter-sync logic stay in sync.
SKILL_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SKILL_DIR))
from snapshot_slides import snapshot_slides  # noqa: E402

from PIL import Image  # noqa: E402


def build_pdf(frame_paths: list[Path], pdf_path: Path, resolution: int) -> None:
    if not frame_paths:
        print("Error: no frames to combine", file=sys.stderr)
        sys.exit(1)
    images = [Image.open(f).convert('RGB') for f in frame_paths]
    images[0].save(
        str(pdf_path),
        save_all=True,
        append_images=images[1:],
        resolution=resolution,
    )
    for im in images:
        im.close()


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description='Snapshot an HTML slide deck and combine into a single PDF.',
    )
    p.add_argument('html', help='Path to the HTML slide deck')
    p.add_argument(
        '--output', '-o', default=None,
        help='Output PDF path (default: <html>.pdf next to the input)',
    )
    p.add_argument(
        '--scale', type=int, default=2, choices=range(1, 5),
        help='Device scale factor for HiDPI frames (default: 2)',
    )
    p.add_argument(
        '--width', type=int, default=None,
        help='Viewport width in pixels (default: auto-detect)',
    )
    p.add_argument(
        '--height', type=int, default=1080,
        help='Viewport height in pixels (default: 1080)',
    )
    p.add_argument(
        '--slides', default=None,
        help='Slide selection, e.g. "1-5,8,10" (default: all)',
    )
    p.add_argument(
        '--resolution', type=int, default=150,
        help='PDF DPI metadata (default: 150)',
    )
    p.add_argument(
        '--frames-dir', default=None,
        help='Keep frame PNGs in this directory (default: temp dir, cleaned up)',
    )
    p.add_argument(
        '--keep-frames', action='store_true',
        help='Keep frames beside the PDF in <pdf_stem>_frames/',
    )
    return p


def main() -> None:
    args = build_parser().parse_args()

    html_path = Path(args.html).resolve()
    if not html_path.exists():
        print(f"Error: {html_path} not found", file=sys.stderr)
        sys.exit(1)

    pdf_path = Path(args.output) if args.output else html_path.with_suffix('.pdf')
    pdf_path = pdf_path.resolve()

    if args.frames_dir:
        frames_dir = Path(args.frames_dir).resolve()
        frames_dir.mkdir(parents=True, exist_ok=True)
        cleanup = False
    elif args.keep_frames:
        frames_dir = pdf_path.parent / f"{pdf_path.stem}_frames"
        frames_dir.mkdir(parents=True, exist_ok=True)
        cleanup = False
    else:
        frames_dir = Path(tempfile.mkdtemp(prefix='html_to_pdf_'))
        cleanup = True

    print(f"HTML: {html_path}")
    print(f"PDF:  {pdf_path}")
    print(f"Scale: {args.scale}x | Frames: {frames_dir}")

    try:
        saved = snapshot_slides(
            html_path=str(html_path),
            output_dir=str(frames_dir),
            scale=args.scale,
            width=args.width,
            height=args.height,
            fmt='png',
            quality=100,
            slide_spec=args.slides,
        )
        build_pdf(sorted(saved), pdf_path, args.resolution)
        print(f"\nDone — {len(saved)} page(s) → {pdf_path}")
    finally:
        if cleanup:
            shutil.rmtree(frames_dir, ignore_errors=True)


if __name__ == '__main__':
    main()
