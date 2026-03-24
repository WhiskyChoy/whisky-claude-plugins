# whisky-claude-plugins

Personal plugin marketplace by WhiskyChoy. Organized for Claude Code, with cross-platform SKILL.md compatibility (Codex CLI, and other agents).

## Installation

```bash
claude plugin marketplace add https://github.com/WhiskyChoy/whisky-claude-plugins
```

## Plugins

| Plugin | Version | Compatibility | Description |
|--------|---------|---------------|-------------|
| **audio-preview** | 1.0.0 | claude-code, codex | Zero-dependency local web server for comparing and picking audio files in a browser UI. |
| **brainstorm** | 1.0.0 | claude-code, codex (partial) | Technical design discussion mode — Socratic dialogue for algorithm, architecture, and design decisions. Produces implementation specs, not code. |
| **cc0-audio** | 1.0.0 | claude-code, codex | Search, download, and compress CC0/free-license audio from Freesound. Handles FFmpeg compression presets, URL checking, and batch processing. |
| **claude-statusline** | 1.0.0 | claude-code | Minimal terminal statusline (directory, model, context bar). Setup recommends claude-hud for a full-featured alternative, then falls back to this. |
| **drawio** | 1.0.0 | claude-code, codex | Generate draw.io diagrams as .drawio files with auto-detection and portable install of the draw.io CLI. Exports to PNG/SVG/PDF with embedded XML. See NOTICE for upstream attribution. |
| **finalize-worktree** | 1.0.0 | claude-code, codex | Commit all worktree changes, sync from main branch, run tests, and merge back. Use when done working in a git worktree. |
| **frontend-slides** | 1.0.0 | claude-code, codex (partial) | [Virtual] Resolves to the best available HTML slide generation provider (ECC built-in or compatible plugin). Does not implement the capability itself. |
| **image-generation** | 1.0.0 | claude-code, codex | [Virtual] Resolves to the best available AI image generation CLI (nano-banana, etc.). For game assets, sprites, UI mockups, and marketing materials. |
| **lyria-audio** | 1.0.0 | claude-code, codex | AI music generation CLI powered by Gemini Lyria (realtime streaming). Handles duration, BPM, brightness, density, scale, and MP3/WAV output. |
| **overleaf-cleanup** | 1.0.0 | claude-code, codex (partial) | Clean LaTeX/Overleaf projects by removing unused files based on dependency analysis from the main .tex entry point. Accepts a zip file or an existing directory. |
| **paper-to-slides** | 1.0.0 | claude-code, codex (partial) | Convert academic papers (PDF, LaTeX, Overleaf) into polished HTML presentations with PPTX/PDF export. Supports multiple papers, style templates, screen-aware sizing, and logo injection. |

## Installing Plugins

### Claude Code

```bash
claude plugin marketplace add https://github.com/WhiskyChoy/whisky-claude-plugins
claude plugin install <name>@whisky-claude-plugins
```

Or install individual plugins:

```bash
claude plugin install audio-preview@whisky-claude-plugins
claude plugin install brainstorm@whisky-claude-plugins
claude plugin install cc0-audio@whisky-claude-plugins
claude plugin install claude-statusline@whisky-claude-plugins
claude plugin install drawio@whisky-claude-plugins
claude plugin install finalize-worktree@whisky-claude-plugins
claude plugin install frontend-slides@whisky-claude-plugins
claude plugin install image-generation@whisky-claude-plugins
claude plugin install lyria-audio@whisky-claude-plugins
claude plugin install overleaf-cleanup@whisky-claude-plugins
claude plugin install paper-to-slides@whisky-claude-plugins
```

### OpenAI Codex CLI

This repo is organized as a Claude Code plugin marketplace, but each plugin's `SKILL.md` is compatible with Codex CLI. To use a skill in Codex, copy its skill directory to your Codex skills location:

```bash
# User-level (available in all projects)
cp -r plugins/<name>/skills/<name> ~/.codex/skills/<name>

# Project-level (committed to repo)
cp -r plugins/<name>/skills/<name> .agents/skills/<name>
```

For plugins with bundled tools (e.g. `drawio`, `cc0-audio`), also copy the `tools/` directory:

```bash
cp -r plugins/<name>/tools ~/tools/<name>
```

Skills marked **Partial** in the Compatibility column use Claude Code-specific tools. See [`PLATFORM_COMPAT.md`](PLATFORM_COMPAT.md) for the full tool mapping table (Claude Code → Codex → generic).

### Other Agents

Any agent that reads SKILL.md files (with YAML frontmatter `name` + `description`) can use these skills. Copy the skill directory to your agent's skill search path.

## Plugin Details

<details>
<summary><strong>audio-preview</strong> — Zero-dependency local web server for comparing and picking audio files in a browser UI.</summary>



