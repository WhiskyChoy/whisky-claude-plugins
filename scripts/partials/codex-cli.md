### OpenAI Codex CLI

This repo is organized as a Claude Code plugin marketplace, but each plugin's `SKILL.md` is compatible with Codex CLI. To use a skill in Codex:

**macOS / Linux (bash):**

```bash
# Copy the entire plugin directory (includes skills, tools, scripts, etc.)
cp -r plugins/<name> ~/codex-plugins/<name>

# Copy the skill into Codex's skill search path:
# User-level (available in all projects)
cp -r ~/codex-plugins/<name>/skills/<name> ~/.codex/skills/<name>

# Project-level (committed to repo)
cp -r plugins/<name>/skills/<name> .agents/skills/<name>
```

**Windows (PowerShell):**

```powershell
# Copy the entire plugin directory
Copy-Item -Recurse plugins\<name> ~\codex-plugins\<name>

# User-level
Copy-Item -Recurse ~\codex-plugins\<name>\skills\<name> ~\.codex\skills\<name>

# Project-level (committed to repo)
Copy-Item -Recurse plugins\<name>\skills\<name> .agents\skills\<name>
```

Some plugins bundle runnable code alongside the skill (in `tools/`, `scripts/`, `src/`, etc.). The SKILL.md for each plugin documents how to locate and run its bundled code — check the skill's setup instructions for specifics.

**Plugins with sub-commands** (e.g., `brainstorm` has `brainstorm-end` and `brainstorm-save`) store each sub-command as a separate SKILL.md under the plugin's `skills/` directory. Sub-command directories use **self-namespaced names** that match the SKILL.md `name` field (e.g., `brainstorm-end/` not `end/`), following the [Codex skill-creator convention](https://github.com/openai/skills/blob/main/skills/.system/skill-creator/SKILL.md). This prevents filesystem collisions when copying skills from multiple plugins into the same directory:

```bash
# Copy all skills from a plugin at once (includes sub-commands)
# Safe because each directory name is globally unique (e.g., brainstorm-end/, not end/)
cp -r plugins/<name>/skills/* ~/.codex/skills/
```

Skills marked **Partial** in the Compatibility column use Claude Code-specific tools. See [`PLATFORM_COMPAT.md`](PLATFORM_COMPAT.md) for the full tool mapping table (Claude Code → Codex → generic).
