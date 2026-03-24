# overleaf-local — Implementation Specification

## Problem Statement

Non-technical Overleaf users (researchers, students, collaborators) need to:

1. **Work locally** on Overleaf projects via git — but git setup, authentication, and the Overleaf git bridge are intimidating.
2. **Compile LaTeX locally** — but installing a TeX distribution, choosing the right engine, and interpreting cryptic log output is a barrier.
3. **Fix compilation warnings** — overfull/underfull hbox/vbox warnings degrade typographic quality, but fixing them requires expert LaTeX knowledge (layout tricks, micro-typography, float management).

The core tension: LaTeX compilation produces unstructured, noisy logs. Translating those logs into targeted fixes — and applying fixes in the right order to avoid cascading regressions — requires a systematic procedure that a coding agent can follow.

## Solution Overview

A single Claude Code skill (`overleaf-local`) with sub-commands that covers the full lifecycle: prerequisite installation, Overleaf git clone, local compilation, iterative compile-fix loop, and bidirectional sync. The compile-fix loop uses a two-pass strategy (structural issues first, then local per-page fixes) with a prioritized fix ladder that prefers layout tricks over text modification. A dual-level lessons system accelerates future fixes by recording successful solutions.

## Procedure Design

### Entry Decision Tree

```
/overleaf-local invoked
│
├─ Detect workspace state:
│   ├─ Has .tex files + Overleaf git remote? ─────── WORKSPACE READY
│   ├─ Has .tex files, no Overleaf remote? ────────── Ask: link to Overleaf?
│   ├─ Near-empty workspace (no .tex)? ────────────── SETUP
│   └─ User provided a task prompt? ───────────────── SETUP (if needed) → TASK
│
├─ WORKSPACE READY
│   ├─ Sub-command provided? → execute it
│   └─ No sub-command? → show status, offer menu
```

### Sub-Commands

Each sub-command is a separate SKILL.md under `plugins/overleaf-local/skills/`. Directory names are **self-namespaced** (matching the `name` field) to prevent filesystem collisions when copied into Codex's flat `~/.codex/skills/` directory. This follows the [Codex skill-creator convention](https://github.com/openai/skills/blob/main/skills/.system/skill-creator/SKILL.md) where the folder name equals the skill name.

| Directory | `name` field | Claude Code | Codex | Purpose |
|-----------|-------------|-------------|-------|---------|
| `skills/overleaf-local/` | `overleaf-local` | `/overleaf-local` | `$overleaf-local` | Main entry (context-aware routing) |
| `skills/overleaf-local-setup/` | `overleaf-local-setup` | `/overleaf-local:overleaf-local-setup` | `$overleaf-local-setup` | Prerequisites, clone, engine detection, preferences |
| `skills/overleaf-local-compile/` | `overleaf-local-compile` | `/overleaf-local:overleaf-local-compile` | `$overleaf-local-compile` | Run the compile-fix loop |
| `skills/overleaf-local-sync/` | `overleaf-local-sync` | `/overleaf-local:overleaf-local-sync` | `$overleaf-local-sync` | Commit + pull --rebase + push to Overleaf |
| `skills/overleaf-local-pull/` | `overleaf-local-pull` | `/overleaf-local:overleaf-local-pull` | `$overleaf-local-pull` | Pull from Overleaf only |
| `skills/overleaf-local-push/` | `overleaf-local-push` | `/overleaf-local:overleaf-local-push` | `$overleaf-local-push` | Push to Overleaf only |
| `skills/overleaf-local-status/` | `overleaf-local-status` | `/overleaf-local:overleaf-local-status` | `$overleaf-local-status` | Show workspace state |
| `skills/overleaf-local-lesson/` | `overleaf-local-lesson` | `/overleaf-local:overleaf-local-lesson` | `$overleaf-local-lesson` | Manage lessons (save/list/search via argument) |

The `lesson` sub-command uses an `arguments` field instead of splitting into three separate skills:

```yaml
name: overleaf-local-lesson
arguments:
  - name: action
    description: "save, list, or search"
    required: true
  - name: pattern
    description: "Search pattern — regex or keyword to match against log warnings (for search action only)"
    required: false
```

Invocation examples:
- `/overleaf-local:overleaf-local-lesson save` / `$overleaf-local-lesson save`
- `/overleaf-local:overleaf-local-lesson list` / `$overleaf-local-lesson list`
- `/overleaf-local:overleaf-local-lesson search "overfull hbox"` / `$overleaf-local-lesson search "overfull hbox"`

