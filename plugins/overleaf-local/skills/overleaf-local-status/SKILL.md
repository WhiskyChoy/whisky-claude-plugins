---
name: overleaf-local-status
description: Show workspace state — TeX distribution, engine, build system, Overleaf remote status, uncommitted changes, and last compilation result. Invocable as /overleaf-local:overleaf-local-status (Claude Code) or $overleaf-local-status (Codex).
user-invocable: true
---

# Status: Workspace Overview

Display the current state of the local Overleaf workspace.

## Information to Gather and Display

1. **TeX distribution:** Run `pdflatex --version` or equivalent. Show distribution name and version.
2. **Engine:** Read from project config (CLAUDE.md / Agents.md) or re-detect from `.tex` files.
3. **Build system:** latexmk / make / arara / direct invocation.
4. **Document class:** What `.cls` is in use, any known constraints.
5. **Overleaf remote:**
   ```bash
   git remote -v | grep overleaf
   ```
6. **Git status:**
   ```bash
   git status --short
   git log origin/master..HEAD --oneline  # unpushed commits
   git log HEAD..origin/master --oneline  # unmerged remote commits
   ```
7. **Last compilation:** Check if PDF exists, its modification time, and whether the last log had warnings/errors.

## Output Format

Present as a concise summary:

```
Workspace: /path/to/project
Distribution: MiKTeX 24.1 (auto-install enabled)
Engine: XeLaTeX
Build: latexmk -xelatex main.tex
Class: IEEEtran (two-column, 10pt)
Remote: git.overleaf.com/abc123 (connected)
Local changes: 3 files modified, 1 untracked
Unpushed: 2 commits
Last compile: OK (0 errors, 0 warnings) — main.pdf 2026-03-24 14:30
```

Adapt to what information is actually available — skip sections that don't apply (e.g., no remote if not connected to Overleaf).
