---
name: switch-workspace
description: Prepare a session for resuming in a different working directory. Copies session state and gives the user a one-line command to exit and resume there.
user-invocable: true
arguments:
  - name: target_path
    description: "Absolute path to the target working directory"
    required: true
---

# Switch Workspace

Migrate the current session so it can be resumed from a different working directory.

## When to Activate

- User says "switch to", "move to", "continue in", "change directory to" another project
- User wants to keep conversation context but work in a different repo

## How It Works

Claude Code stores sessions under `~/.claude/projects/<encoded-cwd>/`. This skill:

1. Copies the current session file to the target project directory
2. Appends a context note about the directory change
3. Gives the user a one-line command to resume there

## Workflow

### Step 1: Validate Target

Verify the target directory exists:

```bash
test -d "<target_path>" && echo "OK" || echo "NOT FOUND"
```

If not found, ask the user to confirm or create it.

### Step 2: Resolve Paths

Determine the current session ID from the environment. The session ID is available as a UUID — check the `sessionId` field. If not directly available, find the most recently modified `.jsonl` file in the current project directory:

```bash
# Encode current cwd: replace / with -- , remove leading -- , replace : with empty
# On Windows (Git Bash), cwd like /d/GitProjects/foo becomes D--GitProjects-foo
# On Unix, /home/user/foo becomes -home-user-foo (leading dash)
CURRENT_CWD="$(pwd)"

# Determine the Claude projects base
CLAUDE_PROJECTS="$HOME/.claude/projects"

# Find current project dir by encoding the cwd
# The encoding rule: absolute path with separators replaced by -
# Windows: D:\Git\foo → D--Git-foo  (backslash and colon removed)
# Unix: /home/user/foo → -home-user-foo (forward slash → -)
# But in Git Bash on Windows, pwd gives /d/GitProjects/foo
# Claude Code encodes the WINDOWS path, so D:\GitProjects\foo → D--GitProjects-foo

# Easiest: just list project dirs and find the one matching cwd
CURRENT_PROJECT_DIR=$(ls -d "$CLAUDE_PROJECTS"/*/ 2>/dev/null | while read d; do
  dirname_base=$(basename "$d")
  # Quick check: does the dir basename loosely match our cwd?
  echo "$dirname_base"
done | head -1)
```

**Simpler approach** — just search for the most recent `.jsonl` across project dirs:

```bash
# Find the current session (most recently modified jsonl)
CURRENT_JSONL=$(find "$CLAUDE_PROJECTS" -name "*.jsonl" -newer /tmp -printf '%T@ %p\n' 2>/dev/null | sort -rn | head -1 | cut -d' ' -f2-)
```

On Windows (Git Bash) where `find -printf` may not work:

```bash
CURRENT_JSONL=$(find "$CLAUDE_PROJECTS" -name "*.jsonl" -type f 2>/dev/null | xargs ls -t 2>/dev/null | head -1)
```

Extract the session ID:

```bash
SESSION_ID=$(basename "$CURRENT_JSONL" .jsonl)
CURRENT_PROJECT=$(basename "$(dirname "$CURRENT_JSONL")")
```

### Step 3: Encode Target Path

Encode the target path into Claude Code's directory naming format:

```bash
# Convert target path to Claude's encoded format
# Windows path: D:\GitProjects\foo → D--GitProjects-foo
# Unix path: /home/user/foo → -home-user-foo
encode_path() {
  local p="$1"
  # Normalize: resolve to absolute, remove trailing slash
  p=$(cd "$p" && pwd -W 2>/dev/null || pwd)  # pwd -W gives Windows path on Git Bash
  # Replace :\ or : with nothing (Windows drive letter)
  p=$(echo "$p" | sed 's|:\\|/|g; s|:|/|g')
  # Replace / with -
  p=$(echo "$p" | sed 's|/|-|g')
  # Replace -- sequences (from empty segments) — keep them as --
  echo "$p"
}

TARGET_ENCODED=$(encode_path "<target_path>")
TARGET_PROJECT_DIR="$CLAUDE_PROJECTS/$TARGET_ENCODED"
```

### Step 4: Copy Session

```bash
# Create target project directory
mkdir -p "$TARGET_PROJECT_DIR"

# Copy the session JSONL
cp "$CURRENT_JSONL" "$TARGET_PROJECT_DIR/"

# Copy subagents directory if it exists
if [ -d "$(dirname "$CURRENT_JSONL")/$SESSION_ID" ]; then
  cp -r "$(dirname "$CURRENT_JSONL")/$SESSION_ID" "$TARGET_PROJECT_DIR/"
fi
```

### Step 5: Append Context Note

Append a user message to the copied JSONL that tells the model about the directory change:

```bash
# Get the last message UUID for parentUuid chaining
LAST_UUID=$(python3 -c "
import json, os
p = os.path.join('$TARGET_PROJECT_DIR', '$SESSION_ID.jsonl')
with open(p, encoding='utf-8') as f:
    lines = f.readlines()
last = json.loads(lines[-1])
print(last.get('uuid', ''))
" 2>/dev/null || echo "")

# Generate a new UUID
NEW_UUID=$(python3 -c "import uuid; print(uuid.uuid4())" 2>/dev/null || cat /proc/sys/kernel/random/uuid 2>/dev/null || echo "00000000-0000-0000-0000-000000000000")

# Append the context note
cat >> "$TARGET_PROJECT_DIR/$SESSION_ID.jsonl" << JSONEOF
{"parentUuid":"$LAST_UUID","isSidechain":false,"type":"user","message":{"role":"user","content":"[System note: This session was migrated from $CURRENT_CWD to <target_path>. The working directory is now <target_path>. File paths from earlier in this conversation may reference $CURRENT_CWD — adjust them to the new location as needed. The project context (CLAUDE.md, git status, etc.) now reflects <target_path>.]"},"uuid":"$NEW_UUID","userType":"external","timestamp":"$(date -u +%Y-%m-%dT%H:%M:%S.000Z)"}
JSONEOF
```

### Step 6: Tell the User

Print the one-liner for the user. Use the appropriate shell syntax based on platform:

**Unix / macOS / Linux / Git Bash:**
```
Session prepared for <target_path>.

To switch, run:
  /exit
  cd "<target_path>" && claude --resume <SESSION_ID> --fork-session
```

**PowerShell (if detected):**
```
Session prepared for <target_path>.

To switch, run:
  /exit
  cd "<target_path>"; claude --resume <SESSION_ID> --fork-session
```

Use `--fork-session` to create a new session ID in the target workspace, avoiding conflicts with the original session.

## Important Notes

- **This is a best-effort migration.** Claude Code may change its internal storage format in future versions.
- **Project-level memory** (`memory/` directory) is NOT copied — it belongs to the original project. The target workspace may have its own memory.
- **CLAUDE.md context** will change — the resumed session will load the target directory's CLAUDE.md, not the original one.
- **Git status** will reflect the target repo, not the source.
- **`--fork-session`** is recommended to avoid duplicate session IDs across project directories.
- The original session remains intact in the source project directory.

## Limitations

- Only works with Claude Code CLI (not Codex or other agents)
- Requires the session to be saved to disk (not using `--no-session-persistence`)
- The `cwd` fields embedded in historical progress records will still reference the old path — this is cosmetic and doesn't affect behavior
