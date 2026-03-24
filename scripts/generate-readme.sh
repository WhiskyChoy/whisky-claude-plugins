#!/usr/bin/env bash
# Generate README.md from marketplace.json and plugin metadata.
# Called by GitHub Actions on push — output goes to stdout.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MARKETPLACE="$REPO_ROOT/.claude-plugin/marketplace.json"

# ── Parse marketplace.json with portable tools (no jq dependency) ──────────

# Extract marketplace name and description
marketplace_name=$(grep -o '"name": *"[^"]*"' "$MARKETPLACE" | head -1 | sed 's/.*: *"//;s/"//')
marketplace_desc=$(grep -o '"description": *"[^"]*"' "$MARKETPLACE" | head -1 | sed 's/.*: *"//;s/"//')

cat <<HEADER
# $marketplace_name

$marketplace_desc

## Installation

\`\`\`bash
claude plugin marketplace add https://github.com/WhiskyChoy/whisky-claude-plugins
\`\`\`

## Plugins

| Plugin | Version | Codex | Description |
|--------|---------|-------|-------------|
HEADER

# ── Build plugin table and detail sections ─────────────────────────────────

details=""
install_cmds=""

for plugin_dir in "$REPO_ROOT"/plugins/*/; do
  [ -d "$plugin_dir" ] || continue

  plugin_json="$plugin_dir/.claude-plugin/plugin.json"
  [ -f "$plugin_json" ] || continue

  name=$(grep -o '"name": *"[^"]*"' "$plugin_json" | head -1 | sed 's/.*: *"//;s/"//')
  desc=$(grep -o '"description": *"[^"]*"' "$plugin_json" | head -1 | sed 's/.*: *"//;s/"//')

  # Get version from marketplace.json for this plugin
  # Use awk to find the plugin block and extract version
  version=$(awk -v pname="$name" '
    /"name":/ && $0 ~ "\"" pname "\"" { found=1 }
    found && /"version":/ { gsub(/.*"version": *"|".*/, ""); print; exit }
  ' "$MARKETPLACE")
  version="${version:-1.0.0}"

  # Extract codex compatibility from plugin.json
  codex_compat=$(grep -A1 '"codex"' "$plugin_json" 2>/dev/null | grep -o '"[^"]*"' | tail -1 | tr -d '"')
  case "$codex_compat" in
    full)    codex_badge="Yes" ;;
    partial) codex_badge="Partial" ;;
    none)    codex_badge="No" ;;
    *)       codex_badge="—" ;;
  esac

  # Table row
  echo "| **$name** | $version | $codex_badge | $desc |"

  # Install command
  install_cmds="${install_cmds}claude plugin install ${name}@whisky-claude-plugins
"

  # Detail section — extract info from SKILL.md if it exists
  skill_md=$(find "$plugin_dir" -name "SKILL.md" -type f 2>/dev/null | head -1)

  detail="### $name\n\n$desc\n"

  if [ -n "$skill_md" ] && [ -f "$skill_md" ]; then
    # Check if it has a Quick Reference section
    if grep -q "## Quick Reference" "$skill_md"; then
      # Extract Quick Reference content (between ## Quick Reference and next ##)
      quick_ref=$(sed -n '/^## Quick Reference$/,/^## /{/^## Quick Reference$/d;/^## /d;p}' "$skill_md")
      if [ -n "$quick_ref" ]; then
        detail="${detail}\n${quick_ref}\n"
      fi
    fi

    # Check for Core Options table
    if grep -q "## Core Options" "$skill_md"; then
      options=$(sed -n '/^## Core Options$/,/^## /{/^## Core Options$/d;/^## /d;p}' "$skill_md")
      if [ -n "$options" ]; then
        detail="${detail}\n**Options:**\n${options}\n"
      fi
    fi

    # Check for Subcommands section
    if grep -q "## Subcommands" "$skill_md" || grep -q "## Quick Reference" "$skill_md"; then
      : # Already captured above
    fi
  fi

  # Check for scripts/ directory (like statusline)
  if [ -d "$plugin_dir/scripts" ]; then
    scripts=$(ls "$plugin_dir/scripts/" 2>/dev/null | tr '\n' ', ' | sed 's/,$//')
    if [ -n "$scripts" ]; then
      detail="${detail}\n**Scripts:** $scripts\n"
    fi
  fi

  # Check for tools/ directory
  if [ -d "$plugin_dir/tools" ]; then
    detail="${detail}\n**Bundled CLI tool:** \`~/tools/${name}/\`\n"
  fi

  details="${details}\n$(echo -e "$detail")\n"
done

cat <<SECTION

## Installing Plugins

\`\`\`bash
$(echo "$install_cmds" | sed '/^$/d')
\`\`\`

## Plugin Details
$(echo -e "$details")
---

*This README is auto-generated from plugin metadata. Do not edit manually.*
SECTION
