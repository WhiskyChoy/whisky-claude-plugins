---
description: Configure the claude-statusline plugin as your active statusline
---

# Setup Claude Statusline

Configure the statusline in the user's Claude Code settings.

## Instructions

1. Read the user's `~/.claude/settings.json`
2. Set or update the `statusLine` field to:

```json
{
  "statusLine": {
    "type": "command",
    "command": "bash ${CLAUDE_PLUGIN_ROOT}/scripts/statusline.sh"
  }
}
```

If `${CLAUDE_PLUGIN_ROOT}` is not resolved at config time, use the plugin's actual install path from the installed_plugins.json cache path for `claude-statusline@whisky-claude-plugins`.

3. Write the updated settings back
4. Tell the user to restart Claude Code for the change to take effect

## Alternative: Python version

If the user prefers Python (no `jq` dependency), use:

```json
{
  "statusLine": {
    "type": "command",
    "command": "python ${CLAUDE_PLUGIN_ROOT}/scripts/statusline.py"
  }
}
```
