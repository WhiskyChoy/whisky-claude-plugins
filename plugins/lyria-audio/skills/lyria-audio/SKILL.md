---
name: lyria-audio
description: Generates AI music using Gemini Lyria (realtime streaming). Handles duration, BPM, brightness, density, scale, loop detection, and MP3/WAV output. Use when asked to "generate music", "create BGM", "make a soundtrack", "generate audio", or any music generation task.
---

# lyria-audio

AI music generation CLI. Powered by Gemini Lyria (realtime streaming).

## /init - First-Time Setup

When the user says "init", "setup lyria", or "install lyria-audio", run these commands. No sudo required.

**Prerequisites:** Bun must be installed. If not: `curl -fsSL https://bun.sh/install | bash`

```bash
# 1. Copy tool from plugin to ~/tools/lyria
cp -r "${CLAUDE_PLUGIN_ROOT}/tools" ~/tools/lyria

# 2. Install dependencies
cd ~/tools/lyria && bun install

# 3. Link globally (creates `lyria` command via Bun - no sudo)
cd ~/tools/lyria && bun link

# 4. Set up API key
mkdir -p ~/.lyria
echo "GEMINI_API_KEY=<ask user for their key>" > ~/.lyria/.env
```

After init, the user can type `lyria "prompt"` from anywhere.

If `bun link` fails or the command is not found after linking, fall back to:
```bash
mkdir -p ~/.local/bin
ln -sf ~/tools/lyria/src/cli.ts ~/.local/bin/lyria
# Then ensure ~/.local/bin is on PATH:
# macOS/Linux (zsh):
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc && source ~/.zshrc
# Windows (Git Bash):
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc && source ~/.bashrc
```

**Windows note:** On Windows with Git Bash, use the full Bun path instead of `bun`:
```bash
# Find your Bun path:
where bun  # (cmd) or: ls /c/Users/*/AppData/Local/Microsoft/WinGet/Packages/Oven-sh.Bun*/bun-windows-x64/bun.exe
# Then run directly:
/path/to/bun.exe run ~/tools/lyria/src/cli.ts "your prompt"
```

Get a Gemini API key at: https://aistudio.google.com/apikey

## Quick Reference

- Command: `lyria "prompt" [options]`
- Default: 30s duration, QUALITY mode

## Core Options

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

## Music Generation Modes

| Mode | Description |
|------|-------------|
| `QUALITY` | Default. Best audio fidelity and coherence |
| `DIVERSITY` | More variation and exploration in the output |
| `VOCALIZATION` | Generates vocal-like sounds and textures |

## Parameter Guide

### Brightness (0.0 - 1.0)
- `0.0` - Dark, somber, melancholic tones
- `0.5` - Neutral, balanced mood
- `1.0` - Bright, uplifting, cheerful tones

### Density (0.0 - 1.0)
- `0.0` - Sparse, ambient, minimal instrumentation
- `0.5` - Moderate arrangement
- `1.0` - Full, complex, layered instrumentation

### BPM (60 - 200)
- `60-80` - Slow, ambient, contemplative
- `90-120` - Moderate, walking pace, relaxed
- `120-150` - Energetic, driving
- `150-200` - Fast, intense, action-packed

### Guidance (0 - 6)
- `0` - Free generation, loosely follows prompt
- `3-4` - Balanced (default)
- `6` - Strict prompt adherence, less creative freedom

## Key Workflows

### Game BGM Loop

```bash
lyria "epic orchestral battle theme, fantasy RPG" --duration 60 --bpm 140 --density 0.8 -o battle-bgm
```

### Ambient / Background

```bash
lyria "mysterious dark ambient, ancient ruins" --duration 90 --brightness 0.2 --density 0.3 -o ambient
```

### Menu Music

```bash
lyria "calm hopeful piano melody, warm" --duration 45 --brightness 0.7 --bpm 90 -o menu
```

### Dramatic / Cinematic

```bash
lyria "intense cinematic orchestral, rising tension" --duration 30 --density 0.9 --guidance 5.0 -o cinematic
```

### Vocal Textures

```bash
lyria "ethereal choir, floating harmonies" --mode VOCALIZATION --duration 30 -o choir
```

### Reproducible Output

```bash
lyria "retro synthwave beat" --seed 42 --bpm 120 -o synthwave
```

## Cost Tracking

Every generation is logged to `~/.lyria/costs.json`. View summary:

```bash
lyria --costs
```

Lyria is free during the experimental preview period.

## API Key Setup

The CLI resolves the Gemini API key in this order:
1. `--api-key` flag
2. `GEMINI_API_KEY` environment variable
3. `.env` file in current directory
4. `.env` file next to the CLI script
5. `~/.lyria/.env`

Get a key at: https://aistudio.google.com/apikey
