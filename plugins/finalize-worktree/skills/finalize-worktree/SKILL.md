---
name: finalize-worktree
description: Commit all worktree changes, sync from main branch, run tests, and merge back. Use when done working in a git worktree.
user-invocable: true
---

# Finalize Worktree

Commit, verify, and merge the current worktree branch back into the main branch.

## Step 0: Validate Environment

Before anything, confirm you are inside a git worktree:

```bash
git rev-parse --is-inside-work-tree   # must be true
git worktree list                      # must show 2+ entries
```

Parse `git worktree list` output:
- The **first entry** is the main working tree — extract its path as `MAIN_REPO`.
- The **current entry** (matching your cwd) has the worktree branch name — extract as `WT_BRANCH`.

If the current directory IS the main working tree (not a worktree), **stop and tell the user** — this skill is only for worktrees.

Detect the **main branch** (the branch to merge into):
1. Check `git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null` — most reliable if remote exists.
2. Fallback: check which of `main`, `master`, `develop`, `trunk` exists locally.
3. If ambiguous, ask the user.

## Step 1: Check Status

Run in parallel:
- `git status` (never use `-uall` flag)
- `git diff --stat`
- `git log --oneline -5`

## Step 2: Commit in Worktree

- Stage specific files by name (never `git add -A` or `git add .`).
- Check `git log --oneline -5` for the project's commit message style and follow it. If no clear convention, use conventional commits (`feat:`, `fix:`, `refactor:`, etc.).
- Must commit before merging — a dirty working tree blocks merge if files overlap.
- If there are no changes to commit, skip to step 3.

## Step 3: Sync from Main Branch

Pull in any new commits from the main branch:

```bash
git merge <MAIN_BRANCH> --no-edit
```

If conflicts arise, resolve them carefully before continuing.

## Step 4: Test

Run the project's test suite. Check CLAUDE.md first for a project-specific test command. Otherwise look for common test config files (`package.json`, `Makefile`, `Cargo.toml`, `pyproject.toml`, `build.gradle`, `pom.xml`, etc.) and run the appropriate test command. If no test setup exists, skip.

## Step 5: Project-Specific Post-Work

If the project has a `CLAUDE.md`, check whether it mentions any post-work steps (e.g. writing lessons, updating docs, updating changelogs). Follow those instructions if applicable.

## Step 6: Merge into Main Branch

Operate on the main working tree using `git -C <MAIN_REPO>`:

```bash
# 1. Check if main working tree is clean
git -C <MAIN_REPO> status --short

# 2. Stash if dirty (skip if clean)
git -C <MAIN_REPO> stash --include-untracked

# 3. Merge the worktree branch
git -C <MAIN_REPO> merge <WT_BRANCH> --no-edit

# 4. Pop stash if we stashed (skip if nothing was stashed)
git -C <MAIN_REPO> stash pop
```

If stash pop conflicts, warn the user and leave the stash intact for manual resolution.

## Step 7: Report

Summarize:
- Files changed and commit(s) created
- Build and test results (pass/fail, test count)
- Merge outcome (fast-forward, merge commit, or conflicts)

## Rules

- **Never force-push or reset --hard** without explicit user approval.
- **Never use `--no-verify`** to skip hooks.
- Worktree branches typically have no remote — use `git merge`, not `git pull`.
- If merge conflicts arise on the main branch, resolve carefully — do NOT discard the main branch's changes.
- Do NOT push to remote unless the user explicitly asks.
- Do NOT delete the worktree — the session cleanup will handle that.
