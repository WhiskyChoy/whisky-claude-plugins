---
name: audio-preview
description: Zero-dependency local web server for comparing and picking audio files. Opens a browser UI with play/pause controls and a pick button. Use when asked to "preview audio", "compare tracks", "listen to candidates", "pick a track", or any audio comparison task.
---

# audio-preview

Zero-dependency local web server for comparing and picking audio files in a browser UI.

## /init - First-Time Setup

```bash
# 1. Copy tool from plugin to ~/tools/audio-preview
cp -r "${CLAUDE_PLUGIN_ROOT}/tools" ~/tools/audio-preview

# 2. Link globally (no dependencies to install)
cd ~/tools/audio-preview && bun link
```

No npm dependencies. No FFmpeg. Just Bun's built-in HTTP server.

**Windows note:** If `bun link` doesn't work, run directly:
```bash
/path/to/bun.exe run ~/tools/audio-preview/src/cli.ts ./audio/
```

## Quick Reference

```bash
audio-preview ./audio/candidates/           # Preview all audio in directory
audio-preview track1.mp3 track2.ogg         # Preview specific files
audio-preview ./dir1/ ./dir2/ --port 9000   # Multiple dirs, custom port
```

## Options

| Option | Default | Description |
|--------|---------|-------------|
| `-p, --port` | `8111` | Server port |
| `-d, --dir` | — | Add a directory (repeatable) |
| `-h, --help` | — | Show help |

## Supported Formats

mp3, ogg, wav, flac, m4a, aac, webm

## How It Works

1. Scans the given directories/files for audio
2. Starts a local HTTP server (Bun built-in, no deps)
3. Opens browser with a dark-themed comparison UI
4. Each track has Play/Pause and Pick buttons
5. Clicking Pick logs the selection to the terminal
6. Press Ctrl+C to stop

## Integration with Other Skills

Works alongside `lyria-audio` and `cc0-audio`:

```bash
# Generate candidates with lyria
lyria "victory fanfare" -o candidate-1 -d ./candidates/
lyria "triumph theme" -o candidate-2 -d ./candidates/

# Source candidates with cc0-audio
cc0-audio download https://opengameart.org/content/victory -o candidate-3 -d ./candidates/

# Compare and pick
audio-preview ./candidates/
```
