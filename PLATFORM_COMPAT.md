# Cross-Platform Tool Mapping

Skills in this repo use Claude Code tool names by default. Other agents should map as follows:

## Tool Mapping

| Action | Claude Code | Codex CLI | Generic |
|--------|-------------|-----------|---------|
| Read files / PDFs | `Read` tool (native PDF + image support) | `cat` via shell; PDFs via `pdfplumber` or `pdftotext` | Read file by path |
| Edit files | `Edit` tool | `apply_patch` | Patch or sed |
| Write files | `Write` tool | `apply_patch` or shell redirect | Write file by path |
| Search file names | `Glob` tool | `find` or `fd` via shell | File search |
| Search file content | `Grep` tool | `rg` or `grep` via shell | Content search |
| Ask user a question | `AskUserQuestion` tool | Prompt the user in plain text | Interactive prompt |
| Invoke another skill | `Skill("name", "args")` | `$name args` | Invoke by name |
| Delegate to sub-agent | `Agent` tool | Sub-shell or separate session | Fork task |
| View images | `Read` tool (multimodal) | `view_image` tool or describe from context | Image viewer |
| Search the web | `WebSearch` tool | `web_search` or browser tool | Web search |
| Fetch a URL | `WebFetch` tool | `curl` via shell | HTTP GET |

## Script Path Resolution

Skills may bundle scripts alongside their SKILL.md. Determine the skill directory at runtime:

```bash
# Claude Code
SKILL_DIR="$HOME/.claude/skills/<skill-name>"

# Codex — find dynamically
SKILL_DIR="$(dirname "$(find ~ -path '*/<skill-name>/SKILL.md' -maxdepth 5 2>/dev/null | head -1)")"

# Generic — set manually
SKILL_DIR="/path/to/skills/<skill-name>"
```

## Compatibility Levels

Each plugin's `plugin.json` declares a `platforms` field:

| Level | Meaning |
|-------|---------|
| `full` | Works out of the box — uses only shell commands and standard tools |
| `partial` | Works with tool mapping — uses Claude Code-specific tools listed above |

Only supported platforms are listed. If a platform is absent from `platforms`, the plugin does not support it.
