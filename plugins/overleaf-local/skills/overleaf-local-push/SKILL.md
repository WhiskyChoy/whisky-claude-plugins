---
name: overleaf-local-push
description: Push local commits to Overleaf remote only (no pull). Invocable as /overleaf-local:overleaf-local-push (Claude Code) or $overleaf-local-push (Codex).
user-invocable: true
---

# Push to Overleaf

Push local commits to the Overleaf remote.

## Procedure

1. Check for uncommitted changes. If present, ask user whether to commit first.
2. Show what will be pushed:
   ```bash
   git log origin/master..HEAD --oneline
   ```
3. Confirm with user: "Ready to push N commits to Overleaf. Proceed?"
4. Push:
   ```bash
   git push origin master
   ```
5. Report success or failure.

## Edge Cases

- **Remote has new commits:** Push will be rejected. Suggest running `/overleaf-local:overleaf-local-pull` first or `/overleaf-local:overleaf-local-sync` for the full flow.
- **Auth token expired:** Guide user to regenerate at Overleaf → Account Settings → Git Integration.
- **Large binary files:** Warn about push size if images are included.
