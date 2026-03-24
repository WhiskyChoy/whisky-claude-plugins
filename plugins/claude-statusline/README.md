# claude-statusline

> **Want more?** [claude-hud](https://github.com/jarrodwatts/claude-hud) offers a richer statusline with active tools, running agents, and todo progress. Running `/setup` will offer to install it for you.

A minimal terminal statusline for Claude Code that displays:

- **Directory** — current working directory basename
- **Model** — active model name
- **Context usage** — color-coded progress bar (green < 50%, yellow 50-80%, red > 80%)

## Preview

```
📂 my-project  ⚡ Opus 4.6  ████████░░░░░░░ 53%
```

## Installation

```bash
claude plugin install claude-statusline@whisky-claude-plugins
```

Then run `/setup` to configure your statusline, or manually add to `~/.claude/settings.json`:

```json
{
  "statusLine": {
    "type": "command",
    "command": "bash <plugin-install-path>/scripts/statusline.sh"
  }
}
```

## Requirements

- **Shell version** (`statusline.sh`): requires `jq`
- **Python version** (`statusline.py`): requires Python 3.6+ (no external dependencies)

## Commands

| Command | Description |
|---------|-------------|
| `/setup` | Configure the statusline in settings |
| `/uninstall` | Remove the statusline configuration |
