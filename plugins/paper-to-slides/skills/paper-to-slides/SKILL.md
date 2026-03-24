---
name: paper-to-slides
description: Convert one or more academic papers (PDF, LaTeX, Overleaf project) into polished HTML presentations. Supports multiple papers in one deck, explicit language selection, screen-aware sizing for 4K displays, and style extraction from reference PPT/HTML templates. Outputs to a dedicated slides directory at the project root (never into the paper source directory). Delegates to frontend-slides for rendering and automatically runs overleaf-cleanup for LaTeX/zip/directory inputs.
allowed_tools: ["Bash", "Read", "Write", "Edit", "Glob", "Grep", "AskUserQuestion", "Agent", "Skill", "WebFetch"]
arguments:
  - name: paper_path
    description: "Path(s) to PDF files, .tex files, Overleaf zips, or project directories. Accepts multiple space-separated paths or glob patterns to combine several papers into one presentation."
    required: false
  - name: style
    description: "Presentation style: academic, popular-science, pitch, tutorial, or poster"
    required: false
  - name: language
    description: "Slide language: en, zh, ja, etc. If not provided, the user will be asked explicitly."
    required: false
  - name: template
    description: "Path to a reference PPT/PPTX/HTML file to extract style from. The template's visual design (colors, fonts, backgrounds, title/end page layout, narrative flow) will be analyzed and distilled into a reusable style template."
    required: false
---

# Paper to Slides

Convert one or more academic papers into a compelling HTML presentation. Reads each paper, extracts the narrative structure, adapts to the target audience, and produces a polished slide deck via the `frontend-slides` skill.

**Detailed reference material** (outline templates, CSS rules, OOXML transforms, fidelity checklists, etc.) is in [`REFERENCE.md`](./REFERENCE.md). Read it on-demand when a specific step requires it.

## Platform Compatibility

This skill works with **Claude Code CLI**, **OpenAI Codex CLI**, and other SKILL.md-compatible agents. Instructions use Claude Code tool names — see [`PLATFORM_COMPAT.md`](../../../../PLATFORM_COMPAT.md) for the full cross-platform tool mapping and script path resolution.

All script invocations below use `$SKILL_DIR` — set it once at the start of the session per the instructions in `PLATFORM_COMPAT.md`.

## When to Activate

- User says "turn this paper into slides", "make a presentation from my paper", "paper to PPT"
- User has a PDF, `.tex` file, Overleaf zip, or project directory and wants slides
- User wants to combine multiple papers into one presentation

## Usage

```
/paper-to-slides                                    # Interactive
/paper-to-slides paper.pdf                          # Single PDF
/paper-to-slides main.tex                           # Single LaTeX file
/paper-to-slides ./my-overleaf-project              # Overleaf directory
/paper-to-slides project.zip                        # Overleaf zip
/paper-to-slides paper.pdf academic                 # With style preset
/paper-to-slides paper1.pdf paper2.pdf              # Multiple papers → one deck
/paper-to-slides paper.pdf --template ref.pptx      # Use a PPTX as style reference
```

---

## Multimodal-First Philosophy

**Use your vision and semantic understanding over script-based heuristics.** If your platform supports multimodal input (Claude Code does natively; Codex via `view_image`):

- **Read PDFs visually**: Read PDF files directly to see figures, diagrams, tables, and layout that text extraction misses. *(Claude Code: `Read` tool with `pages` param. Codex: extract pages as images via `pdf2image`, then `view_image`.)*
- **Inspect figures directly**: View paper figures to decide which are worth including — don't just list filenames. *(Claude Code: `Read` on image files. Codex: `view_image`.)*
- **Visual QA on generated slides**: After generation, use `snapshot_slides.py` to take screenshots, then visually inspect slide quality, layout, typography, and figure placement.
- **Semantic comparison**: When merging supplements, read the content yourself and compare by meaning — not by string similarity scores.

