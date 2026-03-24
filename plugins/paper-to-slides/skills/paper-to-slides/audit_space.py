#!/usr/bin/env python3
"""
audit_space.py — DOM-based content fill audit for HTML slide decks.

Measures how much vertical space each content slide actually uses, flags
sparse slides below a threshold, and optionally captures screenshots of
flagged slides for visual review.

Usage:
    python audit_space.py slides.html
    python audit_space.py slides.html --threshold 0.50
    python audit_space.py slides.html --no-screenshots
    python audit_space.py slides.html --slides 1-5,8
    python audit_space.py slides.html --output-dir _space_audit
    python audit_space.py slides.html --report-file report.json

Dependencies (auto-installed if missing):
    playwright (+ chromium browser)
"""

from __future__ import annotations

import argparse
import json
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

# CSS to hide UI overlays during measurement
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

# JS: activate a single slide by index, reveal all hidden items
ACTIVATE_JS = """(idx) => {
    const slides = document.querySelectorAll(
        'section.slide, div.slide, section[data-slide]'
    );
    if (slides.length === 0) return 0;
    slides.forEach((s, i) => {
        s.classList.toggle('active', i === idx);
        s.style.opacity = i === idx ? '1' : '0';
        s.style.pointerEvents = i === idx ? 'auto' : 'none';
        s.style.zIndex = i === idx ? '10' : '0';
    });
    const active = slides[idx];
    if (active) {
        active.querySelectorAll('.reveal-item').forEach(el => {
            el.style.opacity = '1';
            el.style.transform = 'none';
            el.style.transition = 'none';
        });
    }
    return slides.length;
}"""

# JS: measure content fill ratio on the currently active slide
MEASURE_JS = """() => {
    const active = document.querySelector(
        'section.slide.active, div.slide.active, section[data-slide].active'
    );
    if (!active) return null;

    // Determine slide type from class list
    const classList = Array.from(active.classList);

    // Find the content body container
    const contentBody = active.querySelector('.content-body');
    if (!contentBody) {
        return {
            slide_classes: classList,
            skipped: true,
            reason: 'no .content-body found'
        };
    }

    const bodyRect = contentBody.getBoundingClientRect();
    const availableHeight = bodyRect.height;
    if (availableHeight <= 0) {
        return {
            slide_classes: classList,
            skipped: true,
            reason: 'content-body has zero height'
        };
    }

    // Query all visible content children
    const selectors = 'h2, p, ul, ol, li, .roadmap-grid, .fig-panel, ' +
        '.text-panel, table, blockquote, pre, .formula-block, ' +
        'img, figure, .content-columns, .content-grid';
    const children = contentBody.querySelectorAll(selectors);

    let unionTop = Infinity;
    let unionBottom = -Infinity;
    let h2Bottom = -Infinity;
    let bulletCount = 0;
    let visibleChildCount = 0;

    children.forEach(child => {
        const r = child.getBoundingClientRect();
        // Skip invisible elements
        if (r.width === 0 || r.height === 0) return;
        const style = getComputedStyle(child);
        if (style.display === 'none' || style.visibility === 'hidden') return;

        visibleChildCount++;
        unionTop = Math.min(unionTop, r.top);
        unionBottom = Math.max(unionBottom, r.bottom);

        if (child.tagName === 'H2') {
            h2Bottom = Math.max(h2Bottom, r.bottom);
        }
        if (child.tagName === 'LI') {
            bulletCount++;
        }
    });

    if (visibleChildCount === 0 || unionBottom <= unionTop) {
        return {
            slide_classes: classList,
            skipped: true,
            reason: 'no visible content children'
        };
    }

    const usedHeight = unionBottom - bodyRect.top;
    const fillRatio = usedHeight / availableHeight;

    // Body-only fill: exclude h2 heading height
    let bodyOnlyFill = fillRatio;
    if (h2Bottom > bodyRect.top) {
        const headingHeight = h2Bottom - bodyRect.top;
        const bodyOnlyUsed = unionBottom - h2Bottom;
        const bodyOnlyAvailable = availableHeight - headingHeight;
        bodyOnlyFill = bodyOnlyAvailable > 0
            ? bodyOnlyUsed / bodyOnlyAvailable
            : fillRatio;
    }

    return {
        slide_classes: classList,
        skipped: false,
        fill_ratio: Math.round(fillRatio * 1000) / 1000,
        body_only_fill: Math.round(bodyOnlyFill * 1000) / 1000,
        bullet_count: bulletCount,
        available_height_px: Math.round(availableHeight),
        used_height_px: Math.round(usedHeight)
    };
}"""

