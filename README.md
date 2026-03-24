# whisky-claude-plugins

Personal Claude Code plugin marketplace by WhiskyChoy

## Installation

```bash
claude plugin marketplace add https://github.com/WhiskyChoy/whisky-claude-plugins
```

## Plugins

| Plugin | Version | Codex | Description |
|--------|---------|-------|-------------|
| **audio-preview** | 1.0.0 | Yes | Zero-dependency local web server for comparing and picking audio files in a browser UI. |
| **brainstorm** | 1.0.0 | Partial | Technical design discussion mode — Socratic dialogue for algorithm, architecture, and design decisions. Produces implementation specs, not code. |
| **cc0-audio** | 1.0.0 | Yes | Search, download, and compress CC0/free-license audio from Freesound. Handles FFmpeg compression presets, URL checking, and batch processing. |
| **claude-statusline** | 1.0.0 | No | Minimal terminal statusline (directory, model, context bar). Setup recommends claude-hud for a full-featured alternative, then falls back to this. |
| **drawio** | 1.0.0 | Yes | Generate draw.io diagrams as .drawio files with auto-detection and portable install of the draw.io CLI. Exports to PNG/SVG/PDF with embedded XML. See NOTICE for upstream attribution. |
| **finalize-worktree** | 1.0.0 | Yes | Commit all worktree changes, sync from main branch, run tests, and merge back. Use when done working in a git worktree. |
| **frontend-slides** | 1.0.0 | Partial | [Virtual] Resolves to the best available HTML slide generation provider (ECC built-in or compatible plugin). Does not implement the capability itself. |
| **image-generation** | 1.0.0 | Yes | [Virtual] Resolves to the best available AI image generation CLI (nano-banana, etc.). For game assets, sprites, UI mockups, and marketing materials. |
| **lyria-audio** | 1.0.0 | Yes | AI music generation CLI powered by Gemini Lyria (realtime streaming). Handles duration, BPM, brightness, density, scale, and MP3/WAV output. |
| **overleaf-cleanup** | 1.0.0 | Partial | Clean LaTeX/Overleaf projects by removing unused files based on dependency analysis from the main .tex entry point. Accepts a zip file or an existing directory. |
| **paper-to-slides** | 1.0.0 | Partial | Convert academic papers (PDF, LaTeX, Overleaf) into polished HTML presentations with PPTX/PDF export. Supports multiple papers, style templates, screen-aware sizing, and logo injection. |

## Installing Plugins

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

## Plugin Details

### audio-preview

Zero-dependency local web server for comparing and picking audio files in a browser UI.


```bash
audio-preview ./audio/candidates/           # Preview all audio in directory
audio-preview track1.mp3 track2.ogg         # Preview specific files
audio-preview ./dir1/ ./dir2/ --port 9000   # Multiple dirs, custom port
```

**Bundled CLI tool:** `~/tools/audio-preview/`

### brainstorm

Technical design discussion mode — Socratic dialogue for algorithm, architecture, and design decisions. Produces implementation specs, not code.

### cc0-audio

Search, download, and compress CC0/free-license audio from Freesound. Handles FFmpeg compression presets, URL checking, and batch processing.


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

### claude-statusline

Minimal terminal statusline (directory, model, context bar). Setup recommends claude-hud for a full-featured alternative, then falls back to this.

**Scripts:** statusline.py,statusline.sh

### drawio

Generate draw.io diagrams as .drawio files with auto-detection and portable install of the draw.io CLI. Exports to PNG/SVG/PDF with embedded XML. See NOTICE for upstream attribution.

**Bundled CLI tool:** `~/tools/drawio/`

### finalize-worktree

Commit all worktree changes, sync from main branch, run tests, and merge back. Use when done working in a git worktree.

### frontend-slides

[Virtual] Resolves to the best available HTML slide generation provider (ECC built-in or compatible plugin). Does not implement the capability itself.

### image-generation

[Virtual] Resolves to the best available AI image generation CLI (nano-banana, etc.). For game assets, sprites, UI mockups, and marketing materials.

### lyria-audio

AI music generation CLI powered by Gemini Lyria (realtime streaming). Handles duration, BPM, brightness, density, scale, and MP3/WAV output.


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

### overleaf-cleanup

Clean LaTeX/Overleaf projects by removing unused files based on dependency analysis from the main .tex entry point. Accepts a zip file or an existing directory.

### paper-to-slides

Convert academic papers (PDF, LaTeX, Overleaf) into polished HTML presentations with PPTX/PDF export. Supports multiple papers, style templates, screen-aware sizing, and logo injection.
---

*This README is auto-generated from plugin metadata. Do not edit manually.*
