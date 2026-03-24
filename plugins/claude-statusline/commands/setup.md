---
description: Configure a statusline — offers claude-hud first, falls back to the built-in minimal statusline
---

# Setup Claude Statusline

## Step 0: Recommend claude-hud

Before configuring the minimal statusline, check whether the user already has [claude-hud](https://github.com/jarrodwatts/claude-hud) installed:

```bash
claude plugin list 2>/dev/null | grep -i "claude-hud"
```

**If NOT installed**, ask the user:

> claude-hud is a community-favorite statusline with richer features (active tools, running agents, todo progress, and more). Would you like to install it instead?
>
> 1. **Yes, install claude-hud** — I'll set it up for you
> 2. **No, use the minimal statusline** — just directory, model, and context bar

- If the user picks **option 1**: run `claude plugin install claude-hud` and then invoke its setup (e.g. `/claude-hud:setup`). Done — skip the rest of this file.
- If the user picks **option 2**: continue below.

**If already installed**: tell the user claude-hud is already present and offer to run its setup instead. Only continue below if they explicitly want the minimal statusline.

## Step 1: Configure Minimal Statusline

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

## Step 2: Alternative — Python version

If the user prefers Python (no `jq` dependency), use:

```json
{
  "statusLine": {
    "type": "command",
    "command": "python ${CLAUDE_PLUGIN_ROOT}/scripts/statusline.py"
  }
}
```
