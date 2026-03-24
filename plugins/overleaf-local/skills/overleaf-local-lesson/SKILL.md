---
name: overleaf-local-lesson
description: Manage the LaTeX lessons database — save a new lesson from a successful fix, list all stored lessons, or search lessons by warning pattern. Invocable as /overleaf-local:overleaf-local-lesson (Claude Code) or $overleaf-local-lesson (Codex).
user-invocable: true
arguments:
  - name: action
    description: "save, list, or search"
    required: true
  - name: pattern
    description: "Search pattern — regex or keyword to match against log warnings (for search action only)"
    required: false
---

# Lessons: LaTeX Fix Knowledge Base

A dual-level system for recording and reusing successful LaTeX fixes.

## Storage Locations

```
~/.claude/latex-lessons/           # User-level (cross-project)
<project>/.claude/latex-lessons/   # Project-level (template-specific, higher priority)
```

## Lesson File Format

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

The `hyphens` option allows line breaks at hyphen characters in URLs.
`sloppypar` relaxes inter-word spacing constraints.

## Verification

After applying, the overfull hbox warning for the affected line should
disappear. No new warnings should be introduced.
```

## Action: save

After a non-trivial fix succeeds (not a simple missing-package install), suggest saving:

```
This fix resolved [warning type] in [context]. Save as a reusable lesson? [y/n]
```

In silent mode: auto-save with `confidence: medium` (promoted to `high` after reuse).

Determine scope:
- Template-specific fix → save to project-level
- General LaTeX knowledge → save to user-level

Use kebab-case filenames: `overfull-url-linebreak.md`, `underfull-vbox-float-reorder.md`.

## Action: list

Display all lessons from both levels, grouped by location:

```
Project-level (IEEEtran):
  ieee-twocol-table-overflow.md — high confidence, used 5 times

User-level:
  overfull-url-linebreak.md — high confidence, used 3 times
  underfull-vbox-float-reorder.md — medium confidence, used 1 time
```

Flag stale lessons: `applied_count: 0` and `last_used` older than 6 months → suggest removal.

## Action: search

Match the given pattern against lesson `trigger` and `pattern` fields. Return matching lessons ranked by relevance:

1. Pattern regex match against the query
2. Boost if `context` tags match current environment
3. Boost if `template` matches current document class
4. Prefer higher `confidence` and `applied_count`

## Lookup Priority (used by compile-fix loop)

1. Project-level lessons (most specific)
2. User-level lessons with matching `template` field
3. User-level lessons without template (general knowledge)

## Lesson Lifecycle

1. **Creation:** After successful non-trivial fix → suggest save
2. **Matching:** Compare log warnings against `trigger` + `pattern` regex
3. **Application:** High-confidence → apply directly. Partial match → suggest to user.
4. **Update:** After reuse → increment `applied_count`, update `last_used`, promote confidence
5. **Pruning:** Stale lessons surfaced during `list` action

## Conflicting Lessons

If two lessons match the same warning with different fixes: prefer higher `applied_count` and `confidence`. If tied, prefer project-level over user-level.
