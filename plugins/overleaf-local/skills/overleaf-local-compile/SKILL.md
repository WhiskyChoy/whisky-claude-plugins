---
name: overleaf-local-compile
description: Run the LaTeX compile-fix loop — two-pass strategy (structural issues first, then per-page local fixes) with a prioritized fix ladder that prefers layout tricks over text modification. Invocable as /overleaf-local:overleaf-local-compile (Claude Code) or $overleaf-local-compile (Codex).
user-invocable: true
---

# Compile-Fix Loop

Two passes: structural (whole-document), then local (per-page). Maximum iteration limit: 20 (configurable).

## Pre-Compile: File Dependency Map

If `\input{}`, `\include{}`, or `\subfile{}` commands exist, recursively scan from the main `.tex` entry point and build an in-memory tree. This maps log line numbers back to correct source files. Track file stack using `(./path.tex` enter / `)` leave markers in the log.

Skip for single-file projects with no `\input` commands.

## Pre-Compile: Lesson Lookup

Load lessons from:
1. `<project>/.claude/latex-lessons/*.md` (project-level, higher priority)
2. `~/.claude/latex-lessons/*.md` (user-level, fallback)

Index by `trigger` and `pattern` fields for fast matching against log output.

## Pass 1 — Structural

**Goal:** Resolve all errors and stabilize document structure before local fixes.

```
Step 1: Compile (full build: engine → bib → engine → engine)
Step 2: Parse log → classify issues

IF errors exist:
    Fix in priority order:
    1. Missing packages → install via tlmgr/mpm, recompile
    2. Undefined control sequences → check typos, missing \usepackage
    3. Missing files → check paths, \graphicspath
    4. Syntax errors → fix LaTeX syntax
    Recompile, repeat until no errors

IF float warnings exist:
    Analyze all floats globally:
    - Map each float to declared position vs actual placement
    - Identify floats that drifted far from their \ref
    - Adjust specifiers ([htbp] → [!htbp], [H] with float package)
    - Consider \clearpage at section boundaries if float backlog builds
    Recompile, verify float placement stabilized

EXIT Pass 1 when: zero errors, float placement stable (same across two consecutive compiles)
```

## Pass 2 — Local (Per-Page/Per-Region)

**Goal:** Eliminate all overfull/underfull hbox/vbox warnings.

```
Step 1: Parse log for remaining warnings
Step 2: Group warnings by source file and line region
Step 3: For each warning group:
    a. Check lessons database for matching pattern
       → High-confidence match: apply lesson fix directly
    b. No lesson match: walk the fix ladder (below)
    c. If parallel mode enabled:
       → Spawn subagents to trial top 2-3 candidate fixes
       → Pick the fix producing fewest remaining warnings
    d. If parallel mode disabled:
       → Try fixes sequentially, stop at first that resolves the warning
Step 4: Recompile
Step 5: Re-parse → if new warnings appeared (cascade), repeat from Step 1
Step 6: Exit when zero warnings

SAFETY: Cycle detection — track warning hash sets. If a previous state recurs, stop.
```

## Fix Ladder — Overfull Hbox

Applied in priority order (cheapest/safest first):

| # | Fix | Scope | Risk | Technique |
|---|-----|-------|------|-----------|
| 1 | URL/path line breaking | Word | None | `\usepackage[hyphens]{url}`, `\url{}` wrapping |
| 2 | Hyphenation hints | Word | None | `\-` manual hyphenation, `\allowbreak` |
| 3 | Sloppy paragraph | Paragraph | Low | `\begin{sloppypar}...\end{sloppypar}` |
| 4 | Emergency stretch | Paragraph | Low | `{\emergencystretch=1em ...}` scoped |
| 5 | Looseness adjustment | Paragraph | Low-Med | `\looseness=-1` to reflow one fewer line |
| 6 | Tolerance tuning | Paragraph | Low | Local `\tolerance=200` / `\hbadness=200` |
| 7 | Table/figure width | Float | Low-Med | `\resizebox`, column widths, `\small` in tables |
| 8 | `\enlargethispage` | Page | Medium | Add/remove one `\baselineskip` |
| 9 | Text rewrite (shorter) | Sentence | **High** | Shorten sentence — **approval gate** |

## Fix Ladder — Underfull Vbox

| # | Fix | Scope | Risk |
|---|-----|-------|------|
| 1 | Vertical spacing adjustment | Local | Low |
| 2 | Float repositioning | Float | Medium |
| 3 | Page height adjustment | Page | Medium |
| 4 | Content reflow | Structural | High |
| 5 | Text rewrite (longer) | Sentence | **High** — **approval gate** |

## Fix Ladder — Underfull Hbox

| # | Fix | Scope | Risk |
|---|-----|-------|------|
| 1 | Paragraph reflow | Paragraph | Low |
| 2 | Spacing adjustment | Paragraph | Low |
| 3 | Text rewrite (longer) | Sentence | **High** — **approval gate** |

## Text Modification Gate

When a high-priority text rewrite is needed:

- **Silent mode ON:** Apply the change, log it. Show summary of all text changes after the full loop completes.
- **Silent mode OFF:** Show the user:
  ```
  Line 347 (chapters/intro.tex): Overfull hbox (12.3pt too wide)

  Current:  "...the methodological framework demonstrates comprehensive..."
  Proposed: "...the methodology demonstrates comprehensive..."

  Accept? [y/n/edit]
  ```
  - `y` → apply
  - `n` → skip, accept the warning
  - `edit` → user provides their own rewrite

## Style File Constraints

Before applying any fix, check against the style file analysis from setup:

- Don't add packages that conflict with the document class
- Don't change font sizes if the class enforces them
- Don't use `\enlargethispage` if the class has strict page length requirements
- If unsure whether a fix is legal: ask the user

## Edge Cases

- **Infinite loop:** Fix A introduces warning B, fix B reintroduces A → caught by cycle detection (warning hash sets)
- **Style prohibits all fixes:** Report to user: "This warning cannot be fixed without violating style requirements."
- **Large documents (>100 pages):** Batch fixes before recompiling. Consider `\includeonly{}` for targeted compilation.
- **Binary file warnings:** Don't try to fix warnings from included binary content — detect and skip.
