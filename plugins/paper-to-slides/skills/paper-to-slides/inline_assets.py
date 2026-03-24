#!/usr/bin/env python3
"""
inline_assets.py — Convert an HTML slide deck with external assets into a
single self-contained HTML file by embedding images as base64 data URIs.

Handles:
  - <img src="..."> tags (PNG, JPEG, SVG, GIF, WebP)
  - CSS url(...) references in <style> blocks and inline styles
  - background-image in inline style attributes

Usage:
    python inline_assets.py slides.html --output slides_standalone.html
    python inline_assets.py slides.html  # overwrites in place

Dependencies (auto-installed if missing):
    beautifulsoup4, lxml
"""

from __future__ import annotations

import argparse
import base64
import mimetypes
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse


def ensure_package(package_name, import_name=None):
    """Auto-install a package if not available."""
    import_name = import_name or package_name
    try:
        __import__(import_name)
    except ImportError:
        subprocess.check_call(
            [sys.executable, '-m', 'pip', 'install', package_name],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )


ensure_package('beautifulsoup4', 'bs4')
ensure_package('lxml')

from bs4 import BeautifulSoup  # noqa: E402


MIME_TYPES = {
    '.png': 'image/png',
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.gif': 'image/gif',
    '.svg': 'image/svg+xml',
    '.webp': 'image/webp',
    '.woff': 'font/woff',
    '.woff2': 'font/woff2',
    '.ttf': 'font/ttf',
    '.otf': 'font/otf',
}


def resolve_path(src: str, base_dir: Path) -> Path | None:
    """Resolve a relative or absolute src to a local file path."""
    if not src or src.startswith('data:') or src.startswith('http'):
        return None

    parsed = urlparse(src)
    if parsed.scheme and parsed.scheme != 'file':
        return None

    # Handle file:// URIs
    if parsed.scheme == 'file':
        local = Path(unquote(parsed.path))
    else:
        local = base_dir / unquote(src)

    if local.is_file():
        return local
    return None


def file_to_data_uri(file_path: Path) -> str:
    """Convert a file to a base64 data URI string."""
    suffix = file_path.suffix.lower()
    mime = MIME_TYPES.get(suffix) or mimetypes.guess_type(str(file_path))[0] or 'application/octet-stream'

    data = file_path.read_bytes()
    b64 = base64.b64encode(data).decode('ascii')
    return f"data:{mime};base64,{b64}"


def inline_css_urls(css_text: str, base_dir: Path) -> tuple[str, int]:
    """Replace url(...) references in CSS text with data URIs.

    Returns (new_css_text, count_of_replacements).
    """
    count = 0

    def replace_url(match):
        nonlocal count
        url = match.group(1).strip('\'"')
        resolved = resolve_path(url, base_dir)
        if resolved:
            count += 1
            return f"url({file_to_data_uri(resolved)})"
        return match.group(0)

    result = re.sub(r'url\(([^)]+)\)', replace_url, css_text)
    return result, count


def inline_html(html_path: str, output_path: str | None = None) -> str:
    """Inline all local assets in an HTML file as base64 data URIs.

    Args:
        html_path: Path to the HTML file.
        output_path: Output path. If None, overwrites input.

    Returns:
        Path to the output file.
    """
    html_file = Path(html_path).resolve()
    base_dir = html_file.parent

    content = html_file.read_text(encoding='utf-8')
    soup = BeautifulSoup(content, 'lxml')

    img_count = 0
    css_count = 0

    # 1. Inline <img src="...">
    for img in soup.find_all('img'):
        src = img.get('src', '')
        resolved = resolve_path(src, base_dir)                      # type: ignore
        if resolved:
            img['src'] = file_to_data_uri(resolved)
            img_count += 1

    # 2. Inline <source src="..."> (for <picture> elements)
    for source in soup.find_all('source'):
        src = source.get('srcset', '') or source.get('src', '')
        resolved = resolve_path(src, base_dir)                      # type: ignore
        if resolved:
            if source.get('srcset'):
                source['srcset'] = file_to_data_uri(resolved)
            else:
                source['src'] = file_to_data_uri(resolved)
            img_count += 1

    # 3. Inline CSS url() in <style> blocks
    for style_tag in soup.find_all('style'):
        if style_tag.string:
            new_css, n = inline_css_urls(style_tag.string, base_dir)
            if n > 0:
                style_tag.string = new_css
                css_count += n

    # 4. Inline CSS url() in inline style attributes
    for el in soup.find_all(style=True):
        style_val = el['style']
        if 'url(' in style_val:
            new_style, n = inline_css_urls(style_val, base_dir)     # type: ignore
            if n > 0:
                el['style'] = new_style
                css_count += n

    # 5. Inline <link rel="icon" href="...">
    for link in soup.find_all('link', rel=lambda r: r and 'icon' in r):
        href = link.get('href', '')
        resolved = resolve_path(href, base_dir)                      # type: ignore
        if resolved:
            link['href'] = file_to_data_uri(resolved)
            img_count += 1

    out = Path(output_path) if output_path else html_file
    out.write_text(str(soup), encoding='utf-8')

    print(f"Inlined {img_count} image(s) and {css_count} CSS url() reference(s)")
    print(f"Output: {out}")
    return str(out)


def main():
    parser = argparse.ArgumentParser(
        description='Embed all local assets in an HTML file as base64 data URIs.',
    )
    parser.add_argument('html', help='Path to the HTML slide deck')
    parser.add_argument(
        '--output', '-o', default=None,
        help='Output path (default: overwrite input file)',
    )
    args = parser.parse_args()

    html_file = Path(args.html)
    if not html_file.exists():
        print(f"Error: {html_file} not found", file=sys.stderr)
        sys.exit(1)

    inline_html(str(html_file), args.output)


if __name__ == '__main__':
    main()