```bash
audio-preview ./audio/candidates/           # Preview all audio in directory
audio-preview track1.mp3 track2.ogg         # Preview specific files
audio-preview ./dir1/ ./dir2/ --port 9000   # Multiple dirs, custom port
```

**Bundled CLI tool:** `~/tools/audio-preview/`

</details>
<details>
<summary><strong>brainstorm</strong> — Technical design discussion mode — Socratic dialogue for algorithm, architecture, and design decisions. Produces implementation specs, not code.</summary>

*No additional details.*
</details>
<details>
<summary><strong>cc0-audio</strong> — Search, download, and compress CC0/free-license audio from Freesound. Handles FFmpeg compression presets, URL checking, and batch processing.</summary>



```bash
cc0-audio search "dark ambient loop"          # Search Freesound (default)
cc0-audio search "battle theme" --source oga  # Search OpenGameArt
cc0-audio download 123456                     # Download by Freesound ID
cc0-audio download https://opengameart.org/content/battle-theme-a -o battle  # Download from OGA
cc0-audio compress input.wav --preset bgm     # Compress with BGM preset
cc0-audio check-urls "https://example.com/audio"  # Check URL reachability
cc0-audio batch manifest.json                 # Batch search + download + compress
```

**Bundled CLI tool:** `~/tools/cc0-audio/`

</details>
<details>
<summary><strong>claude-statusline</strong> — Minimal terminal statusline (directory, model, context bar). Setup recommends claude-hud for a full-featured alternative, then falls back to this.</summary>


**Scripts:** statusline.py,statusline.sh

</details>
<details>
<summary><strong>drawio</strong> — Generate draw.io diagrams as .drawio files with auto-detection and portable install of the draw.io CLI. Exports to PNG/SVG/PDF with embedded XML. See NOTICE for upstream attribution.</summary>


**Bundled CLI tool:** `~/tools/drawio/`

</details>
<details>
<summary><strong>finalize-worktree</strong> — Commit all worktree changes, sync from main branch, run tests, and merge back. Use when done working in a git worktree.</summary>

*No additional details.*
</details>
<details>
<summary><strong>frontend-slides</strong> — [Virtual] Resolves to the best available HTML slide generation provider (ECC built-in or compatible plugin). Does not implement the capability itself.</summary>

*No additional details.*
</details>
<details>
<summary><strong>image-generation</strong> — [Virtual] Resolves to the best available AI image generation CLI (nano-banana, etc.). For game assets, sprites, UI mockups, and marketing materials.</summary>

*No additional details.*
</details>
<details>
<summary><strong>lyria-audio</strong> — AI music generation CLI powered by Gemini Lyria (realtime streaming). Handles duration, BPM, brightness, density, scale, and MP3/WAV output.</summary>



- Command: `lyria "prompt" [options]`
- Default: 30s duration, QUALITY mode

**Options:**

| Option | Default | Description |
|--------|---------|-------------|
| `-o, --output` | `lyria-{timestamp}` | Output filename (no extension) |
| `-d, --dir` | current directory | Output directory |
| `--duration` | `30` | Duration in seconds |
| `--bpm` | auto | Beats per minute (60-200) |
| `--brightness` | auto | Tonal brightness: 0.0 (dark) to 1.0 (bright) |
| `--density` | auto | Arrangement density: 0.0 (sparse) to 1.0 (full) |
| `--guidance` | `4.0` | Prompt adherence: 0 (free) to 6 (strict) |
| `--temperature` | `1.1` | Generation randomness |
| `--scale` | auto | Musical key: C_MAJOR, A_MINOR, etc. |
| `--mode` | `QUALITY` | Generation mode: QUALITY, DIVERSITY, VOCALIZATION |
| `--format` | `mp3` | Output format: `mp3` or `wav` |
| `--seed` | random | Seed for reproducible output |
| `--no-loop` | - | Disable loop-point detection |
| `--api-key` | - | Gemini API key (overrides env/file) |
| `--costs` | - | Show cost summary |

**Bundled CLI tool:** `~/tools/lyria-audio/`

</details>
<details>
<summary><strong>overleaf-cleanup</strong> — Clean LaTeX/Overleaf projects by removing unused files based on dependency analysis from the main .tex entry point. Accepts a zip file or an existing directory.</summary>

*No additional details.*
</details>
<details>
<summary><strong>paper-to-slides</strong> — Convert academic papers (PDF, LaTeX, Overleaf) into polished HTML presentations with PPTX/PDF export. Supports multiple papers, style templates, screen-aware sizing, and logo injection.</summary>

*No additional details.*
</details>
---

*This README is auto-generated from plugin metadata. Do not edit manually.*
