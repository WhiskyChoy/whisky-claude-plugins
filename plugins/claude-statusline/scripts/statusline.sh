#!/bin/bash

# --- Ensure jq is available (auto-install on Windows via winget) ---
if ! command -v jq &>/dev/null; then
    if [[ "$(uname -s)" == MINGW* || "$(uname -s)" == MSYS* || -n "$WINDIR" ]]; then
        powershell.exe -NoProfile -Command "winget install jqlang.jq --accept-source-agreements --accept-package-agreements" &>/dev/null
        # winget installs to a PATH that Git Bash doesn't see until re-login;
        # find the binary and use it directly for this session
        JQ="$(powershell.exe -NoProfile -Command "(Get-Command jq -ErrorAction SilentlyContinue).Source" 2>/dev/null | tr -d '\r')"
        if [ -z "$JQ" ]; then
            # fallback: common winget install location
            for p in "/c/Users/$USERNAME/AppData/Local/Microsoft/WinGet/Links/jq.exe" \
                     "/c/ProgramData/chocolatey/bin/jq.exe"; do
                if [ -f "$p" ]; then JQ="$p"; break; fi
            done
        fi
    else
        printf "\033[33mjq not found — install it with your package manager\033[0m"
    fi
fi
JQ="${JQ:-jq}"

input=$(cat)

# If jq is still unavailable, fall back to the Python version
if ! "$JQ" --version &>/dev/null; then
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    printf "%s" "$input" | python3 "$SCRIPT_DIR/statusline.py" 2>/dev/null \
        || printf "%s" "$input" | python "$SCRIPT_DIR/statusline.py" 2>/dev/null
    exit $?
fi

dir=$(echo "$input" | "$JQ" -r '.workspace.current_dir // .cwd // ""')
basename_dir=$(basename "$dir")

model=$(echo "$input" | "$JQ" -r '.model.display_name // ""')

used=$(echo "$input" | "$JQ" -r '.context_window.used_percentage // empty')

# ANSI colors
RESET=$'\033[0m'
BOLD_BLUE=$'\033[1;34m'
YELLOW=$'\033[33m'
GREEN=$'\033[32m'
RED=$'\033[31m'
DARK_GRAY=$'\033[90m'

# Build parts array
parts=()
parts+=("${BOLD_BLUE}📂 ${basename_dir}${RESET}")

if [ -n "$model" ]; then
    parts+=("${YELLOW}⚡ ${model}${RESET}")
fi

if [ -n "$used" ]; then
    pct=$(printf "%.0f" "$used")
    bar_width=15
    filled=$(awk "BEGIN {printf \"%d\", ($used * $bar_width / 100) + 0.5}")
    empty=$((bar_width - filled))

    if [ "$pct" -lt 50 ]; then
        bar_color="$GREEN"
    elif [ "$pct" -lt 80 ]; then
        bar_color="$YELLOW"
    else
        bar_color="$RED"
    fi

    filled_str=""
    for ((i=0; i<filled; i++)); do filled_str+="█"; done
    empty_str=""
    for ((i=0; i<empty; i++)); do empty_str+="░"; done

    parts+=(" ${bar_color}${filled_str}${DARK_GRAY}${empty_str}${RESET} ${pct}%")
fi

# Join parts with two spaces
result=""
for i in "${!parts[@]}"; do
    if [ "$i" -eq 0 ]; then
        result="${parts[$i]}"
    else
        result="${result}  ${parts[$i]}"
    fi
done

printf "%s" "$result"
