#!/usr/bin/env python3
"""
snapshot_slides.py — Headless slide screenshot tool using Playwright.

Captures high-resolution screenshots of individual slides from an HTML
presentation, hiding progress bars, navigation controls, and other UI
overlays. Runs entirely headless — no visible browser window.

Usage:
    python snapshot_slides.py slides.html --output-dir snapshots/
    python snapshot_slides.py slides.html --output-dir snapshots/ --scale 3
    python snapshot_slides.py slides.html --output-dir snapshots/ --width 1440 --height 1080
    python snapshot_slides.py slides.html --output-dir snapshots/ --slides 1-5,8,10
    python snapshot_slides.py slides.html --output-dir snapshots/ --format jpeg --quality 90

Dependencies (auto-installed if missing):
    playwright (+ chromium browser)
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def ensure_playwright():
    """Import playwright, installing package + chromium if missing."""
    try:
        import playwright  # noqa: F401
    except ImportError:
        subprocess.check_call(
            [sys.executable, '-m', 'pip', 'install', 'playwright'],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    # Ensure chromium browser is installed
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            p.chromium.executable_path  # noqa: B018
    except Exception:
        subprocess.check_call(
            [sys.executable, '-m', 'playwright', 'install', 'chromium'],
        )


ensure_playwright()

from playwright.sync_api import sync_playwright  # noqa: E402

# CSS injected before capture to hide UI overlays
HIDE_UI_CSS = """
.progress, .progress-bar,
.controls, .navigate, [class*="nav-arrow"],
.cursor, .slide-nav,
.toolbar, [class*="toolbar"],
.ui-overlay, [class*="control-bar"] {
    display: none !important;
    visibility: hidden !important;
    opacity: 0 !important;
    pointer-events: none !important;
}
""".strip()


def parse_slide_spec(spec: str) -> set[int]:
    """Parse a slide specification like '1-5,8,10' into a set of 1-based indices."""
    result: set[int] = set()
    for part in spec.split(','):
        part = part.strip()
        if '-' in part:
            start_s, end_s = part.split('-', 1)
            start, end = int(start_s), int(end_s)
            result.update(range(start, end + 1))
        else:
            result.add(int(part))
    return result


def detect_slides(page) -> list:
    """Detect slide elements in the page using common selectors."""
    selectors = [
        'section.slide',
        'div.slide',
        'section[data-slide]',
        '.reveal .slides > section',
        '.remark-slide-container',
        'section',
    ]
    for selector in selectors:
        elements = page.query_selector_all(selector)
        if elements:
            return elements
    return []


def snapshot_slides(
    html_path: str,
    output_dir: str,
    scale: int = 2,
    width: int | None = None,
    height: int = 1080,
    fmt: str = 'png',
    quality: int = 90,
    slide_spec: str | None = None,
) -> list[Path]:
    """Capture screenshots of each slide in an HTML presentation.

    Args:
        html_path: Path to the HTML slide deck.
        output_dir: Directory for output images.
        scale: Device scale factor (1-4). Higher = crisper output.
        width: Viewport width. If None, auto-detected from slide CSS.
        height: Viewport height.
        fmt: Image format — 'png' or 'jpeg'.
        quality: JPEG quality (1-100). Ignored for PNG.
        slide_spec: Optional slide selection like '1-5,8,10'.

    Returns:
        List of paths to generated screenshot files.
    """
    html_file = Path(html_path).resolve()
    if not html_file.exists():
        print(f"Error: {html_file} not found", file=sys.stderr)
        sys.exit(1)

    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    requested_slides = parse_slide_spec(slide_spec) if slide_spec else None

    file_url = html_file.as_uri()

    saved_files: list[Path] = []

    with sync_playwright() as p:
        # Use a temporary viewport; we'll resize after detecting aspect ratio
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={'width': width or 1920, 'height': height},
            device_scale_factor=scale,
        )
        page = context.new_page()
        page.goto(file_url, wait_until='domcontentloaded', timeout=60000)

        # Auto-detect viewport width from slide dimensions if not specified
        if width is None:
            detected_width = page.evaluate("""() => {
                const slide = document.querySelector(
                    'section.slide, div.slide, section[data-slide], .reveal .slides > section, section'
                );
                if (!slide) return null;
                const style = getComputedStyle(slide);
                const w = parseFloat(style.width);
                const h = parseFloat(style.height);
                if (w > 0 && h > 0) {
                    // Return the slide's natural width, clamped to reasonable range
                    return Math.round(Math.min(Math.max(w, 800), 2560));
                }
                return null;
            }""")
            if detected_width:
                # Determine aspect ratio and pick appropriate viewport
                aspect = detected_width / height if height else 1.78
                if aspect < 1.5:
                    # Likely 4:3 — use 1440×1080
                    final_width = 1440
                else:
                    # Likely 16:9 — use 1920×1080
                    final_width = 1920
            else:
                final_width = 1920

            # Recreate context with correct viewport
            context.close()
            context = browser.new_context(
                viewport={'width': final_width, 'height': height},
                device_scale_factor=scale,
            )
            page = context.new_page()
            page.goto(file_url, wait_until='domcontentloaded', timeout=60000)

        # Inject CSS to hide UI overlays
        page.add_style_tag(content=HIDE_UI_CSS)

        # Wait for fonts and images to load
        page.wait_for_timeout(2000)
        page.evaluate("() => document.fonts?.ready")
        page.wait_for_timeout(500)

        slides = detect_slides(page)
        total = len(slides)

        if total == 0:
            print("Warning: No slides detected. Taking full-page screenshot.", file=sys.stderr)
            dest = out_path / f"slide_001.{fmt}"
            screenshot_opts = {'path': str(dest), 'full_page': True}
            if fmt == 'jpeg':
                screenshot_opts['quality'] = quality
            page.screenshot(**screenshot_opts)                  # type: ignore
            saved_files.append(dest)
        else:
            pad = len(str(total))
            for i in range(total):
                slide_num = i + 1
                if requested_slides and slide_num not in requested_slides:
                    continue

                # Activate this slide, deactivate all others, force reveal-items visible
                page.evaluate(f"""(() => {{
                    const slides = document.querySelectorAll(
                        'section.slide, div.slide, section[data-slide]'
                    );
                    if (slides.length === 0) return;
                    slides.forEach((s, idx) => {{
                        s.classList.toggle('active', idx === {i});
                        s.style.opacity = idx === {i} ? '1' : '0';
                        s.style.pointerEvents = idx === {i} ? 'auto' : 'none';
                        s.style.zIndex = idx === {i} ? '10' : '0';
                    }});
                    const active = slides[{i}];
                    if (active) {{
                        active.querySelectorAll('.reveal-item').forEach(el => {{
                            el.style.opacity = '1';
                            el.style.transform = 'none';
                            el.style.transition = 'none';
                        }});
                    }}
                }})()""")

                page.wait_for_timeout(300)

                dest = out_path / f"slide_{str(slide_num).zfill(pad)}.{fmt}"
                screenshot_opts = {'path': str(dest)}
                if fmt == 'jpeg':
                    screenshot_opts['quality'] = quality
                page.screenshot(**screenshot_opts)                  # type: ignore

                saved_files.append(dest)
                print(f"  [{slide_num}/{total}] {dest.name}")

        context.close()
        browser.close()

    return saved_files


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description='Capture high-resolution screenshots of HTML slides (headless).',
    )
    parser.add_argument('html', help='Path to the HTML slide deck')
    parser.add_argument(
        '--output-dir', '-o', default='snapshots',
        help='Output directory for screenshots (default: snapshots/)',
    )
    parser.add_argument(
        '--scale', type=int, default=2, choices=range(1, 5),
        help='Device scale factor for HiDPI output (default: 2)',
    )
    parser.add_argument(
        '--width', type=int, default=None,
        help='Viewport width in pixels (default: auto-detect from aspect ratio)',
    )
    parser.add_argument(
        '--height', type=int, default=1080,
        help='Viewport height in pixels (default: 1080)',
    )
    parser.add_argument(
        '--format', dest='fmt', default='png', choices=['png', 'jpeg'],
        help='Output image format (default: png)',
    )
    parser.add_argument(
        '--quality', type=int, default=90,
        help='JPEG quality 1-100 (default: 90, ignored for PNG)',
    )
    parser.add_argument(
        '--slides', default=None,
        help='Slide selection, e.g. "1-5,8,10" (default: all)',
    )
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    html_path = Path(args.html)
    if not html_path.exists():
        print(f"Error: File not found: {html_path}", file=sys.stderr)
        sys.exit(1)

    print(f"Snapshotting: {html_path}")
    print(f"  Scale: {args.scale}x | Format: {args.fmt} | Output: {args.output_dir}")
    if args.slides:
        print(f"  Slides: {args.slides}")

    saved = snapshot_slides(
        html_path=str(html_path),
        output_dir=args.output_dir,
        scale=args.scale,
        width=args.width,
        height=args.height,
        fmt=args.fmt,
        quality=args.quality,
        slide_spec=args.slides,
    )

    print(f"\nDone — {len(saved)} screenshot(s) saved to {args.output_dir}/")


if __name__ == '__main__':
    main()
