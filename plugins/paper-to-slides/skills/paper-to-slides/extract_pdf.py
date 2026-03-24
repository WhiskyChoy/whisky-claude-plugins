#!/usr/bin/env python3
"""
extract_pdf.py — Chunked PDF extraction with block cache and link table.

Extracts text from PDFs in manageable chunks, classifies pages by type,
builds a section-indexed cache for targeted re-reads by downstream steps.

Usage:
    python extract_pdf.py paper.pdf --output-dir slides_out
    python extract_pdf.py paper.pdf --output-dir slides_out --scope main-body
    python extract_pdf.py paper.pdf --output-dir slides_out --scope pages --pages 1-50
    python extract_pdf.py paper.pdf --output-dir slides_out --chunk-size 20

Output:
    <output_dir>/_pdf_cache/
        chunk_001.txt      # Raw text for pages 1-20
        chunk_002.txt      # Raw text for pages 21-40
        ...
        index.json         # Link table: sections → chunks → pages
        metadata.json      # Quick summary (page count, classifications)
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path


def ensure_pdfplumber():
    """Import pdfplumber, installing if missing."""
    try:
        import pdfplumber           # type: ignore[import]  # pdfplumber does not have type hints
        return pdfplumber
    except ImportError:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "pdfplumber"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        import pdfplumber           # type: ignore[import]  # pdfplumber does not have type hints
        return pdfplumber


# ---------------------------------------------------------------------------
# Data classes (immutable where possible)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PageInfo:
    """Classification result for a single page."""
    page_num: int          # 1-indexed
    char_count: int
    classification: str    # content | reference | appendix | figure | front_matter
    headings: tuple        # detected section headings on this page
    has_figures: bool       # low text density suggests figure-dominant page


@dataclass
class ChunkRecord:
    """Metadata for one cached chunk."""
    chunk_id: str
    pages: str              # e.g. "1-20"
    page_start: int
    page_end: int
    sections: list[str]
    file: str               # relative path within _pdf_cache/
    classifications: list[str]
    figure_pages: list[int]
    char_count: int


@dataclass
class ExtractionResult:
    """Top-level result returned / written to metadata.json."""
    source: str
    total_pages: int
    scope_applied: str
    pages_extracted: int
    chunks: list[ChunkRecord] = field(default_factory=list)
    page_classifications: dict = field(default_factory=dict)  # page_num → classification
    title_guess: str = ""
    authors_guess: str = ""
    abstract_snippet: str = ""


# ---------------------------------------------------------------------------
# Page classification
# ---------------------------------------------------------------------------

_REF_PATTERNS = re.compile(
    r"(?:^references$|^bibliography$|^\[\d+\]|\\bibitem)",
    re.IGNORECASE | re.MULTILINE,
)
_APPENDIX_PATTERNS = re.compile(
    r"(?:^appendix\b|^supplementary\s+material)",
    re.IGNORECASE | re.MULTILINE,
)
_HEADING_PATTERN = re.compile(
    r"^(?:\d+\.?\s+)?[A-Z\u4e00-\u9fff].{2,80}$",
    re.MULTILINE,
)
_FRONT_MATTER_KEYWORDS = {"abstract", "keywords", "introduction"}

FIGURE_CHAR_THRESHOLD = 200


def classify_page(page_num: int, text: str, prev_class: str) -> PageInfo:
    """Classify a single page based on text content."""
    char_count = len(text.strip())
    headings = tuple(m.group().strip() for m in _HEADING_PATTERN.finditer(text))

    # Figure-dominant: very low text
    if char_count < FIGURE_CHAR_THRESHOLD:
        return PageInfo(page_num, char_count, "figure", headings, True)

    # Reference section
    ref_matches = len(_REF_PATTERNS.findall(text))
    if ref_matches >= 3 or (prev_class == "reference" and ref_matches >= 1):
        return PageInfo(page_num, char_count, "reference", headings, False)

    # Appendix
    if _APPENDIX_PATTERNS.search(text) or prev_class == "appendix":
        return PageInfo(page_num, char_count, "appendix", headings, False)

    # Front matter (first few pages with abstract/keywords)
    if page_num <= 3:
        lower = text.lower()
        if any(kw in lower for kw in _FRONT_MATTER_KEYWORDS):
            return PageInfo(page_num, char_count, "front_matter", headings, False)

    return PageInfo(page_num, char_count, "content", headings, False)


def classify_all_pages(pdf) -> list[PageInfo]:
    """Classify every page in the PDF."""
    results = []
    prev_class = "content"
    for i, page in enumerate(pdf.pages):
        text = page.extract_text() or ""
        info = classify_page(i + 1, text, prev_class)
        results.append(info)
        prev_class = info.classification
    return results


# ---------------------------------------------------------------------------
# Metadata extraction (title, authors, abstract from first pages)
# ---------------------------------------------------------------------------

def extract_metadata(pdf, page_infos: list[PageInfo]) -> dict:
    """Best-effort title, authors, abstract from first 3 pages."""
    first_pages_text = []
    for i in range(min(3, len(pdf.pages))):
        first_pages_text.append(pdf.pages[i].extract_text() or "")
    combined = "\n".join(first_pages_text)

    # Title: typically the first prominent line
    lines = [l.strip() for l in combined.split("\n") if l.strip()]
    title_guess = lines[0] if lines else ""

    # Abstract: text between "abstract" and first section heading
    abstract_snippet = ""
    abs_match = re.search(
        r"abstract[:\s]*\n?(.*?)(?:\n\d+\.?\s+[A-Z]|\nIntroduction|\nKeywords)",
        combined,
        re.IGNORECASE | re.DOTALL,
    )
    if abs_match:
        abstract_snippet = abs_match.group(1).strip()[:500]

    return {
        "title_guess": title_guess,
        "authors_guess": "",  # Hard to extract reliably; leave for LLM
        "abstract_snippet": abstract_snippet,
    }


# ---------------------------------------------------------------------------
# Scope filtering
# ---------------------------------------------------------------------------

def filter_pages_by_scope(
    page_infos: list[PageInfo],
    scope: str,
    page_range: str | None = None,
) -> list[int]:
    """Return 1-indexed page numbers to extract based on scope."""
    if scope == "all":
        return [p.page_num for p in page_infos]

    if scope == "main-body":
        return [
            p.page_num
            for p in page_infos
            if p.classification in ("content", "front_matter", "figure")
        ]

    if scope == "pages" and page_range:
        selected = set()    # type: set[int]
        for part in page_range.split(","):
            part = part.strip()
            if "-" in part:
                start, end = part.split("-", 1)
                selected.update(range(int(start), int(end) + 1))
            else:
                selected.add(int(part))
        return sorted(p for p in selected if 1 <= p <= len(page_infos))

    # Default: main-body
    return filter_pages_by_scope(page_infos, "main-body")


# ---------------------------------------------------------------------------
# Chunked extraction
# ---------------------------------------------------------------------------

def extract_chunks(
    pdf,
    pages_to_extract: list[int],
    cache_dir: Path,
    chunk_size: int = 20,
) -> list[ChunkRecord]:
    """Extract text in chunks, save to cache files, return chunk records."""
    cache_dir.mkdir(parents=True, exist_ok=True)

    chunks = []
    page_idx = 0
    chunk_num = 0

    while page_idx < len(pages_to_extract):
        chunk_num += 1
        chunk_pages = pages_to_extract[page_idx : page_idx + chunk_size]
        page_idx += chunk_size

        chunk_id = f"chunk_{chunk_num:03d}"
        chunk_file = f"{chunk_id}.txt"
        chunk_path = cache_dir / chunk_file

        text_parts = []
        sections = []
        classifications = set()         # type: set[str]
        figure_pages = []
        total_chars = 0

        for pg in chunk_pages:
            page = pdf.pages[pg - 1]  # 0-indexed
            text = page.extract_text() or ""
            text_parts.append(f"--- PAGE {pg} ---\n{text}")
            total_chars += len(text)

            # Collect headings as sections
            for m in _HEADING_PATTERN.finditer(text):
                heading = m.group().strip()
                if len(heading) > 3:
                    sections.append(heading)

            if len(text.strip()) < FIGURE_CHAR_THRESHOLD:
                figure_pages.append(pg)

        chunk_path.write_text("\n\n".join(text_parts), encoding="utf-8")

        page_range_str = (
            f"{chunk_pages[0]}-{chunk_pages[-1]}"
            if len(chunk_pages) > 1
            else str(chunk_pages[0])
        )

        chunks.append(
            ChunkRecord(
                chunk_id=chunk_id,
                pages=page_range_str,
                page_start=chunk_pages[0],
                page_end=chunk_pages[-1],
                sections=sections[:20],  # cap to avoid huge lists
                file=f"_pdf_cache/{chunk_file}",
                classifications=sorted(classifications),
                figure_pages=figure_pages,
                char_count=total_chars,
            )
        )

    return chunks


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run(
    pdf_path: str,
    output_dir: str,
    scope: str = "main-body",
    page_range: str | None = None,
    chunk_size: int = 20,
) -> ExtractionResult:
    """Full extraction pipeline. Returns result and writes cache + index."""
    pdfplumber = ensure_pdfplumber()
    pdf_file = Path(pdf_path)
    out = Path(output_dir)
    cache_dir = out / "_pdf_cache"

    with pdfplumber.open(pdf_file) as pdf:
        total_pages = len(pdf.pages)

        # 1. Classify all pages
        page_infos = classify_all_pages(pdf)

        # 2. Extract metadata from first pages
        meta = extract_metadata(pdf, page_infos)

        # 3. Filter by scope
        pages_to_extract = filter_pages_by_scope(page_infos, scope, page_range)

        # 4. Chunked extraction with cache
        chunks = extract_chunks(pdf, pages_to_extract, cache_dir, chunk_size)

    # Build classification summary
    class_counts = {}           # type: dict[str, int]
    page_classifications = {}
    for p in page_infos:
        class_counts[p.classification] = class_counts.get(p.classification, 0) + 1
        page_classifications[p.page_num] = p.classification

    result = ExtractionResult(
        source=str(pdf_file),
        total_pages=total_pages,
        scope_applied=scope,
        pages_extracted=len(pages_to_extract),
        chunks=chunks,
        page_classifications=page_classifications,
        title_guess=meta["title_guess"],
        authors_guess=meta["authors_guess"],
        abstract_snippet=meta["abstract_snippet"],
    )

    # Write index.json
    index_data = {
        "source": result.source,
        "total_pages": result.total_pages,
        "scope_applied": result.scope_applied,
        "pages_extracted": result.pages_extracted,
        "title_guess": result.title_guess,
        "abstract_snippet": result.abstract_snippet,
        "classification_summary": class_counts,
        "figure_pages": [
            p.page_num for p in page_infos if p.classification == "figure"
        ],
        "chunks": [asdict(c) for c in chunks],
    }
    index_path = cache_dir / "index.json"
    index_path.write_text(json.dumps(index_data, indent=2, ensure_ascii=False), encoding="utf-8")

    # Write metadata.json (quick summary for the LLM to read)
    metadata = {
        "source": str(pdf_file.name),
        "total_pages": total_pages,
        "scope_applied": scope,
        "pages_extracted": len(pages_to_extract),
        "classification_summary": class_counts,
        "figure_pages": index_data["figure_pages"],
        "title_guess": result.title_guess,
        "abstract_snippet": result.abstract_snippet[:300],
        "chunk_count": len(chunks),
        "is_long_pdf": total_pages > 30,
    }
    meta_path = cache_dir / "metadata.json"
    meta_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")

    return result


def main():
    parser = argparse.ArgumentParser(
        description="Chunked PDF extraction with block cache and link table."
    )
    parser.add_argument("pdf_path", help="Path to the PDF file")
    parser.add_argument(
        "--output-dir", "-o", required=True,
        help="Output directory (will create _pdf_cache/ inside)"
    )
    parser.add_argument(
        "--scope", choices=["all", "main-body", "pages"], default="main-body",
        help="Extraction scope: all, main-body (skip refs/appendix), or pages"
    )
    parser.add_argument(
        "--pages", default=None,
        help="Page range when --scope=pages (e.g., '1-50' or '1-30,45-60')"
    )
    parser.add_argument(
        "--chunk-size", type=int, default=20,
        help="Pages per chunk (default: 20)"
    )

    args = parser.parse_args()
    result = run(
        pdf_path=args.pdf_path,
        output_dir=args.output_dir,
        scope=args.scope,
        page_range=args.pages,
        chunk_size=args.chunk_size,
    )

    # Print summary to stdout
    class_summary = {}
    for p_class in result.page_classifications.values():
        class_summary[p_class] = class_summary.get(p_class, 0) + 1

    print(json.dumps({
        "source": result.source,
        "total_pages": result.total_pages,
        "pages_extracted": result.pages_extracted,
        "chunks_created": len(result.chunks),
        "classification_summary": class_summary,
        "figure_pages": [
            pg for pg, cls in result.page_classifications.items()
            if cls == "figure"
        ],
        "title_guess": result.title_guess,
        "abstract_snippet": result.abstract_snippet[:200],
        "cache_dir": str(Path(args.output_dir) / "_pdf_cache"),
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
