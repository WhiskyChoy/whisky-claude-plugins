#!/usr/bin/env python3
"""
inject_logo.py — Inject an organization logo into HTML slide presentations.

Adds CSS rules and logo <img> elements to every slide <section> in an HTML
presentation file.  Supports different positioning for content slides
(header-bar region) vs title/section/end slides (corner overlay).

Usage:
    python inject_logo.py slides.html assets/logo.png
    python inject_logo.py slides.html assets/logo.png --position top-right
    python inject_logo.py slides.html assets/logo.png --content-height 6%
    python inject_logo.py slides*.html assets/logo.png   # multiple files

Persisted at: ~/.claude/skills/paper-to-slides/inject_logo.py
"""

import argparse
import os
import re
import sys
from pathlib import Path


# --- Default configuration ---------------------------------------------------

DEFAULTS = {
    "position": "top-right",       # top-left | top-right | bottom-left | bottom-right
    "content_height": "calc(var(--header-bar-height, 7.6%) - 1.6%)",
    "overlay_height": "6%",
    "offset_x": "2%",
    "offset_y": "0.8%",
    "overlay_offset_x": "3%",
    "overlay_offset_y": "3%",
    "alt_text": "Logo",
    "z_index": "30",
}

# CSS anchor keywords mapped from position label
_POS_MAP = {
    "top-right":    ("top", "right"),
    "top-left":     ("top", "left"),
    "bottom-right": ("bottom", "right"),
    "bottom-left":  ("bottom", "left"),
}


# --- CSS generation ----------------------------------------------------------

def build_logo_css(cfg):
    """Generate the CSS block for logo placement.

    Args:
        cfg: dict of configuration values (merged defaults + overrides).

    Returns:
        A CSS string to be injected before the PAGE NUMBER section.
    """
    vert, horiz = _POS_MAP.get(cfg["position"], ("top", "right"))

    # Content slides — logo inside the header bar
    content_vert_prop = vert
    content_vert_val = cfg["offset_y"]
    content_horiz_prop = horiz
    content_horiz_val = cfg["offset_x"]

    # Overlay slides (title/section/end) — corner placement
    overlay_vert_prop = vert
    overlay_vert_val = cfg["overlay_offset_y"]
    overlay_horiz_prop = horiz
    overlay_horiz_val = cfg["overlay_offset_x"]

    return f"""/* ---- LOGO (auto-injected by inject_logo.py) ---- */
.slide-logo {{
  position: absolute;
  z-index: {cfg["z_index"]};
  pointer-events: none;
}}
/* Content slides: logo in header bar */
.slide-content .slide-logo {{
  {content_vert_prop}: {content_vert_val};
  {content_horiz_prop}: {content_horiz_val};
  height: {cfg["content_height"]};
}}
.slide-content .slide-logo img {{
  height: 100%;
  width: auto;
  object-fit: contain;
}}
/* Title/section/end slides: corner placement */
.slide-title .slide-logo,
.slide-section .slide-logo,
.slide-end .slide-logo {{
  {overlay_vert_prop}: {overlay_vert_val};
  {overlay_horiz_prop}: {overlay_horiz_val};
  height: {cfg["overlay_height"]};
}}
.slide-title .slide-logo img,
.slide-section .slide-logo img,
.slide-end .slide-logo img {{
  height: 100%;
  width: auto;
  object-fit: contain;
}}

"""


# --- HTML injection ----------------------------------------------------------

_SECTION_RE = re.compile(r'(<section\s+class="slide[^"]*"\s+data-slide="\d+"[^>]*>)')


