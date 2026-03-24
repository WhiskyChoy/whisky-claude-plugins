#!/usr/bin/env bash
# Generate README.md from marketplace.json, plugin metadata, and partial files.
# Called by GitHub Actions on push — output goes to stdout.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MARKETPLACE="$REPO_ROOT/.claude-plugin/marketplace.json"
PARTIALS="$REPO_ROOT/scripts/partials"

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

| Plugin | Version | Compatibility | Description |
|--------|---------|---------------|-------------|
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
  version=$(awk -v pname="$name" '
    /"name":/ && $0 ~ "\"" pname "\"" { found=1 }
    found && /"version":/ { gsub(/.*"version": *"|".*/, ""); print; exit }
  ' "$MARKETPLACE")
  version="${version:-1.0.0}"

  # Build compatibility string from platforms object in plugin.json
  compat=""
  in_platforms=0
  while IFS= read -r line; do
    if echo "$line" | grep -q '"platforms"'; then
      in_platforms=1
      continue
    fi
    if [ "$in_platforms" -eq 1 ]; then
      if echo "$line" | grep -q '}'; then
        break
      fi
      plat=$(echo "$line" | grep -o '"[^"]*"' | head -1 | tr -d '"')
      level=$(echo "$line" | grep -o '"[^"]*"' | tail -1 | tr -d '"')
      if [ -n "$plat" ] && [ -n "$level" ]; then
        case "$level" in
          full)    label="$plat" ;;
          partial) label="$plat (partial)" ;;
          none)    continue ;;
          *)       label="$plat" ;;
        esac
        if [ -n "$compat" ]; then
          compat="$compat, $label"
        else
          compat="$label"
        fi
      fi
    fi
  done < "$plugin_json"
  compat="${compat:-—}"

  # Table row
  echo "| **$name** | $version | $compat | $desc |"

  # Install command
  install_cmds="${install_cmds}claude plugin install ${name}@whisky-claude-plugins
"

  # Detail section — extract info from SKILL.md if it exists
  # Prefer the main skill (directory matching plugin name), fall back to any SKILL.md
  skill_md="$plugin_dir/skills/$name/SKILL.md"
  [ -f "$skill_md" ] || skill_md=$(find "$plugin_dir" -name "SKILL.md" -type f 2>/dev/null | head -1)

  detail_body=""

  if [ -n "$skill_md" ] && [ -f "$skill_md" ]; then
    if grep -q "## Quick Reference" "$skill_md"; then
      quick_ref=$(sed -n '/^## Quick Reference$/,/^## /{/^## Quick Reference$/d;/^## /d;p}' "$skill_md")
      if [ -n "$quick_ref" ]; then
        detail_body="${detail_body}\n${quick_ref}\n"
      fi
    fi

    if grep -q "## Core Options" "$skill_md"; then
      options=$(sed -n '/^## Core Options$/,/^## /{/^## Core Options$/d;/^## /d;p}' "$skill_md")
      if [ -n "$options" ]; then
        detail_body="${detail_body}\n**Options:**\n${options}\n"
      fi
    fi
  fi

  if [ -d "$plugin_dir/scripts" ]; then
    scripts=$(ls "$plugin_dir/scripts/" 2>/dev/null | tr '\n' ', ' | sed 's/,$//')
    if [ -n "$scripts" ]; then
      detail_body="${detail_body}\n**Scripts:** $scripts\n"
    fi
  fi

  if [ -d "$plugin_dir/tools" ]; then
    detail_body="${detail_body}\n**Bundled CLI tool:** \`~/tools/${name}/\`\n"
  fi

  detail="<details>\n<summary><strong>${name}</strong> — ${desc}</summary>\n"
  if [ -n "$detail_body" ]; then
    detail="${detail}\n${detail_body}\n"
  else
    detail="${detail}\n*No additional details.*\n"
  fi
  detail="${detail}</details>\n"

  details="${details}\n$(echo -e "$detail")"
done

# ── Assemble output from partials and generated content ────────────────────

cat <<SECTION

## Installing Plugins

### Claude Code

\`\`\`bash
claude plugin marketplace add https://github.com/WhiskyChoy/whisky-claude-plugins
claude plugin install <name>@whisky-claude-plugins
\`\`\`

Or install individual plugins:

\`\`\`bash
$(echo "$install_cmds" | sed '/^$/d')
\`\`\`

SECTION

cat "$PARTIALS/codex-cli.md"
echo ""
cat "$PARTIALS/other-agents.md"

cat <<SECTION

## Plugin Details
$(echo -e "$details")
---

SECTION

cat "$PARTIALS/recommendations.md"

cat <<FOOTER

---

*This README is auto-generated from plugin metadata. Do not edit manually.*
FOOTER