Scripts (`extract_pdf.py`, `diff_supplement.py`) are **auxiliary tools** for data extraction and metadata. They should never be the primary decision-maker for content quality or similarity.

---

## Prerequisites

Verify at the start of every invocation. **Stop with actionable guidance** if anything is missing.

### Required Skills

| Skill | Purpose | Check | Invoke |
|-------|---------|-------|--------|
| `frontend-slides` | HTML slide generation | Verify skill file exists | Claude: `Skill("frontend-slides")` / Codex: `$frontend-slides` |
| `overleaf-cleanup` | LaTeX project cleanup | Only for `.zip`/`.tex`/directory inputs | Claude: `Skill("overleaf-cleanup")` / Codex: `$overleaf-cleanup` |

### Required Python Packages

| Package | Purpose | When Needed |
|---------|---------|-------------|
| `pdfplumber` | PDF text extraction (auxiliary) | PDF inputs with long docs |
| `python-pptx` | PPTX template analysis / export | Template extraction, PPTX export |
| `Pillow` | Image processing, OOXML transforms, PDF export | Template assets, PDF export |
| `lxml` | PPTX XML parsing | Template extraction |
| `pdf2image` | PDF figures → PNG (needs `poppler`) | PDF figure extraction |
| `matplotlib` | LaTeX math → PNG for PPTX | PPTX export with math |
| `beautifulsoup4` | HTML parsing for PPTX conversion | PPTX export |
| `playwright` | Headless slide screenshots + PDF export | Snapshots, visual QA, PDF export |

**Auto-install** missing packages on demand with `sys.executable -m pip install`.

Playwright also requires a one-time browser install:
```bash
python -m playwright install chromium
```

### System Dependencies

- **Python 3.8+**: `python --version`
- **Poppler**: Only needed for PDF figure conversion. Windows: `conda install -c conda-forge poppler`. Mac: `brew install poppler`. Linux: `apt install poppler-utils`.
- **Chromium** (via Playwright): Auto-installed by `snapshot_slides.py` on first run. Required for slide screenshots, visual QA, and PDF export.

---

## Workflow

### Phase A: Input & Extraction

#### Step 1: Locate the Paper(s)

`paper_path` accepts one or more paths. For each, determine type:
- **PDF** → extract text (Step 2)
- **LaTeX** → read source (Step 3)
- **Overleaf zip/directory** → **MUST invoke** the `overleaf-cleanup` skill first *(Claude Code: `Skill("overleaf-cleanup", "<path>")`; Codex: `$overleaf-cleanup <path>`)*, then parse cleaned `.tex` (Step 3)
- **Not provided** → Ask the user for path(s), search CWD for candidates

#### Step 2: Extract Content from PDF

**Primary approach — read the PDF directly.** You are the primary reader — form your own understanding of the paper's structure, arguments, and contributions.

**Claude Code** — use the `Read` tool with `pages` parameter (gives both text and visual content):
```
Read(file_path="paper.pdf", pages="1-20")   # first 20 pages (you see both text AND images)
Read(file_path="paper.pdf", pages="21-40")  # next batch
```

**Codex** — extract text via shell, view figures as images:
```bash
python -c "
import pdfplumber
with pdfplumber.open('paper.pdf') as pdf:
    for p in pdf.pages[:20]:
        print(p.extract_text() or '')
"
```

Read in batches of 20 pages. **Visual reading advantages** (when platform supports multimodal):
- See figures/diagrams in context (text extraction loses these entirely)
- Understand table layouts and complex formatting
- Identify which figures are high-value for slides
- Spot equations that should be preserved as-is vs. simplified

**Auxiliary script** — for long PDFs (>40 pages) where you need metadata before deciding what to read:

```bash
PDF_SCRIPT="$SKILL_DIR/extract_pdf.py"
python "$PDF_SCRIPT" "<pdf_path>" --output-dir "<output_dir>"
```

The script produces `<output_dir>/_pdf_cache/` with:

