# CLAUDE.md

## What this repo is

A Claude Code plugin marketplace. Each plugin lives under `plugins/<name>/` and provides skills (SKILL.md), optional tools, and metadata. The repo is also compatible with Codex CLI via SKILL.md.

## Plugin anatomy

Every plugin MUST have this structure:

```
plugins/<name>/
  .claude-plugin/
    plugin.json          # name, description, author, platforms
  skills/
    <name>/
      SKILL.md           # the skill definition (YAML frontmatter + markdown body)
```

Optional subdirectories: `tools/`, `scripts/`, `src/`. Scripts that a SKILL.md references should live alongside it in `skills/<name>/`, not in `tools/`. The `tools/` directory is for standalone CLI tools that get installed separately.

### plugin.json

```jsonc
{
  "name": "<name>",
  "description": "<one-line>",
  "author": { "name": "whisky" },
  "platforms": { "claude-code": "full", "codex": "partial" }  // "full" or "partial"
}
```

The `name` field in plugin.json MUST match the directory name under `plugins/`.

### SKILL.md frontmatter

```yaml
---
name: <name>
description: <trigger description for the agent>
user-invocable: true  # if it can be called with /name
allowed_tools: [...]  # optional
arguments:            # optional
  - name: <arg>
    description: <desc>
    required: true|false
---
```

## Registry: marketplace.json

`.claude-plugin/marketplace.json` is the central index. Every plugin directory under `plugins/` MUST have a corresponding entry here. Remove a plugin from both places or neither.

## README.md is auto-generated

The README is generated from plugin metadata. Do not hand-edit it. After changing plugins, regenerate it. The footer says: *"This README is auto-generated from plugin metadata. Do not edit manually."*

## Cross-platform compatibility

SKILL.md files use Claude Code tool names. `PLATFORM_COMPAT.md` at the repo root maps these to Codex CLI and generic equivalents. SKILL.md files should link to this mapping rather than duplicating it.

## Commit style

Conventional commits: `type(scope): message`. Scope is the plugin name. Types: `feat`, `fix`, `refactor`, `docs`, `chore`.

## Rules

### No virtual or meta plugins

A plugin MUST do what its name says. Do not create plugins that merely resolve to another provider, dispatch to built-in skills, or wrap installation instructions. If a skill depends on another skill, inline the resolution logic (a few lines checking availability and falling back) directly in its own SKILL.md.

### No wrapper abstractions for single consumers

If only one plugin needs a capability lookup, put the lookup in that plugin. Extract a shared abstraction only when three or more consumers exist.

### One source of truth per fact

- Plugin existence → `marketplace.json` + `plugins/<name>/` directory
- Plugin metadata → `plugin.json`
- Skill behavior → `SKILL.md`
- Platform mapping → `PLATFORM_COMPAT.md`

Do not scatter the same fact across files. If a description appears in both `plugin.json` and `SKILL.md`, the SKILL.md description is the agent-facing trigger text and may be longer; `plugin.json` is the short marketplace summary.

### Plugins must be self-contained

A plugin must not depend on another plugin in this repo existing at install time. Cross-plugin dependencies (like `paper-to-slides` using `overleaf-cleanup`) are runtime skill invocations, not install-time requirements — the SKILL.md documents what to check and how to fail gracefully if the dependency is missing.

### Keep SKILL.md platform-agnostic where possible

Use Claude Code tool names as the primary notation, reference `PLATFORM_COMPAT.md` for mapping, and avoid hardcoding paths like `~/.claude/skills/` in logic that other platforms need to follow.

### Sub-command naming convention

Plugins with multiple skills use **self-namespaced directory names** that match the SKILL.md `name` field. This follows the [Codex skill-creator convention](https://github.com/openai/skills/blob/main/skills/.system/skill-creator/SKILL.md) where the folder name equals the skill name, preventing filesystem collisions when skills are copied into Codex's flat `~/.codex/skills/` directory.

- **Directory:** `skills/<plugin>-<sub>/` — folder name = skill name
- **`name` field:** `<plugin>-<sub>` — same as directory, used by both platforms
- **Claude Code:** resolves as `/<plugin>:<plugin>-<sub>`
- **Codex:** `$<plugin>-<sub>`

Example: `plugins/brainstorm/skills/brainstorm-end/SKILL.md` with `name: brainstorm-end` → `/brainstorm:brainstorm-end` (Claude Code), `$brainstorm-end` (Codex).
