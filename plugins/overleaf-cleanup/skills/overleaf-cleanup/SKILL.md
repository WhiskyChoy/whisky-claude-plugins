---
name: overleaf-cleanup
description: Clean LaTeX/Overleaf projects by removing unused files based on dependency analysis from the main .tex entry point. Accepts a zip file or an existing directory.
allowed_tools: ["Bash", "Read", "Write", "Glob", "Grep", "AskUserQuestion"]
arguments:
  - name: project_path
    description: Path to an Overleaf zip file OR an existing project directory containing .tex files
    required: false
  - name: main_tex
    description: Main .tex entry point filename (relative to project root)
    required: false
---

# Overleaf Cleanup

Remove all files not referenced (directly or transitively) from the main `.tex` entry point in a LaTeX project. Works with both zip downloads and existing directories.

## When to Activate

- User says "clean overleaf", "simplify overleaf zip", "remove unused tex files"
- User has a zip downloaded from Overleaf and wants to trim it
- User wants to find unused files in a LaTeX project directory
- User points to a directory containing `.tex` files

## Usage

```
/overleaf-cleanup                              # Interactive — asks for project path and main tex
/overleaf-cleanup myproject.zip                # Zip file, auto-detect main tex
/overleaf-cleanup myproject.zip main.tex       # Zip file with entry point
/overleaf-cleanup ./my-latex-project           # Existing directory
/overleaf-cleanup ./my-latex-project main.tex  # Directory with entry point
```

## Platform Compatibility

This skill works with **Claude Code CLI** and **OpenAI Codex CLI**. See `paper-to-slides/SKILL.md → Platform Compatibility` for the full tool mapping table.

**Script path** — determine once per session:
```bash
# Claude Code
SKILL_DIR="$HOME/.claude/skills/overleaf-cleanup"
# Codex — find dynamically
SKILL_DIR="$(dirname "$(find ~ -path '*/overleaf-cleanup/SKILL.md' -maxdepth 5 2>/dev/null | head -1)")"
```

## Workflow

### Step 1: Locate the Project

Determine whether `project_path` is a zip file, a directory, or not provided.

- **If `project_path` is a `.zip` file**: proceed to Step 2a (unzip).
- **If `project_path` is a directory**: use it directly as `WORK_DIR`, skip to Step 3.
- **If NOT provided**: search the current directory and common download locations for `.zip` files and directories containing `.tex` files. Ask the user to select from candidates:
  - List any `.zip` files found as options.
  - List any directories containing `.tex` files as options.
  - Include an "Other" option for the user to type a custom path.
  - If the path the user selects is a directory, skip to Step 3.
  - If the path is a `.zip` file, proceed to Step 2a.

### Step 2a: Unzip (zip file only)

```bash
# Create a working directory next to the zip
WORK_DIR="${ZIP_PATH%.zip}"
mkdir -p "$WORK_DIR"
unzip -o "$ZIP_PATH" -d "$WORK_DIR"
```

### Step 3: Determine Main Entry Point

The main `.tex` file **must** be confirmed by the user. Never assume silently.

- **If provided by the user** (e.g., via arguments): use it directly.
- **If NOT provided**: scan for candidates that contain `\documentclass`:
  ```bash
  grep -rl "\\\\documentclass" "$WORK_DIR" --include="*.tex"
  ```
  **Rank candidates by document length** (line count or byte size). The longest `.tex` file containing `\documentclass` is almost always the true main entry point — short files with `\documentclass` are typically standalone examples, cover pages, or appendices. When presenting candidates, sort them by length (descending) and annotate each with its line count.

  Then present the candidates and let the user select one.
  - If **one candidate** found: present it for confirmation (do not auto-select).
  - If **multiple candidates** found: list them all as options (longest first, with line counts shown), and mark the longest as "(Recommended)".
  - If **no candidates** found: ask the user to type the main `.tex` filename manually.

### Step 4: Run Dependency Analysis

The Python cleanup script lives alongside this SKILL.md. Run it directly — do NOT copy it into the project directory.

```bash
SCRIPT="$SKILL_DIR/overleaf_cleanup.py"
python "$SCRIPT" "$WORK_DIR" --main "main.tex"
```

The script will:
1. Parse the main `.tex` file
2. Recursively follow `\input`, `\include`, `\includegraphics`, `\bibliography`, `\addbibresource`, `\usepackage` (local `.sty`), `\lstinputlisting`, `\verbatiminput`, and `\import` commands
3. Collect all referenced files (with extension resolution)
4. Identify unreferenced files

### Step 5: Report & Confirm Deletion

1. Show the dry-run summary to the user (total files, referenced, artifacts, unused)
2. Ask the user to confirm before running with `--delete`

```bash
python "$SCRIPT" "$WORK_DIR" --main "main.tex" --delete
```

### Step 6: Ask Whether to Remove the Original Zip

**Only if the input was a zip file.** Skip this step for directory inputs.

After cleanup is complete, ask the user:

```
Question: "Remove the original zip file (<zip_filename>)?"
Options:
  - "Yes, delete it" — "The project has been extracted and cleaned; the zip is no longer needed"
  - "No, keep it" — "Keep the original zip as a backup"
```

If the user chooses to delete, remove the zip file:
```bash
rm "$ZIP_PATH"
```

## Important Notes

- The script handles **recursive** `\input`/`\include` chains
- It resolves relative paths from the including file's directory
- `.cls`, `.bst`, `.def` files are kept by default (often implicitly loaded)
- Build artifacts (`.aux`, `.log`, `.synctex.gz`, etc.) are always removed
- Use `--dry-run` first (default) to preview, then `--delete` to act
- The `--extra` flag allows specifying additional entry points for multi-document projects

## Python Script Location

The cleanup script lives alongside this SKILL.md. On Claude Code: `~/.claude/skills/overleaf-cleanup/overleaf_cleanup.py`. Set `SKILL_DIR` (see Platform Compatibility) and run from there — do NOT copy it into the project directory.

## Execution Procedure

When the user activates this skill:

1. Run `python "$SKILL_DIR/overleaf_cleanup.py"` with `--dry-run` (default) and show results to user
2. Ask user to confirm before running with `--delete`
3. If input was a zip file, ask whether to remove the original zip (Step 6)
4. Report final file count and saved space