| File | Purpose |
|------|---------|
| `metadata.json` | Page count, classification breakdown, title/abstract guess |
| `index.json` | Section → chunk → page mapping, figure page list |
| `chunk_001.txt` ... | Raw text per chunk (15-20 pages each) |

**Use the script only for:**
- Quick page count and classification breakdown (for Step 4b question)
- Identifying figure-heavy pages (for Step 10)
- Locating specific sections in very long papers

**Do NOT rely on the script's page classifications as ground truth.** Its heuristics (text density thresholds, keyword matching) can misclassify pages. Always verify by reading the actual content yourself.

> **Cleanup**: Delete `_pdf_cache/` after slide generation is finalized (Step 13).

#### Step 3: Extract Content from LaTeX

1. Invoke `overleaf-cleanup` skill for zip/directory inputs (mandatory).
2. Identify main `.tex` file, read it and all `\input`/`\include`'d files.
3. Parse structure: `\title`, `\author`, `\abstract`, `\section`, `\begin{figure}`, etc.
4. Extract figure file paths.

#### Step 4: Analyze Paper Structure

**You are the semantic analyst.** Read the paper content from Step 2/3 and extract:

- Title & authors, abstract, problem statement
- Key contributions (what's novel)
- Method overview (how it works, not surface-level keywords)
- Key results (specific numbers, comparisons, significance)
- Figures/tables worth including
- Conclusion and implications

**Semantic understanding is critical here.** Do not just extract keywords or section headings — understand the paper's narrative arc, what problem it solves, why the approach works, and what the results mean. This understanding drives slide quality.

For PDF inputs, read the actual text from Step 2. If you need more detail on a specific section, re-read those pages directly. The extraction script's metadata is only for navigation, not for understanding.

When multiple papers provided, extract from **each** separately and label with identifiers.

> **Multi-paper merging**: See `REFERENCE.md → Multi-Paper Merge Guidelines` for terminology collision, notation conflict, and attribution rules.

---

### Phase B: User Preferences

#### Step 4b: Page Limits per Paper

Ask per paper using the metadata from Step 2a/2b:

```
Question: "How many pages should I read from '<filename>'? (Total: <N> pages, ~<M> content / ~<R> references / ~<A> appendix)"
Options:
  - "Main body only (auto-detect)" — "Skip references and appendix pages. Recommended."
  - "All pages" — "Read everything including appendices (chunked for long PDFs)"
  - "First <N/2> pages" — "Read only the first half"
  - "Let me specify sections" — "I'll tell you which page ranges or sections to focus on"
```

The page classification from Step 2b makes this question informative — the user sees the breakdown before deciding. For LaTeX inputs, estimate from content sections instead.

#### Step 5: Choose Slide Language

**Must be explicitly confirmed.** Never assume. Options: English, 中文, Same as paper.

When non-English: translate all text, keep technical acronyms, use CJK fonts, set `lang` attribute.

#### Step 6: Choose Presentation Style

**Must be confirmed.** Options: Academic, Popular science, Pitch, Tutorial.

> See `REFERENCE.md → Style Presets` for slide count, density, tone, and audience adaptation examples per style.

#### Step 7: Style Template

Always ask for a reference template unless `template` argument was provided.

##### Template Analysis — 100% Fidelity Rule

When a template is available, its visual assets **MUST be used with 100% fidelity** — backgrounds, logos, colors, fonts, aspect ratio.

> See `REFERENCE.md → Template Fidelity Requirements` for the full element-by-element checklist and common mistakes.

**For PPTX templates** — run the persisted extraction script:

```bash
EXTRACT_SCRIPT="$SKILL_DIR/extract_pptx_template.py"
python "$EXTRACT_SCRIPT" "<pptx_path>" --output-dir "<output_dir>/assets"
```

The script extracts images (with OOXML transform handling), theme colors, fonts, decorative shapes, and produces `style_report.json`.

> **OOXML Image Transforms**: The script auto-detects `<a:grayscl/>`, `<a:duotone>`, etc. and applies Pillow equivalents. See `REFERENCE.md → OOXML Image Transforms` for details and manual fallback.

**For HTML templates**: Extract CSS properties, fonts, colors, layout, background images, logos.

**Distill into `_style_template.html`**: A `<style>` block with CSS variables/fonts/backgrounds, 3 skeleton slides (title, content, end), logo positioned via CSS, and background images via `assets/`.

#### Step 7a: Aspect Ratio Inference + Dual Version Offer

Read `aspect_ratio_label` from `style_report.json`. Offer to generate the other ratio version.

> See `REFERENCE.md → CSS Transformation Rules` for the 16:9 ↔ 4:3 conversion table.

**Naming**: Primary = `slides.html`, secondary = `slides_{ratio}.html` (e.g., `slides_4_3.html`).

#### Step 7c: Single-File Output (Must Ask)

**Always ask this question.** The original HTML with assets is always kept; this only controls whether an additional self-contained copy is generated.

```
Question: "Would you also like a single-file HTML version (all images embedded, easy to share)?"
Options:
  - "Yes, generate single-file version (Recommended)" — "Creates slides_single.html with all assets inlined as base64. The original slides.html + assets/ folder is kept as-is."
  - "No, just the original" — "Only output slides.html with the assets/ folder."
```

If **yes**: after generating the primary `slides.html` (with assets/ folder), produce an additional `slides_single.html` by running `inline_assets.py`:

```bash
INLINE_SCRIPT="$SKILL_DIR/inline_assets.py"
python "$INLINE_SCRIPT" "<slides.html>" --output "<slides_single.html>"
```

For dual aspect ratio versions, also produce `slides_4_3_single.html` etc.

**Output naming**: `{original_stem}_single.html` — never overwrite the original.

**Important — export tools must always use the original HTML:**
- PPTX export (`html_to_pptx.py`, `html_slides_to_pptx.py`) → use `slides.html` (not `_single`)
- PDF export (`snapshot_slides.py`) → use `slides.html` (not `_single`)
- The `_single.html` files are **for sharing/viewing only** — they contain bloated base64 data that slows down Playwright rendering and parsing. Always point export tools at the original HTML + `assets/` folder.

If **no**: skip. The original `slides.html` + `assets/` is the only output.

#### Step 7b: Organization Logo Auto-Detection & Injection

Ask: "Auto-detect from template", "I'll provide a logo file", or "No logo needed".

**Two approaches:**

##### Approach A: Semantic placement (preferred)

Include logo in the HTML generation prompt to `frontend-slides`. Provide guidelines per slide type:
- **Content slides**: header bar region, proportional sizing
- **Title/end slides**: visually balanced, may differ from content slides
- **Section dividers**: subtle corner placement
- **Figure-heavy slides**: smaller size, avoid overlap

Always use the **original logo image** — never apply CSS filters that alter colors.

> **Lesson learned**: Do NOT use `filter: brightness(0) invert(1)` on logos — destroys colored logos.

##### Approach B: Batch injection (fallback for existing slides)

```bash
LOGO_SCRIPT="$SKILL_DIR/inject_logo.py"
python "$LOGO_SCRIPT" <slides.html> <logo.png> --alt-text "Org Name"
```

Idempotent, supports `--position` (top-right/top-left/bottom-right/bottom-left).

---

### Phase C: Setup & Planning

#### Step 8: Establish Output Directory

**Never write into the paper's source directory.** Create `<project_root>/slides_<slug>/` with `assets/` subdirectory.

Naming: single paper → `slides_<paper_name>`, multiple → `slides_<combined_name>`. Sanitize: lowercase, `_` for spaces, max 40 chars.

#### Step 9: Generate Slide Outline

Create a structured outline and present for approval. For multi-paper decks, ask organization strategy: Sequential, Interleaved by theme, or Comparative.

> See `REFERENCE.md → Slide Outline Templates` for per-style outline structures and `Multi-Paper Merge Guidelines` for the pre-generation checklist.

#### Step 10: Handle Figures

**View figures directly** — don't just list filenames. *(Claude Code: `Read` tool on image files. Codex: `view_image` or describe from filename/context.)*

- **LaTeX inputs**: Visually inspect each candidate figure file. Assess which figures communicate key results and are worth including. Copy selected figures to `assets/`.
- **PDF inputs**: You already saw figures when reading PDF pages in Step 2. For high-value figures, either:
  - Ask the user to extract them (provide page numbers and descriptions from your visual reading)
  - Use `pdf2image` to extract specific pages as PNGs for figure-heavy pages
- **Template assets**: If the template has decorative images, view them to verify quality and relevance.

Present your visual assessment to the user: "Figure 3 (page 8) shows the architecture diagram — worth including on the methods slide. Figure 5 (page 12) is a bar chart comparing baselines — key for the results slide."

---

### Phase D: Generation & Review

#### Step 11: Detect Screen Resolution

```bash
SCREEN_SCRIPT="$SKILL_DIR/detect_screen.py"
python "$SCREEN_SCRIPT"
```

If `css_recommendation` is `"boost"` (HiDPI/4K): increase CSS `clamp()` upper bounds ~50%, add `@media (min-width: 2500px)` breakpoint. If `"default"`: use standard values.

#### Step 12: Generate Slides via frontend-slides

Invoke the `frontend-slides` skill *(Claude Code: `Skill("frontend-slides", ...)`; Codex: `$frontend-slides ...`)* with: structured slide content (type, heading, body, figure, notes per slide), style direction, language, screen resolution, `_style_template.html`, and logo info from Step 7b.

#### Step 12b: Generate Dual Aspect Ratio Version

If dual version requested in Step 7a:
1. Primary already generated as `slides.html`.
2. Copy to `slides_{ratio}.html`, apply CSS transformations (see `REFERENCE.md → CSS Transformation Rules`).
3. Open both in browser for comparison.

#### Step 13: Post-Generation & Review

**Visual QA before asking the user.** Take screenshots and inspect them yourself:

1. Run `snapshot_slides.py` to capture all slides as images.
2. View the screenshot files to visually inspect *(Claude Code: `Read` tool. Codex: `view_image`)*:
   - Layout and typography — are titles readable? Is text overflowing?
   - Figure placement — are images properly sized and positioned?
   - Color and contrast — do backgrounds and text work together?
   - Consistency — do all slides follow the same visual language?
3. Fix obvious issues (CSS tweaks, content overflow) before showing to the user.

Then open in browser. Ask: "Great, done!" / "Adjust content" / "Adjust style" / "Both". Iterate.

#### Step 13c: Space Usage Optimization

Audit and fix slides that use too little vertical space (common with few bullet points).

**Workflow:**

1. **Audit** — Run `audit_space.py` on the primary HTML:

```bash
AUDIT_SCRIPT="$SKILL_DIR/audit_space.py"
python "$AUDIT_SCRIPT" "<slides.html>" --threshold 0.55
```

Report and screenshots are saved to `_space_audit/` next to the HTML file.

2. **Visual Review** — If any slides are flagged, view each screenshot in `_space_audit/` to visually assess the layout.

3. **Determine Fix** — Use this lookup table:

| Symptom | Fix |
|---------|-----|
| 1-3 bullets, fill < 45% | Increase `--body-size` clamp floor by 0.2-0.4rem |
| All content slides 45-55% | Increase `line-height` on `ul` (1.65 → 1.9) |
| `li` items too cramped | Increase `margin-bottom` on `li` (0.45em → 0.65em) |
| `slide-figure` low fill | Increase `max-height` on `.fig-panel img` |

4. **Apply** — Edit CSS in `<style>` block. Prefer global `:root` changes when multiple slides flagged. Apply same delta to dual-version HTML.

5. **Re-audit** — Run `audit_space.py` again to verify improvement (max 2 passes).

6. **Cleanup** — Remove `_space_audit/` directory after optimization is complete:

```python
import shutil; shutil.rmtree('_space_audit/')
```

#### Step 13b: Snapshot Slides (Optional)

Capture high-resolution screenshots of each slide for review/sharing:

```bash
SNAP_SCRIPT="$SKILL_DIR/snapshot_slides.py"

# Default: 2x scale, auto-detect aspect ratio
python "$SNAP_SCRIPT" "<slides.html>" --output-dir "<output_dir>/snapshots"

# 4:3 slides at 3x resolution
python "$SNAP_SCRIPT" "<slides_4_3.html>" --output-dir "<output_dir>/snapshots_4_3" --scale 3

# Specific slides only
python "$SNAP_SCRIPT" "<slides.html>" --output-dir "<output_dir>/snapshots" --slides 5-24
```

The script runs headless Chromium, hides progress bars and navigation overlays, and outputs `slide_001.png`, `slide_002.png`, etc. Viewport auto-selects 1920×1080 (16:9) or 1440×1080 (4:3) based on slide CSS.

#### Step 14: Export (Required Ask)

**Always ask** the export format:

```
Question: "Which export format(s) do you need?"
Options:
  - "PPTX only" — "PowerPoint file for editing and presenting"
  - "PDF only" — "Fixed-layout document for sharing and printing"
  - "Both PPTX and PDF" — "PowerPoint for editing + PDF for distribution"
  - "No export needed" — "Keep HTML only"
```

##### PPTX Export

```bash
EXPORT_SCRIPT="$SKILL_DIR/html_to_pptx.py"
python "$EXPORT_SCRIPT" "<slides.html>" --output "<slides.pptx>" --style-report "<style_report.json>"
```

For dual versions, export each separately. Use `--width 10 --height 7.5` for 4:3, defaults for 16:9.

> See `REFERENCE.md → PPTX Export Notes` for math rendering, figure scaling, and known limitations.

##### PDF Export

Use the snapshot script to produce high-resolution slide images, then combine into a PDF:

```bash
SNAP_SCRIPT="$SKILL_DIR/snapshot_slides.py"
python "$SNAP_SCRIPT" "<slides.html>" --output-dir "<output_dir>/pdf_frames" --scale 2 --format png
```

Then combine the PNGs into a single PDF using Pillow:

```python
from PIL import Image
from pathlib import Path

frames = sorted(Path("<output_dir>/pdf_frames").glob("slide_*.png"))
images = [Image.open(f).convert("RGB") for f in frames]
images[0].save("<slides.pdf>", save_all=True, append_images=images[1:], resolution=150)
```

For dual versions, export each separately.

#### Step 15: Supplemental Materials Merge

**You are the semantic judge.** Do NOT rely on the diff script's string-similarity scores to decide what's new vs. existing.

##### Recommended approach (semantic):

1. **Extract content** from both existing slides and supplements:

```bash
DIFF_SCRIPT="$SKILL_DIR/diff_supplement.py"
python "$DIFF_SCRIPT" "<slides.html>" <supplements...> --extract-only -o "<content.json>"
```

2. **Read the extracted content** yourself. For each supplement section, determine:
   - **Same topic, same depth** → unchanged (skip)
   - **Same topic, new details or different angle** → update candidate (ask user)
   - **Genuinely new topic not covered** → new section (ask to append)

3. **Present your semantic assessment** to the user with specific reasoning, not just similarity scores.

##### Auxiliary syntactic hint (optional):

If you want a rough starting point, run without `--extract-only` — but treat the SequenceMatcher scores as unreliable hints. Content with different wording about the same topic often scores below 0.6 and gets misclassified as "new".

Apply to all versions. Re-export if needed.

---

## Important Notes

- **Never dump raw paper text onto slides.** Distill and restructure for the audience.
- **One idea per slide.** Academic papers are dense; slides should not be.
- **Figures over text.** Use the paper's figures where possible.
- **Speaker notes**: Include detailed notes for the presenter — paper detail goes here, not on the slide face.
- **Math**: Include MathJax/KaTeX CDN. Simplify for non-academic styles.
- **Citations**: Academic style includes key citations. Other styles: omit or use a "References" end slide.

## Persisted Python Scripts

All scripts live in the same directory as this SKILL.md (on Claude Code: `~/.claude/skills/paper-to-slides/`). Set `SKILL_DIR` once per session (see Platform Compatibility above), then run directly — do NOT copy into the project.

| Script | Purpose | Usage |
|--------|---------|-------|
| `extract_pdf.py` | **Auxiliary.** Chunked PDF extraction for metadata/navigation on long PDFs. Prefer reading PDFs directly via Read tool. | `python ... <pdf> -o <dir> [--scope main-body\|all\|pages] [--pages 1-50]` |
| `detect_screen.py` | Screen resolution & DPI detection | `python "$SKILL_DIR/detect_screen.py"` |
| `extract_pptx_template.py` | PPTX asset extraction with OOXML transforms | `python ... <pptx> -o <dir>` |
| `html_to_pptx.py` | HTML → PPTX export with math/figure handling | `python ... <html> --output <pptx> [--style-report <json>]` |
| `inject_logo.py` | Batch logo injection (CSS + elements) | `python ... <slides.html> <logo.png> [--position top-right]` |
| `diff_supplement.py` | **Auxiliary.** Content extraction (--extract-only) for LLM semantic comparison. Legacy syntactic diff available but unreliable. | `python ... <slides.html> <supp...> --extract-only -o <content.json>` |
| `audit_space.py` | DOM-based content fill audit, flags sparse slides, captures screenshots to `_space_audit/` | `python ... <slides.html> [--threshold 0.55] [--no-screenshots] [--slides 1-5,8]` |
| `snapshot_slides.py` | Headless slide screenshots (Playwright) | `python ... <slides.html> -o <dir> [--scale 2] [--slides 1-5,8]` |
| `inline_assets.py` | Embed images/CSS as base64 for single-file HTML | `python ... <slides.html> [-o <standalone.html>]` |

## Execution Procedure

0. **Preflight** — verify Python, required skills, input-dependent dependencies
1. **Locate** paper(s) — determine input types (Step 1)
2. **Read the paper** — read PDF pages directly for semantic understanding; use extraction script only for metadata on long PDFs (Step 2)
3. **Ask page limits** — show page breakdown, get user's scope choice (Step 4b)
4. **Semantic analysis** — understand the paper's narrative, contributions, and results yourself (Step 4)
5. **Gather preferences** — language, style, template (Steps 5–7)
6. **Aspect ratio** — infer from template, offer dual version (Step 7a)
7. **Ask single-file** — must ask whether to also generate `_single.html` version (Step 7c)
8. **Logo detection** — auto-detect or manual logo (Step 7b)
9. **Create output directory** at project root (Step 8)
10. **Generate outline** — for multi-paper, choose organization strategy (Step 9)
11. **Handle figures** — copy to `assets/`, flag figure pages (Step 10)
12. **Detect screen** resolution (Step 11)
13. **Generate slides** via `frontend-slides` — include logo if confirmed (Step 12)
14. **Dual version** — generate secondary ratio if requested (Step 12b)
14b. **Logo fallback** — if not embedded during generation, run `inject_logo.py` (Step 7b Approach B)
15. **Preview and iterate** (Step 13)
15a. **Space usage optimization** — audit fill ratios, fix sparse slides, cleanup (Step 13c)
15b. **Snapshot slides** — optional headless screenshots for review (Step 13b)
16. **Single-file version** — if requested in step 7, run `inline_assets.py` to produce `slides_single.html` (Step 7c)
17. **Ask export format** — PPTX, PDF, both, or none (Step 14)
18. **Supplemental materials** — extract content, semantically compare yourself, merge if needed (Step 15)
