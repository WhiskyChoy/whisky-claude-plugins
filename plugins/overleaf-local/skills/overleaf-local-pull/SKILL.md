---
name: overleaf-local-pull
description: Pull latest changes from Overleaf remote only (no push). Invocable as /overleaf-local:overleaf-local-pull (Claude Code) or $overleaf-local-pull (Codex).
user-invocable: true
---

# Pull from Overleaf

Pull remote changes without pushing local changes.

## Procedure

1. Check for uncommitted local changes. If present, ask user whether to stash or commit first.
2. Pull with rebase:
   ```bash
   git pull --rebase origin master
   ```
3. If conflicts:
   - Show conflicting files
   - Offer LaTeX-aware help resolving (respect `\section`, `\begin{figure}` as structural boundaries)
   - **Never auto-resolve** academic content
4. Report what changed (new/modified files, summary of remote commits pulled).

## Edge Cases

- **Auth token expired:** Guide user to regenerate at Overleaf → Account Settings → Git Integration.
- **Overleaf git bridge timeout:** Suggest retry later.
- **Dirty working tree:** Must be handled before pull — stash or commit.
