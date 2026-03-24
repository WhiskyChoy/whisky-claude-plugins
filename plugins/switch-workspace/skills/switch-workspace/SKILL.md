---
name: switch-workspace
description: Prepare a session for resuming in a different working directory. Copies session state and gives the user a one-line command to exit and resume there.
user-invocable: true
arguments:
  - name: target_path
    description: "Absolute path to the target working directory. If not provided, list recent workspaces for the user to pick from."
    required: false
---

# Switch Workspace

Migrate the current session so it can be resumed from a different working directory.

## When to Activate

- User says "switch to", "move to", "continue in", "change directory to" another project
- User wants to keep conversation context but work in a different repo

## How It Works

Claude Code stores sessions under `~/.claude/projects/<encoded-cwd>/`. This skill copies the session file to a new project directory and gives the user a resume command.

## Bundled Script

A Python script implements the full algorithm below. If available, prefer using it:

```bash
# Locate the script (alongside this SKILL.md, up in tools/)
SCRIPT="$(dirname "$(find ~/.claude -path '*/switch-workspace/tools/switch_workspace.py' -maxdepth 6 2>/dev/null | head -1)")/switch_workspace.py"

# If installed as a plugin, try the plugin tools path
[ -z "$SCRIPT" ] && SCRIPT="$(find ~/.claude -path '*/switch-workspace/switch_workspace.py' -maxdepth 6 2>/dev/null | head -1)"

# Run it
python "$SCRIPT" "<target_path>"

# Or with explicit source cwd (if pwd doesn't match the project):
python "$SCRIPT" "<target_path>" --cwd "D:\GitProjects\sci-agent"
```

The script handles path encoding, session discovery, copying, and context note injection across Windows, macOS, and Linux. It prints the resume command to stderr and the session ID to stdout.

If the script is not available, follow the algorithm below manually.

## Algorithm

### 1. Resolve Target

**If `target_path` is provided:** confirm it exists and is a directory. If not, ask the user.

**If `target_path` is NOT provided:** list recent workspaces for the user to pick from.

The encoded project directory names under `~/.claude/projects/` can be decoded back to real paths by reversing the encoding rule (see step 2). List them sorted by most recent session activity (newest `.jsonl` modification time), exclude the current workspace, and present as a numbered list. Let the user pick one, or type a custom path.

The script supports this via `--list` flag, or automatically when no target is given.

### 2. Locate Current Session

Session files are at `~/.claude/projects/<encoded-cwd>/<session-id>.jsonl`.

**Encoding rule** — the directory name is the absolute path with separators replaced:
- On Windows: `D:\GitProjects\foo` → `D--GitProjects-foo` (drop the colon, replace `\` with `-`)
- On Unix: `/home/user/foo` → `-home-user-foo` (replace `/` with `-`)

Find the current project directory by encoding the current working directory, then find the most recently modified `.jsonl` inside it. Extract the session ID from the filename (strip `.jsonl`).

**Pitfall learned from testing:** Do NOT search for the most recent `.jsonl` globally across all project dirs — other sessions may be newer. Always scope to the current project's encoded directory.

### 3. Encode Target Path

Apply the same encoding rule to `<target_path>` to get the target project directory name.

**Pitfall learned from testing:** On Windows with Git Bash, `pwd` gives Unix-style paths like `/d/GitProjects/foo`, but Claude Code encodes the Windows path `D:\GitProjects\foo`. Use `pwd -W` (Git Bash) or equivalent to get the native OS path before encoding. On Unix, `pwd` already gives the native path.

### 4. Copy Session

- Create `~/.claude/projects/<target-encoded>/` if it doesn't exist
- Copy the `.jsonl` file there
- Copy the subagents directory (`<session-id>/`) if it exists alongside the JSONL

### 5. Append Context Note

Append one JSON line to the **copied** JSONL (not the original). It must be a valid message record:

```json
{
  "parentUuid": "<uuid of the last record in the file>",
  "isSidechain": false,
  "type": "user",
  "message": {
    "role": "user",
    "content": "[System note: This session was migrated from <source_path> to <target_path>. The working directory is now <target_path>. File paths from earlier in this conversation may reference <source_path> — adjust them to the new location as needed. The project context (CLAUDE.md, git status, etc.) now reflects <target_path>.]"
  },
  "uuid": "<new random uuid>",
  "userType": "external",
  "timestamp": "<current UTC timestamp in ISO 8601>"
}
```

Use Python to read the last line's UUID and generate a new UUID — this is cross-platform and avoids shell escaping issues with JSON.

### 6. Tell the User

Print the session ID and the resume command. The user needs to:
1. `/exit` the current session
2. `cd` to the target directory
3. Run `claude --resume <session-id> --fork-session`

`--fork-session` creates a new session ID in the target workspace, avoiding conflicts with the original.

## Re-running / Overwriting

Safe to re-run. The script copies a fresh snapshot of the source session each time, overwriting any previous copy in the target, then appends one context note. This means:

- **Same source → same target again:** overwrites cleanly, no duplicate notes
- **A → B, then B → C:** the migration chain is preserved (B's copy includes the A→B note, then a B→C note is appended — this is correct context)
- **The original session is never modified**

## Important Notes

- **Best-effort migration.** Claude Code may change its storage format in future versions.
- **Project-level memory** (`memory/` directory) is NOT copied — it belongs to the original project.
- **CLAUDE.md** will change — the resumed session loads the target directory's CLAUDE.md.
- **Git status** will reflect the target repo.
- The original session remains intact.

## Limitations

- Claude Code CLI only
- Requires session persistence (not using `--no-session-persistence`)
- Historical `cwd` fields in progress records still reference the old path (cosmetic only)