# Slide types to audit (skip title, section, end)
AUDITABLE_TYPES = {'slide-content', 'slide-figure'}


def parse_slide_spec(spec: str) -> set[int]:
    """Parse a slide specification like '1-5,8,10' into a set of 1-based indices."""
    result: set[int] = set()
    for part in spec.split(','):
        part = part.strip()
        if '-' in part:
            start_s, end_s = part.split('-', 1)
            result.update(range(int(start_s), int(end_s) + 1))
        else:
            result.add(int(part))
    return result


def is_auditable(classes: list[str]) -> bool:
    """Check if a slide's classes indicate it should be audited."""
    return bool(set(classes) & AUDITABLE_TYPES)


def audit_slides(
    html_path: str,
    threshold: float = 0.55,
    output_dir: str | None = None,
    take_screenshots: bool = True,
    scale: int = 1,
    slide_spec: str | None = None,
    report_file: str | None = None,
) -> dict:
    """Audit content fill ratio of each slide and optionally screenshot flagged ones.

    Args:
        html_path: Path to the HTML slide deck.
        threshold: Fill ratio below which a slide is flagged.
        output_dir: Directory for screenshots. Default: _space_audit/ next to HTML.
        take_screenshots: Whether to capture screenshots of flagged slides.
        scale: Screenshot DPI scale factor.
        slide_spec: Optional slide selection like '1-5,8'.
        report_file: If set, write JSON report to this path.

    Returns:
        Report dict with per-slide measurements and flagged status.
    """
    html_file = Path(html_path).resolve()
    if not html_file.exists():
        print(f"Error: {html_file} not found", file=sys.stderr)
        sys.exit(1)

    # Default output dir: _space_audit/ next to the HTML file
    if output_dir is None:
        out_path = html_file.parent / '_space_audit'
    else:
        out_path = Path(output_dir)

    if take_screenshots:
        out_path.mkdir(parents=True, exist_ok=True)

    requested_slides = parse_slide_spec(slide_spec) if slide_spec else None
    file_url = html_file.as_uri()

    report = {
        'html_path': str(html_file),
        'threshold': threshold,
        'total_slides': 0,
        'audited_slides': 0,
        'flagged_count': 0,
        'temp_dir': str(out_path) + '/',
        'slides': [],
    }

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # Start with a temporary viewport; resize after aspect ratio detection
        context = browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            device_scale_factor=scale,
        )
        page = context.new_page()
        page.goto(file_url, wait_until='domcontentloaded', timeout=60000)

        # Auto-detect aspect ratio
        detected_width = page.evaluate("""() => {
            const slide = document.querySelector(
                'section.slide, div.slide, section[data-slide]'
            );
            if (!slide) return null;
            const style = getComputedStyle(slide);
            const w = parseFloat(style.width);
            const h = parseFloat(style.height);
            if (w > 0 && h > 0) {
                return Math.round(Math.min(Math.max(w, 800), 2560));
            }
            return null;
        }""")

        if detected_width:
            aspect = detected_width / 1080
            final_width = 1440 if aspect < 1.5 else 1920
            context.close()
            context = browser.new_context(
                viewport={'width': final_width, 'height': 1080},
                device_scale_factor=scale,
            )
            page = context.new_page()
            page.goto(file_url, wait_until='domcontentloaded', timeout=60000)

        # Inject CSS to hide UI overlays
        page.add_style_tag(content=HIDE_UI_CSS)

        # Wait for fonts and images
        page.wait_for_timeout(2000)
        page.evaluate("() => document.fonts?.ready")
        page.wait_for_timeout(500)

        # Count total slides
        total = page.evaluate("""() => {
            return document.querySelectorAll(
                'section.slide, div.slide, section[data-slide]'
            ).length;
        }""")
        report['total_slides'] = total

        if total == 0:
            print("Warning: No slides detected.", file=sys.stderr)
            context.close()
            browser.close()
            return report

        pad = len(str(total))

        for i in range(total):
            slide_num = i + 1

            if requested_slides and slide_num not in requested_slides:
                continue

            # Activate the slide
            page.evaluate(ACTIVATE_JS, i)
            page.wait_for_timeout(300)

            # Measure
            result = page.evaluate(MEASURE_JS)

            if result is None:
                continue

            classes = result.get('slide_classes', [])

            # Skip non-auditable slide types
            if not is_auditable(classes):
                continue

            if result.get('skipped'):
                continue

            report['audited_slides'] += 1              # type: ignore

            fill_ratio = result['fill_ratio']
            flagged = fill_ratio < threshold

            slide_entry = {
                'slide_number': slide_num,
                'slide_classes': classes,
                'fill_ratio': fill_ratio,
                'body_only_fill': result['body_only_fill'],
                'bullet_count': result['bullet_count'],
                'flagged': flagged,
                'screenshot': None,
                'available_height_px': result['available_height_px'],
                'used_height_px': result['used_height_px'],
            }

            if flagged:
                report['flagged_count'] += 1            # type: ignore

                if take_screenshots:
                    dest = out_path / f"flagged_slide_{str(slide_num).zfill(pad)}.png"
                    page.screenshot(path=str(dest))
                    slide_entry['screenshot'] = str(dest)
                    print(f"  [flagged] Slide {slide_num}: fill={fill_ratio:.1%} → {dest.name}")
                else:
                    print(f"  [flagged] Slide {slide_num}: fill={fill_ratio:.1%}")
            else:
                print(f"  [  ok  ] Slide {slide_num}: fill={fill_ratio:.1%}")

            report['slides'].append(slide_entry)       # type: ignore

        context.close()
        browser.close()

    # Write report
    if report_file:
        report_path = Path(report_file)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False))
        print(f"\nReport written to {report_path}")
    elif take_screenshots and report['flagged_count'] > 0:      # type: ignore
        # Also write report.json into the output dir
        default_report = out_path / 'report.json'
        default_report.write_text(json.dumps(report, indent=2, ensure_ascii=False))
        print(f"\nReport written to {default_report}")

    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description='Audit content fill ratio of HTML slides and flag sparse ones.',
    )
    parser.add_argument('html', help='Path to the HTML slide deck')
    parser.add_argument(
        '--threshold', type=float, default=0.55,
        help='Fill ratio below which a slide is flagged (default: 0.55)',
    )
    parser.add_argument(
        '--output-dir', default=None,
        help='Directory for screenshots (default: _space_audit/ next to HTML)',
    )
    parser.add_argument(
        '--no-screenshots', action='store_true',
        help='Skip screenshot capture (report only)',
    )
    parser.add_argument(
        '--scale', type=int, default=1, choices=range(1, 5),
        help='Screenshot DPI scale (default: 1)',
    )
    parser.add_argument(
        '--slides', default=None,
        help='Audit specific slides only, e.g. "1-5,8" (default: all)',
    )
    parser.add_argument(
        '--report-file', default=None,
        help='Write JSON report to file (default: _space_audit/report.json)',
    )
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    html_path = Path(args.html)
    if not html_path.exists():
        print(f"Error: File not found: {html_path}", file=sys.stderr)
        sys.exit(1)

    print(f"Auditing space usage: {html_path}")
    print(f"  Threshold: {args.threshold:.0%} | Screenshots: {not args.no_screenshots}")
    if args.slides:
        print(f"  Slides: {args.slides}")

    report = audit_slides(
        html_path=str(html_path),
        threshold=args.threshold,
        output_dir=args.output_dir,
        take_screenshots=not args.no_screenshots,
        scale=args.scale,
        slide_spec=args.slides,
        report_file=args.report_file,
    )

    flagged = report['flagged_count']
    audited = report['audited_slides']
    total = report['total_slides']
    print(f"\nDone — {audited}/{total} slides audited, {flagged} flagged (< {args.threshold:.0%} fill)")

    if not args.report_file:
        # Print JSON to stdout for programmatic use
        print("\n" + json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
