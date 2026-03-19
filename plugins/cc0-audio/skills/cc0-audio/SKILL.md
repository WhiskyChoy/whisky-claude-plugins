---
name: cc0-audio
description: Searches, downloads, and compresses CC0/free-license audio from Freesound and Pixabay. Handles search, preview, download, FFmpeg compression (BGM/voice presets), URL checking, and batch processing. Use when asked to "find music", "search for sound effects", "download CC0 audio", "compress audio", "check audio URLs", or any free audio sourcing task.
---

# cc0-audio

CC0 audio sourcing CLI. Search, download, and compress free-license audio from Freesound and Pixabay.

## /init - First-Time Setup

When the user says "init", "setup cc0-audio", or "install cc0-audio", run these commands. No sudo required.

**Prerequisites:** Bun and FFmpeg must be installed.

```bash
# 1. Copy tool from plugin to ~/tools/cc0-audio
cp -r "${CLAUDE_PLUGIN_ROOT}/tools" ~/tools/cc0-audio

# 2. Install dependencies
cd ~/tools/cc0-audio && bun install

# 3. Link globally (creates `cc0-audio` command via Bun - no sudo)
cd ~/tools/cc0-audio && bun link

# 4. Set up Freesound API key
mkdir -p ~/.cc0-audio
echo "FREESOUND_API_KEY=<ask user for their key>" > ~/.cc0-audio/.env
```

Get a free Freesound API key at: https://freesound.org/apiv2/apply

Verify FFmpeg is installed:

```bash
ffmpeg -version
```

**Windows note:** On Windows with Git Bash, if `bun link` doesn't work, run directly:
```bash
# Find your Bun path:
where bun  # (cmd) or: ls /c/Users/*/AppData/Local/Microsoft/WinGet/Packages/Oven-sh.Bun*/bun-windows-x64/bun.exe
# Then run directly:
/path/to/bun.exe run ~/tools/cc0-audio/src/cli.ts search "query"
```

## Quick Reference

```bash
cc0-audio search "dark ambient loop"          # Search Freesound (default)
cc0-audio search "battle theme" --source oga  # Search OpenGameArt
cc0-audio download 123456                     # Download by Freesound ID
cc0-audio download https://opengameart.org/content/battle-theme-a -o battle  # Download from OGA
cc0-audio compress input.wav --preset bgm     # Compress with BGM preset
cc0-audio check-urls "https://example.com/audio"  # Check URL reachability
cc0-audio batch manifest.json                 # Batch search + download + compress
```

## Subcommands

### `search <query>`

Search CC0 audio. Returns ID, title, duration, and preview URL.

| Option | Default | Description |
|---|---|---|
| `--source` | `freesound` | Source: `freesound`, `opengameart`/`oga` |
| `--duration` | - | Max duration in seconds |
| `--license` | `cc0` | License filter (`cc0`, `by`, `any`) |

```bash
cc0-audio search "sword clash" --duration 3
```

### `download <id-or-url>`

Download by Freesound ID, OpenGameArt content URL, or direct URL.
OGA downloads auto-print credit info (title, author, license).

| Option | Default | Description |
|---|---|---|
| `-o, --output` | auto | Output filename (no extension) |
| `-d, --dir` | cwd | Output directory |

```bash
cc0-audio download 654321 -o sword-hit -d ./audio
```

### `compress <input>`

FFmpeg compression with presets.

| Option | Default | Description |
|---|---|---|
| `--preset` | `bgm` | Preset: `bgm`, `voice`, or `custom` |
| `--duration` | - | Trim to N seconds |
| `--ffmpeg-args` | - | Custom FFmpeg args (with `--preset custom`) |
| `-o, --output` | auto | Output filename (no extension) |
| `-d, --dir` | cwd | Output directory |

```bash
cc0-audio compress battle-theme.wav --preset bgm -o battle-compressed
cc0-audio compress click.wav --preset voice --duration 1 -o ui-click
```

### `check-urls <base-url>`

Batch HEAD-request against audio URLs. Reports reachability and file sizes.

```bash
cc0-audio check-urls "https://cdn.example.com/audio"
```

### `batch <manifest.json>`

Automated pipeline: search, download, and compress in one step.

```bash
cc0-audio batch audio-manifest.json -d ./output
```

## Compression Presets

| Preset | Settings | Use Case |
|---|---|---|
| `bgm` | mono 44100Hz VBR q5 | Game BGM loops (~200KB/min) |
| `voice` | mono 22050Hz VBR q6 | Short voice cues (~15KB each) |
| `custom` | Pass-through to FFmpeg | Full control over FFmpeg args |

## Batch Manifest Format

A JSON array where each entry defines a search-download-compress pipeline:

```json
[
  { "query": "page turn book", "preset": "voice", "output": "page-turn", "duration": 1 },
  { "query": "ambient forest", "preset": "bgm", "output": "forest-bg", "duration": 60 }
]
```

## Credit & Attribution Tracking

**IMPORTANT:** After downloading audio, always record credits in the project's documentation.

### CC0 (Public Domain)
No attribution legally required, but good practice to record the source for auditability:
```markdown
| `output.mp3` | Track Title | Author | [Freesound #ID](https://freesound.org/people/author/sounds/ID/) (CC0) |
```

### CC-BY (Attribution Required)
**Must** credit the author visibly in the project. Include:
- Author name
- Original title
- Source URL
- License: "Licensed under CC-BY 4.0"

```markdown
| `output.mp3` | Track Title | AuthorName | [Freesound #ID](url) — [CC-BY 4.0](https://creativecommons.org/licenses/by/4.0/) |
```

### Best practice
- Always prefer CC0 (`--license cc0`) to avoid attribution obligations
- If using CC-BY, verify the specific version (3.0 vs 4.0) from the Freesound page
- Keep a credits table in the project README or a dedicated `CREDITS.md`
- Record Freesound IDs so sources are traceable even if URLs change

## API Key Setup

**Freesound**: Create `~/.cc0-audio/.env` with your API key:

```
FREESOUND_API_KEY=your_key_here
```

Get a free key at https://freesound.org/apiv2/apply

The CLI resolves the key in this order:
1. `--api-key` flag
2. `FREESOUND_API_KEY` environment variable
3. `.env` file in current directory
4. `.env` file next to the CLI script
5. `~/.cc0-audio/.env`
