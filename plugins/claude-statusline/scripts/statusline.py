import json, sys

data = json.load(sys.stdin)

# --- Directory ---
dir_path = data.get("workspace", {}).get("current_dir") or data.get("cwd", "")
basename = dir_path.replace("\\", "/").rstrip("/").rsplit("/", 1)[-1] if dir_path else ""

# --- Model ---
model = data.get("model", {}).get("display_name", "")

# --- Context progress bar ---
used = data.get("context_window", {}).get("used_percentage")
if used is not None:
    pct = int(used)
    bar_width = 15
    filled = round(bar_width * used / 100)
    empty = bar_width - filled
    # Color: green < 50%, yellow 50-80%, red > 80%
    if pct < 50:
        bar_color = "\033[32m"   # green
    elif pct < 80:
        bar_color = "\033[33m"   # yellow
    else:
        bar_color = "\033[31m"   # red
    bar = f"{bar_color}{'█' * filled}\033[90m{'░' * empty}\033[0m"
    ctx = f" {bar} \033[0m{pct}%"
else:
    ctx = ""

# --- Assemble ---
# 📂 dir  ⚡ model  [████░░░░] 42%
parts = []
parts.append(f"\033[1;34m📂 {basename}\033[0m")
if model:
    parts.append(f"\033[33m⚡ {model}\033[0m")
if ctx:
    parts.append(ctx)

print("  ".join(parts), end="")
