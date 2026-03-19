# whisky-claude-plugins

Personal Claude Code plugin marketplace by WhiskyChoy

## Installation

```bash
claude plugin marketplace add https://github.com/WhiskyChoy/whisky-claude-plugins
```

## Plugins

| Plugin | Version | Description |
|--------|---------|-------------|
| **cc0-audio** | 1.0.0 | Search, download, and compress CC0/free-license audio from Freesound. Handles FFmpeg compression presets, URL checking, and batch processing. |
| **claude-statusline** | 1.0.0 | Custom terminal statusline showing directory, model, and context usage with a color-coded progress bar. |
| **finalize-worktree** | 1.0.0 | Commit all worktree changes, sync from main branch, run tests, and merge back. Use when done working in a git worktree. |
| **lyria-audio** | 1.0.0 | AI music generation CLI powered by Gemini Lyria (realtime streaming). Handles duration, BPM, brightness, density, scale, and MP3/WAV output. |

## Installing Plugins

```bash
claude plugin install cc0-audio@whisky-claude-plugins
claude plugin install claude-statusline@whisky-claude-plugins
claude plugin install finalize-worktree@whisky-claude-plugins
claude plugin install lyria-audio@whisky-claude-plugins
```

## Plugin Details

### cc0-audio

Search, download, and compress CC0/free-license audio from Freesound. Handles FFmpeg compression presets, URL checking, and batch processing.


```bash
cc0-audio search "dark ambient loop"          # Search for CC0 audio
cc0-audio download 123456                     # Download by Freesound ID
cc0-audio download "https://..."              # Download by direct URL
cc0-audio compress input.wav --preset bgm     # Compress with BGM preset
cc0-audio check-urls "https://example.com/audio"  # Check URL reachability
cc0-audio batch manifest.json                 # Batch search + download + compress
```

**Bundled CLI tool:** `~/tools/cc0-audio/`

### claude-statusline

Custom terminal statusline showing directory, model, and context usage with a color-coded progress bar.

**Scripts:** statusline.py,statusline.sh

### finalize-worktree

Commit all worktree changes, sync from main branch, run tests, and merge back. Use when done working in a git worktree.

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
---

*This README is auto-generated from plugin metadata. Do not edit manually.*