def inject_logo_into_html(html_content, logo_src, cfg):
    """Inject logo CSS and elements into HTML slide content.

    Args:
        html_content: the full HTML string.
        logo_src: relative path to the logo image (e.g. 'assets/logo.png').
        cfg: configuration dict.

    Returns:
        A tuple of (new_html_content, slide_count).
    """
    # Skip if already injected
    if "slide-logo" in html_content:
        print("  [SKIP] Logo already present in this file.", file=sys.stderr)
        return html_content, 0

    # 1. Inject CSS — before the PAGE NUMBER section if it exists, else before </style>
    css_block = build_logo_css(cfg)

    if "/* ---- PAGE NUMBER ---- */" in html_content:
        html_content = html_content.replace(
            "/* ---- PAGE NUMBER ---- */",
            css_block + "/* ---- PAGE NUMBER ---- */",
        )
    elif "</style>" in html_content:
        html_content = html_content.replace(
            "</style>",
            css_block + "</style>",
        )
    else:
        print("  [WARN] Could not find insertion point for CSS.", file=sys.stderr)

    # 2. Inject logo div into every slide section
    alt = cfg["alt_text"]
    logo_tag = f'<div class="slide-logo"><img src="{logo_src}" alt="{alt}"></div>'
    count = 0

    def _add_logo(match):
        nonlocal count
        count += 1
        return match.group(0) + "\n  " + logo_tag

    html_content = _SECTION_RE.sub(_add_logo, html_content)

    return html_content, count


# --- File processing ---------------------------------------------------------

def process_file(html_path, logo_path, cfg):
    """Process a single HTML file: copy logo if needed, inject CSS + elements.

    Args:
        html_path: path to the HTML slides file.
        logo_path: path to the logo image file.
        cfg: configuration dict.

    Returns:
        Number of slides modified.
    """
    html_path = Path(html_path)
    logo_path = Path(logo_path)

    if not html_path.is_file():
        print(f"Error: HTML file not found: {html_path}", file=sys.stderr)
        return 0
    if not logo_path.is_file():
        print(f"Error: Logo file not found: {logo_path}", file=sys.stderr)
        return 0

    # Determine the relative path from the HTML file to the logo
    assets_dir = html_path.parent / "assets"
    logo_dest = assets_dir / "logo.png"

    # Copy logo to assets/ if not already there
    if not logo_dest.exists() or not logo_dest.samefile(logo_path):
        import shutil
        assets_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(logo_path, logo_dest)
        print(f"  Copied logo to: {logo_dest}")

    # Compute relative src for the <img> tag
    try:
        logo_src = os.path.relpath(logo_dest, html_path.parent).replace("\\", "/")
    except ValueError:
        logo_src = "assets/logo.png"

    # Read, inject, write
    with open(html_path, "r", encoding="utf-8") as f:
        content = f.read()

    new_content, count = inject_logo_into_html(content, logo_src, cfg)

    if count > 0:
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(new_content)
        print(f"  {html_path.name}: injected logo into {count} slides")
    else:
        print(f"  {html_path.name}: no changes made")

    return count


# --- CLI entry point ---------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Inject an organization logo into HTML slide presentations."
    )
    parser.add_argument(
        "html_files",
        nargs="+",
        help="Path(s) to HTML slide file(s)",
    )
    parser.add_argument(
        "logo_path",
        help="Path to the logo image file",
    )
    parser.add_argument(
        "--position", "-p",
        default=DEFAULTS["position"],
        choices=list(_POS_MAP.keys()),
        help=f"Logo corner position (default: {DEFAULTS['position']})",
    )
    parser.add_argument(
        "--content-height",
        default=DEFAULTS["content_height"],
        help="Logo height on content slides (CSS value)",
    )
    parser.add_argument(
        "--overlay-height",
        default=DEFAULTS["overlay_height"],
        help="Logo height on title/section/end slides (CSS value)",
    )
    parser.add_argument(
        "--alt-text",
        default=DEFAULTS["alt_text"],
        help="Alt text for the logo image",
    )
    args = parser.parse_args()

    cfg = {
        **DEFAULTS,
        "position": args.position,
        "content_height": args.content_height,
        "overlay_height": args.overlay_height,
        "alt_text": args.alt_text,
    }

    total = 0
    for html_file in args.html_files:
        print(f"\nProcessing: {html_file}")
        total += process_file(html_file, args.logo_path, cfg)

    print(f"\nDone. Logo injected into {total} slides total.")


if __name__ == "__main__":
    main()
