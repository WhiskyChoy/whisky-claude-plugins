---
name: overleaf-local
description: Local Overleaf workflow — clone, compile, fix warnings, and sync LaTeX projects via git. Use when the user wants to work on an Overleaf project locally, compile LaTeX, fix compilation warnings, or sync changes back to Overleaf. Triggers on "overleaf", "latex compile", "tex compile", "fix warnings", "hbox", "vbox", or any Overleaf git URL.
user-invocable: true
---

# overleaf-local: Local Overleaf Workflow

## Platform Compatibility

This skill works with **Claude Code CLI**, **OpenAI Codex CLI**, and other SKILL.md-compatible agents. Instructions use Claude Code tool names — see [`PLATFORM_COMPAT.md`](https://github.com/WhiskyChoy/whisky-claude-plugins/blob/master/PLATFORM_COMPAT.md) for the full cross-platform tool mapping.

## What This Does

A full lifecycle tool for Overleaf projects: prerequisite installation, Overleaf git clone, local compilation, iterative compile-fix loop (two-pass: structural then local), and bidirectional sync. A dual-level lessons system accelerates future fixes by recording successful solutions.

**Target audience:** Non-technical Overleaf users (researchers, students, collaborators) who find git, TeX distributions, and LaTeX log output intimidating.

## Entry Decision Tree

On invocation, detect workspace state and route:

1. **Has `.tex` files + Overleaf git remote?** → WORKSPACE READY
2. **Has `.tex` files, no Overleaf remote?** → Ask: link to Overleaf?
3. **Near-empty workspace (no `.tex`)?** → Run `/overleaf-local:overleaf-local-setup`
4. **User provided a task prompt?** → Run setup if needed → execute task → compile-fix

If workspace is ready:
- Sub-command provided → execute it
- No sub-command, no task → show status and offer menu

## Sub-Commands

| Command | Purpose |
|---------|---------|
| `/overleaf-local` | Main entry — context-aware routing (this skill) |
| `/overleaf-local:overleaf-local-setup` | Prerequisites, clone, engine detection, preferences |
| `/overleaf-local:overleaf-local-compile` | Run the compile-fix loop |
| `/overleaf-local:overleaf-local-sync` | Commit + pull --rebase + push to Overleaf |
| `/overleaf-local:overleaf-local-pull` | Pull from Overleaf only |
| `/overleaf-local:overleaf-local-push` | Push to Overleaf only |
| `/overleaf-local:overleaf-local-status` | Show workspace state |
| `/overleaf-local:overleaf-local-lesson` | Manage lessons (save/list/search) |

## Workspace Detection

To determine workspace state, check:

```bash
# Check for .tex files
find . -maxdepth 3 -name "*.tex" -type f | head -5

# Check for Overleaf git remote
git remote -v 2>/dev/null | grep "overleaf"
```

## Task Execution (Writing Mode)

When the user provides a writing task (e.g., "read paper.pdf and write a review") instead of a sub-command:

1. Run setup if prerequisites are missing
2. Read the document class (`.cls`) to understand column width, float positions, section conventions, citation style
3. Read existing `.tex` files to match macro usage, package conventions, label naming
4. Generate LaTeX that is **template-aware from the start**:
   - Respect column width — don't write long unbreakable tokens in two-column layouts without wrapping
   - Use `[htbp]` for floats, `\centering` not `\begin{center}`
   - Match existing citation command style (`\cite`, `\citep`, `\citet`)
   - Use relative units (`\textwidth`, `\linewidth`) not absolute lengths
5. Run `/overleaf-local:overleaf-local-compile` to fix any remaining warnings

## Language

Match the user's language. If they speak Chinese, respond in Chinese. Technical terms in English mixed with native language is natural and encouraged.