No sub-command + no task prompt → show status and offer the menu.
No sub-command + task prompt (e.g., "read paper.pdf and help me write a review") → run SETUP if needed, then execute the task, then compile-fix.

### Cross-Platform Naming Convention

Directory names are **self-namespaced** — identical to the SKILL.md `name` field. This follows the [Codex skill-creator convention](https://github.com/openai/skills/blob/main/skills/.system/skill-creator/SKILL.md) where the folder name equals the skill name, and prevents filesystem collisions when skills from different plugins are copied into Codex's flat `~/.codex/skills/` directory.

- **Directory name** = **`name` field** = `<plugin>-<sub>` (e.g., `overleaf-local-setup`)
- **Claude Code:** `/<plugin>:<plugin>-<sub>` (e.g., `/overleaf-local:overleaf-local-setup`)
- **Codex:** `$<plugin>-<sub>` (e.g., `$overleaf-local-setup`)

For Codex installation, copy the skills tree directly — each directory name is globally unique:

```bash
cp -r plugins/overleaf-local/skills/* ~/.codex/skills/
```

---

## Phase 1: Setup

### 1.1 Prerequisite Detection & Installation

**Detection order:**

1. Check for `git` → if missing, offer install, exit if declined.
2. Check for TeX distribution:
   - Look for `pdflatex`, `xelatex`, `lualatex` on PATH.
   - If found, detect distribution: `pdflatex --version` → "MiKTeX" or "TeX Live".
   - If not found → offer installation.
3. Check available disk space before offering TeX installation.

**Storage-aware recommendation:**

```
You have X GB free.

Option A — Incremental (MiKTeX): ~200 MB now, downloads packages on demand.
            Best if disk is tight or you compile diverse projects.
Option B — Pre-installed (TeX Live small): ~550 MB, covers most use cases.
            Best for reliable offline builds.
Option C — Full (TeX Live full): ~7.5 GB, everything included.
            Best if you never want to think about missing packages.
```

**Platform-specific silent install commands:**

| Platform | Default Recommendation | Command |
|----------|----------------------|---------|
| Windows | MiKTeX (incremental) | `winget install -e --id MiKTeX.MiKTeX --silent --accept-package-agreements --accept-source-agreements` |
| macOS | TeX Live via Homebrew | `brew install --cask mactex-no-gui` |
| Linux | TeX Live via install-tl | `perl ./install-tl --no-interaction --scheme=small --no-doc-install --no-src-install` |

**Post-install configuration (MiKTeX):**

Enable auto-install-on-the-fly so missing packages download silently at compile time:
```bash
initexmf --admin --set-config-value="[MPM]AutoInstall=1"
```

**Post-install configuration (TeX Live):**

For scheme-small/basic, install commonly needed extras:
```bash
tlmgr install latexmk biber biblatex
```

**Hard gate:** If the user declines installation or conditions aren't met, exit with a clear message. Do not proceed with a broken environment.

### 1.2 Overleaf Git Bridge Setup

1. **Explain requirements:** Overleaf git integration requires a paid/institutional plan. Ask user to confirm they have access.
2. **Collect Overleaf project URL:** e.g., `https://git.overleaf.com/abc123def456`
3. **Collect git authentication token:** Direct user to Overleaf → Account Settings → Git Integration. Explain what the token is and where to find it.
4. **Credential storage preference:**
   - **Secure (recommended):** Use OS credential helper (`git credential-manager` on Windows, `osxkeychain` on macOS, `libsecret`/`store` on Linux). Token stored in OS keychain.
   - **Quick:** Store token in `.git/config` URL (`https://git:TOKEN@git.overleaf.com/...`). Plaintext but convenient.
   - **Manual:** Ask every time. Most secure but tedious.
5. **Clone:** `git clone <configured-url> .` (into current workspace).
6. **Verify:** Confirm clone succeeded, show file listing.

### 1.3 Engine Auto-Detection

Scan `.tex` files in the workspace to select the LaTeX engine:

| Signal | Engine |
|--------|--------|
| CJK characters (Unicode ranges: U+4E00–U+9FFF, U+3000–U+303F, etc.) | XeLaTeX |
| `\usepackage{fontspec}` or `\usepackage{xeCJK}` or `\usepackage{ctex}` | XeLaTeX |
| `\usepackage[T1]{fontenc}` + no CJK signals | pdfLaTeX |
| `\directlua` or `\usepackage{luacode}` | LuaLaTeX |
| Ambiguous or conflicting signals | Ask user |

Default if no signals detected: **pdfLaTeX** (fastest, most compatible).

### 1.4 Build System Detection

Check for existing build configuration, in priority order:

1. `latexmkrc` or `.latexmkrc` → use `latexmk`
2. `Makefile` with LaTeX-related targets → use `make`
3. `arara` directives in main `.tex` file (`% arara:`) → use `arara`
4. None found → use direct engine invocation with appropriate flags

When using direct invocation, construct the command based on detected engine:
```bash
# pdfLaTeX
pdflatex -interaction=nonstopmode -halt-on-error main.tex

# XeLaTeX
xelatex -interaction=nonstopmode -halt-on-error main.tex

# LuaLaTeX
lualatex -interaction=nonstopmode -halt-on-error main.tex
```

Always use `-interaction=nonstopmode` (don't stop on errors, log them) and `-halt-on-error` (stop after first fatal error rather than producing garbage output).

For bibliography: detect `\bibliography{}` or `\addbibresource{}` → run `bibtex` or `biber` respectively between engine passes. A typical full build is: engine → bib → engine → engine (for cross-references).

### 1.5 Style File Analysis

Detect `.cls` and `.sty` files in the workspace:
- Identify the document class (`\documentclass{...}`)
- Check for known conference/journal classes (IEEE, ACM, Springer, Elsevier, etc.)
- Note constraints: column count, margin settings, font size restrictions
- If class is unknown or custom: ask user what constraints to respect

Store analysis results for the compile-fix phase (which layout tricks are legal).

### 1.6 User Preference Collection

Ask these questions once during setup, store answers in project config:

1. **Silent text modification?** — "When fixing compilation warnings, may I slightly reword sentences without asking each time? You can always review changes in the diff."
   - Yes → apply text changes silently, show summary after
   - No → ask before each text modification
2. **Parallel fix trials?** — "May I use subagents to try multiple layout fixes in parallel? Faster but uses more resources."
   - Yes → spawn subagents for fix trials
   - No → sequential fix attempts
3. **Credential storage mode?** — (covered in 1.2)

### 1.7 Post-Setup Knowledge Persistence

After setup completes, write project-specific configuration so future agent sessions inherit the setup:

**For Claude Code** — append to project `CLAUDE.md`:
```markdown
## LaTeX Environment (auto-generated by overleaf-local)
- Distribution: MiKTeX 24.1 (auto-install enabled)
- Engine: XeLaTeX
- Build command: latexmk -xelatex main.tex
- Document class: IEEEtran (two-column, 10pt)
- Overleaf remote: configured (git.overleaf.com)
```

**For Codex CLI** — append to `Agents.md` in project root, same content.

---

## Phase 2: Task Execution (Writing)

When the user provides a writing task (e.g., "read paper.pdf and write a review"), the skill generates LaTeX that is **template-aware from the start** to minimize compile-fix work later.

### 2.1 Template-Aware Generation

Before generating any LaTeX:

1. Read the document class (`.cls`) to understand:
   - Column width (single vs. two-column)
   - Available float positions
   - Section structure conventions
   - Citation style (numeric, author-year)
2. Read existing `.tex` files to match style:
   - Macro usage patterns
   - Package conventions
   - Naming conventions for labels/refs

### 2.2 Generation Rules

- **Respect column width:** Don't write paragraphs with long unbreakable tokens (URLs, code) in two-column layouts without wrapping them.
- **Float conventions:** Place figures/tables with `[htbp]` by default; use `\centering` not `\begin{center}`.
- **Bibliography:** Match existing citation command style (`\cite`, `\citep`, `\citet`).
- **No hardcoded dimensions:** Use relative units (`\textwidth`, `\linewidth`) not absolute lengths.

---

## Phase 3: Compile-Fix Loop

This is the core algorithm. Two passes: structural (whole-document), then local (per-page).

### 3.1 Pre-Compile: File Dependency Map

**When to build:** If `\input{}`, `\include{}`, or `\subfile{}` commands are found in any `.tex` file.

**How:** Recursively scan from the main `.tex` entry point. Build an in-memory tree:
```
main.tex
├── preamble.tex
├── chapters/intro.tex
│   └── chapters/figures/fig1.tex
├── chapters/method.tex
└── chapters/conclusion.tex
```

**Purpose:** Map log line numbers back to the correct source file. LaTeX logs emit `(./chapters/intro.tex` when entering a file and `)` when leaving — track a file stack during log parsing.

**When NOT to build:** Single `main.tex` with no `\input` commands. Skip the overhead.

### 3.2 Pre-Compile: Lesson Lookup

Before compiling, load available lessons from:
1. `<project>/.claude/latex-lessons/*.md` (project-level, higher priority)
2. `~/.claude/latex-lessons/*.md` (user-level, fallback)

Index lessons by `trigger` and `pattern` fields for fast matching against log output.

### 3.3 Pass 1 — Structural

**Goal:** Resolve all errors and stabilize document structure (page breaks, float placement) before doing local fixes.

```
Step 1: Compile (full build: engine → bib → engine → engine)
Step 2: Parse log → classify issues

IF errors exist:
    Step 3a: Fix errors in priority order:
        1. Missing packages → install via tlmgr/mpm, recompile
        2. Undefined control sequences → check for typos, missing \usepackage
        3. Missing files → check paths, \graphicspath
        4. Syntax errors → fix LaTeX syntax
    Step 4a: Recompile, repeat until no errors

IF float warnings exist (figures/tables displaced):
    Step 3b: Analyze all floats globally:
        - Map each float to its declared position and actual placement
        - Identify floats that drifted far from their \ref
        - Adjust float specifiers ([htbp] → [!htbp], [H] with float package)
        - Consider \clearpage at section boundaries if float backlog builds
    Step 4b: Recompile, verify float placement stabilized

EXIT Pass 1 when: zero errors, float placement stable (same across two consecutive compiles)
```

### 3.4 Pass 2 — Local (Per-Page/Per-Region)

**Goal:** Eliminate all remaining warnings — overfull/underfull hbox/vbox.

```
Step 1: Parse log for remaining warnings
Step 2: Group warnings by source file and line region
Step 3: For each warning group:
    a. Check lessons database for matching pattern
       → If high-confidence match found: apply lesson fix directly
    b. If no lesson match: walk the fix ladder (see below)
    c. If parallel mode enabled:
       → Spawn subagents to trial top 2-3 candidate fixes concurrently
       → Pick the fix that produces fewest remaining warnings
    d. If parallel mode disabled:
       → Try fixes sequentially, stop at first that resolves the warning
Step 4: Recompile
Step 5: Re-parse → if new warnings appeared (cascade), repeat from Step 1
Step 6: Exit when zero warnings

SAFETY: Maximum iteration limit (configurable, default 20).
If limit reached → report remaining warnings to user, ask how to proceed.
```

### 3.5 Fix Ladder — Overfull Hbox

Applied in priority order (cheapest/safest first):

| Priority | Fix | Scope | Risk | Technique |
|----------|-----|-------|------|-----------|
| 1 | URL/path line breaking | Word | None | `\usepackage[hyphens]{url}`, `\url{}` wrapping |
| 2 | Hyphenation hints | Word | None | `\-` manual hyphenation points, `\allowbreak` |
| 3 | Sloppy paragraph | Paragraph | Low | `\begin{sloppypar}...\end{sloppypar}` for the specific paragraph |
| 4 | Emergency stretch | Paragraph | Low | `{\emergencystretch=1em ...}` scoped to paragraph |
| 5 | Looseness adjustment | Paragraph | Low-Med | `\looseness=-1` to reflow into one fewer line |
| 6 | Tolerance tuning | Paragraph | Low | Local `\tolerance=200` / `\hbadness=200` |
| 7 | Table/figure width | Float | Low-Med | Adjust `\resizebox`, column widths, `\small` in tables |
| 8 | `\enlargethispage` | Page | Medium | Add/remove one `\baselineskip` from page height |
| 9 | Text rewrite (shorter) | Sentence | **High** | Shorten sentence to reduce line count — **approval gate** |

### 3.6 Fix Ladder — Underfull Vbox

| Priority | Fix | Scope | Risk |
|----------|-----|-------|------|
| 1 | Vertical spacing adjustment | Local | Low | `\vspace` tuning, `\vfill` placement |
| 2 | Float repositioning | Float | Medium | Adjust `[htbp]` specifiers, `\FloatBarrier` |
| 3 | Page height adjustment | Page | Medium | `\enlargethispage{-1\baselineskip}` |
| 4 | Content reflow | Structural | High | Reorder floats, adjust section breaks |
| 5 | Text rewrite (longer) | Sentence | **High** | Expand sentence to fill space — **approval gate** |

### 3.7 Fix Ladder — Underfull Hbox

| Priority | Fix | Scope | Risk |
|----------|-----|-------|------|
| 1 | Paragraph reflow | Paragraph | Low | `\looseness=1` to add one line |
| 2 | Spacing adjustment | Paragraph | Low | `\spaceskip` tuning |
| 3 | Text rewrite (longer) | Sentence | **High** | Slightly expand to fill — **approval gate** |

### 3.8 Text Modification Gate

When a fix at priority 8/9 (text rewrite) is needed:

- **Silent mode ON:** Apply the change, log it. Show a summary of all text changes after the full compile-fix loop completes.
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

### 3.9 Style File Constraints

Before applying any fix, check against the style file analysis from Phase 1:

- **Don't add packages** that conflict with the document class (e.g., `geometry` with a journal class that controls margins).
- **Don't change font sizes** if the class enforces them.
- **Don't use `\enlargethispage`** if the class has strict page length requirements (some conferences check page count exactly).
- If unsure whether a fix is legal: ask the user.

---

## Phase 4: Sync

### 4.1 Commit

```bash
git add -A
git commit -m "<auto-generated meaningful message>"
```

Commit message format: summarize what changed (e.g., "Fix overfull hbox in sections 3-5, adjust float placement").

### 4.2 Pull with Rebase

```bash
git pull --rebase origin master
```

If conflicts:
- Show conflicting files to user
- Offer to help resolve (LaTeX-aware merge — understand that `\section`, `\begin{figure}`, etc. are structural boundaries)
- Do not auto-resolve — academic content conflicts require human judgment

### 4.3 Push

```bash
git push origin master
```

Confirm with user before pushing: "Ready to push N commits to Overleaf. Proceed?"

---

## Lessons System

### Storage Structure

```
~/.claude/latex-lessons/           # User-level (cross-project)
├── overfull-url-linebreak.md
├── underfull-vbox-float-reorder.md
└── ...

<project>/.claude/latex-lessons/   # Project-level (template-specific)
├── ieee-twocol-table-overflow.md
└── ...
```

### Lesson File Format

```markdown
---
trigger: overfull hbox
pattern: "Overfull \\\\hbox.*\\\\url\\{"
context:
  - url-in-text
  - single-column
fix: url-linebreak
confidence: high
applied_count: 3
last_used: 2026-03-20
template: IEEEtran
---

## Problem

Long URLs in running text cause overfull hbox. The `\url{}` command doesn't
break at arbitrary positions by default.

## Fix

Add `\usepackage[hyphens]{url}` to the preamble. If already present, wrap the
specific URL in `\begin{sloppypar}...\end{sloppypar}`.

## Why It Works

The `hyphens` option for the `url` package allows line breaks at hyphen
characters in URLs. `sloppypar` relaxes inter-word spacing constraints,
giving TeX more flexibility to find valid line breaks.

## Verification

After applying, the overfull hbox warning for the affected line should
disappear. No new warnings should be introduced.
```

### Lesson Lifecycle

1. **Creation:** After a non-trivial fix succeeds (not a simple missing-package install), the skill suggests saving:
   ```
   This fix resolved [warning type] in [context]. Save as a reusable lesson? [y/n]
   ```
   In silent mode: auto-save with `confidence: medium` (elevated to `high` after reuse).

2. **Matching:** During compile-fix, compare each log warning against lessons:
   - Match `trigger` (warning type) + `pattern` (regex against log line)
   - Boost score if `context` tags match current environment
   - Boost score if `template` matches current document class
   - Prefer higher `confidence` and `applied_count`

3. **Application:** High-confidence match → apply directly. Partial match → suggest to user.

4. **Update:** After successful reuse: increment `applied_count`, update `last_used`, promote `confidence` if previously `medium`.

5. **Pruning:** Lessons with `applied_count: 0` and `last_used` older than 6 months can be suggested for removal during `lesson list`.

### Lookup Priority

1. Project-level lessons (most specific — template and project context match)
2. User-level lessons with matching `template` field
3. User-level lessons without template (general knowledge)

---

## Interface Contract

### Inputs

| Input | Source | Required |
|-------|--------|----------|
| Overleaf project URL | User (during setup) | For setup only |
| Git authentication token | User (during setup) | For setup only |
| `.tex` source files | Workspace (after clone) | Yes |
| User preferences (silent mode, parallel, credentials) | User (during setup) | Yes |
| Task prompt | User (optional) | No — triggers writing phase |

### Outputs

| Output | Destination | When |
|--------|-------------|------|
| Compiled PDF | Workspace | After each successful compile |
| Project config | `CLAUDE.md` / `Agents.md` | After setup |
| Lessons | `.claude/latex-lessons/` or `~/.claude/latex-lessons/` | After saving fixes |
| Fix summary | Terminal output | After compile-fix loop completes |
| Git commits | Local + Overleaf remote | After sync |

### Preconditions

- OS: Windows, macOS, or Linux
- Network: required for setup (TeX install, Overleaf clone) and sync
- Overleaf plan: must support git integration (paid or institutional)
- Disk space: minimum 500 MB free (for minimal TeX install)

### Postconditions

- After setup: workspace has cloned Overleaf project, TeX distribution installed, engine selected
- After compile: PDF exists, zero warnings (or user-accepted remaining warnings)
- After sync: local commits pushed to Overleaf remote

---

## Design Decisions & Rationale

### Two-pass compile-fix (structural → local) over flat loop

**Decided:** Fix structural issues (errors, float placement) before local issues (hbox/vbox).
**Rejected:** Flat priority-queue loop (fix one issue at a time regardless of type).
**Why:** Structural changes invalidate local work. Fixing an overfull hbox on page 7 is wasted effort if a float repositioning later changes page 7's content entirely. The two-pass approach mirrors how human LaTeX experts work.

### MiKTeX default on Windows, TeX Live on Unix

**Decided:** Platform-specific defaults with user override.
**Rejected:** One distribution everywhere.
**Why:** MiKTeX's auto-install-on-the-fly is uniquely valuable for non-technical Windows users — they never encounter "missing package" errors. TeX Live is the native, well-supported choice on Unix and has reliable `tlmgr`.

### In-memory dependency map over cached file

**Decided:** Build the file dependency map by scanning `\input`/`\include` at each compile-fix invocation.
**Rejected:** YAML/TOML cache file in workspace.
**Why:** The map is cheap to build (grep for includes, resolve paths) and always fresh. A cache file creates staleness risk — user adds `\input{newchapter}`, cache is wrong until regenerated.

### Dual-level lessons over single location

**Decided:** Project-level + user-level lessons with project taking priority.
**Rejected:** User-level only.
**Why:** A fix for IEEE two-column overflow may not apply to a Springer single-column layout. Project-level lessons capture template-specific knowledge. User-level lessons capture universal LaTeX knowledge (URL line breaking, etc.).

### Project-level config over global config

**Decided:** Write TeX environment info to project `CLAUDE.md` / `Agents.md`.
**Rejected:** Global `~/.claude/` config.
**Why:** TeX setup varies per project — one uses pdfLaTeX, another XeLaTeX. Global config would create conflicts. Project-level config is inherited by any agent session in that workspace automatically.

### Layout tricks before text changes

**Decided:** Exhaust all layout-level fixes before proposing text modification.
**Rejected:** Immediate text rewrite, or mixed strategy.
**Why:** Text content is semantically meaningful, especially in academic writing. Layout tricks are invisible to the reader. The fix ladder encodes this: zero-risk layout changes first, high-risk content changes last and gated behind user approval.

---

## Edge Cases and Boundary Conditions

### Setup Phase

- **No internet during setup:** Can't install TeX or clone from Overleaf. Detect early, tell user, exit.
- **TeX already installed but too old:** Some packages require recent TeX. Check version, suggest update if needed.
- **Overleaf project is empty:** Clone succeeds but no `.tex` files. Enter writing mode or ask user what to do.
- **Overleaf token expired:** Git clone/pull fails with auth error. Detect, guide user to regenerate token.
- **Workspace already has a different git remote:** Don't overwrite. Ask user how to proceed.

### Compile-Fix Phase

- **Infinite loop risk:** Fix A introduces warning B, fix B reintroduces warning A. Mitigated by iteration limit (default 20) and cycle detection (track warning hash sets — if a previous state recurs, stop).
- **Style file prohibits all applicable fixes:** The fix ladder is exhausted but the warning remains. Report to user: "This warning cannot be fixed without violating the style requirements. Accept it or modify the constraint."
- **Multi-file project with shared preamble:** A preamble fix (adding a package) might affect all files. Apply globally, verify no regressions.
- **Very large documents (>100 pages):** Compile time becomes significant. Batch fixes aggressively before recompiling. Consider `\includeonly{}` for targeted compilation during fix iterations.
- **Binary files in project (images, PDFs):** Don't try to "fix" warnings originating from included binary content. Detect and skip.

### Sync Phase

- **Concurrent Overleaf edits:** Another collaborator edited on Overleaf while user worked locally. `git pull --rebase` may conflict. Show conflicts, help resolve, never auto-resolve content.
- **Large binary files:** Git push may be slow with many images. Warn user about push size.
- **Overleaf git bridge downtime:** Push/pull fails. Detect, suggest retry later.

### Lessons System

- **Conflicting lessons:** Two lessons match the same warning with different fixes. Prefer higher `applied_count` and `confidence`. If tied, prefer project-level over user-level.
- **Stale lessons:** A lesson references a package or technique that no longer works with current TeX. The `last_used` and `applied_count` fields help identify stale entries. If a lesson's fix fails, demote its confidence.
- **Lesson explosion:** User accumulates hundreds of lessons. Performance of pattern matching could degrade. Mitigated by indexing on `trigger` field (coarse category) before running regex `pattern` matching.

---

## Verification Criteria

### Setup

- [ ] TeX distribution installed and `pdflatex --version` / `xelatex --version` succeeds
- [ ] Git clone from Overleaf remote succeeds
- [ ] Engine auto-detection matches manual inspection of `.tex` files
- [ ] Project config written to `CLAUDE.md` / `Agents.md` and is parseable

### Compile-Fix

- [ ] Full build produces a valid PDF
- [ ] Zero warnings in the final log (or user-accepted exceptions)
- [ ] No text modifications applied without user consent (unless silent mode)
- [ ] Fix did not violate style file constraints
- [ ] Iteration count stayed within limit
- [ ] All modified `.tex` files are valid LaTeX (no broken syntax introduced by fixes)

### Sync

- [ ] All local changes committed with meaningful messages
- [ ] `git push` to Overleaf succeeded
- [ ] Overleaf web editor shows the pushed changes

### Lessons

- [ ] Saved lessons are valid markdown with correct YAML frontmatter
- [ ] Lesson matching returns relevant results for known warning patterns
- [ ] Lessons are stored in the correct level (project vs user)
- [ ] `applied_count` and `last_used` update after successful reuse

---

## Open Risks

1. **LaTeX log parsing fidelity.** The `.log` format is unstructured, wraps at 79 characters mid-word, and varies between engines. No parser will be 100% accurate. The skill should be conservative — if it can't parse a warning, report it verbatim rather than misinterpreting.

2. **Fix cascade depth.** In pathological cases (very tight two-column layouts with many floats), the compile-fix loop may oscillate. The iteration limit and cycle detection mitigate this, but some documents may require human intervention.

3. **Style file diversity.** There are thousands of LaTeX document classes. The skill can recognize common ones (IEEE, ACM, Springer, Elsevier, LNCS), but custom or rare classes will need user guidance on constraints.

4. **Text rewrite quality.** Claude rewriting academic sentences needs to preserve technical meaning. Even in silent mode, there's a risk of semantic drift. The fix summary should make text changes easy to review.

5. **MiKTeX auto-install network dependency.** On Windows with MiKTeX incremental install, the first compile of a package-heavy document requires network access to download packages. If the user is offline, compilation fails with unhelpful errors. The skill should detect this and suggest pre-installing known required packages.

6. **Overleaf git bridge limitations.** Overleaf's git integration has known quirks: large projects may time out on clone, binary files (PDFs, images) bloat the repo, and the bridge occasionally lags behind the web editor state. The skill should handle these gracefully with retries and clear error messages.

7. **Subagent coordination.** When parallel fix trials are enabled, subagents each try a different fix on the same file. Merging the "winning" fix back requires care — the main agent must apply only the chosen fix, not combine multiple attempts.
