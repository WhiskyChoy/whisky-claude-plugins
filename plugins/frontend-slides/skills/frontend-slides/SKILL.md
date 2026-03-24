---
name: frontend-slides
description: "[Virtual] Resolves to the best available provider for HTML slide generation. Does not implement the capability itself — delegates to ECC built-in or compatible plugins."
user-invocable: true
---

# Frontend Slides (Virtual Provider)

## Platform Compatibility

This skill works with **Claude Code CLI**, **OpenAI Codex CLI**, and other SKILL.md-compatible agents. Instructions use Claude Code tool names — see [`PLATFORM_COMPAT.md`](https://github.com/WhiskyChoy/whisky-claude-plugins/blob/master/PLATFORM_COMPAT.md) for the full cross-platform tool mapping.

This is a **virtual skill** — it does not generate slides itself. It resolves to the best available provider and delegates.

## Resolution Protocol

On every invocation, determine which provider is available by checking `providers.json` (in the same directory as this SKILL.md) in order:

```bash
SKILL_DIR="$(dirname "$(find ~/.claude -path '*/frontend-slides/providers.json' -maxdepth 6 2>/dev/null | head -1)")"
```

### Step 1: Check Providers

Read `providers.json` and check each provider in order:

1. **ECC frontend-slides** — Check if `~/.claude/skills/frontend-slides/SKILL.md` exists AND contains `origin: ECC` in its frontmatter. If this virtual plugin has overwritten the ECC skill at that path, check whether the SKILL.md there contains the phrase "Virtual Provider" — if so, it is this resolver, not the real skill. In that case, skip.
2. **ECC frontend-design** — Check if `~/.claude/skills/frontend-design/SKILL.md` exists with `origin: ECC`.

For each provider, use the `check` object in `providers.json`:
- `method: "skill-file"` — verify the file at `path` exists and (if `expect_field`/`expect_value` are set) that the frontmatter contains the expected value.

### Step 2: Delegate or Guide

- **If a provider is found**: Tell the user which provider is being used, then invoke it with the user's original arguments. Pass all arguments through unchanged.
- **If no provider is found**: Show the `fallback_guidance` message from `providers.json`. Help the user install or update Claude Code to get the ECC skill.

### Step 3: Forward Invocation

When delegating to the resolved provider, use its `invoke` pattern from `providers.json`. For example, for the ECC built-in:

```
Skill("frontend-slides", "<user's original arguments>")
```

## Why This Exists

Skills like `paper-to-slides` depend on a slide generation capability. Rather than hardcoding a specific provider, this virtual skill:

- **Centralizes resolution** — one place to check what's available
- **Enables swapping** — add a custom provider to `providers.json` without changing dependent skills
- **Guides users** — when nothing is available, explains how to get it
- **Keeps the marketplace self-contained** — users install from one repo, virtual dependencies included

## Adding a New Provider

Edit `providers.json` and add an entry to the `providers` array. Fields:

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Human-readable name |
| `type` | Yes | `ecc-skill`, `plugin`, or `external` |
| `check.method` | Yes | How to verify availability (`skill-file`, `command`, `plugin-list`) |
| `check.path` | Yes | Path or command to check |
| `invoke` | Yes | How to call this provider |
| `notes` | No | Context about capabilities or limitations |

Providers are checked in array order — put the preferred/most capable provider first.
