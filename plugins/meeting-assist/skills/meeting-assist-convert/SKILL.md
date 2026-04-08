---
name: meeting-assist-convert
description: >-
  Convert raw meeting recordings (mp3, mp4, m4a, etc.) to unified 16kHz mono
  WAV files with date-normalized filenames using ffmpeg. Invocable as
  /meeting-assist:meeting-assist-convert (Claude Code) or
  $meeting-assist-convert (Codex).
user-invocable: true
allowed_tools:
  - Bash
  - Glob
arguments:
  - name: raw_dir
    description: "Path to raw recordings directory (default: raw/)"
    required: false
  - name: unified_dir
    description: "Path to unified output directory (default: unified/)"
    required: false
---

# Meeting Assist — Convert

See [`PLATFORM_COMPAT.md`](https://github.com/WhiskyChoy/whisky-claude-plugins/blob/master/PLATFORM_COMPAT.md) for the full cross-platform tool mapping.

## Purpose

Extract audio from raw meeting recordings and convert to a unified format (16kHz mono MP3) with date-normalized filenames, suitable for downstream ASR processing.

## Prerequisites

All dependencies are documented in the main `/meeting-assist` skill. Quick verify for this step:

```bash
ffmpeg -version 2>/dev/null | head -1
```

## Input

Scan `<raw_dir>` (default: `raw/`) for media files with these extensions:
`.mp3`, `.mp4`, `.m4a`, `.mp3`, `.flac`, `.ogg`, `.webm`, `.mkv`, `.avi`, `.mov`, `.wma`, `.aac`

## Output

`<unified_dir>/audio/<date-normalized>.mp3` — 16kHz mono MP3

## Algorithm

### Step 1: Scan raw files

```bash
# List all media files in raw_dir
ls raw/*.{mp3,mp4,m4a,wav,flac,ogg,webm,mkv,avi,mov,wma,aac} 2>/dev/null
```

### Step 2: Date normalization

Extract date/time from filename → normalize to `YYYY-MM-DD_HHMMSS`:

| Pattern | Example | Result |
|---------|---------|--------|
| `YYYY.MM.DD_HH.MM` | `2026.03.27_14.06.mp4` | `2026-03-27_140600` |
| `YYYYMMDD_HHMMSS` | `20260306_140525.m4a` | `2026-03-06_140525` |
| `YYYY-MM-DD_HHMMSS` | `2026-03-06_140525.mp3` | `2026-03-06_140525` |
| `YYYY-MM-DD_HH-MM-SS` | `2026-03-06_14-05-25.mp3` | `2026-03-06_140525` |
| `YYYYMMDD` (no time) | `20260306.m4a` | `2026-03-06_000000` |
| `YYYY.MM.DD` (no time) | `2026.03.06.mp4` | `2026-03-06_000000` |

**Fallback**: If no date pattern matches, use the file's last-modified timestamp.

**Collision handling**: If two files produce the same normalized name, append `_2`, `_3`, etc.

### Step 3: Convert

For each file, run:

```bash
ffmpeg -i "<input>" -ar 16000 -ac 1 -b:a 64k -y "<unified_dir>/audio/<normalized>.mp3"
```

Flags: `-ar 16000` (16kHz sample rate, optimal for ASR), `-ac 1` (mono), `-b:a 64k` (64kbps bitrate, sufficient for speech), `-y` (overwrite).

### Step 4: Incremental skip

Before converting, check if output WAV already exists. If so, skip and report as "skipped".

## Output Report

```
Converted:
  2026-03-27_140600.mp3 ← 2026.03.27_14.06.mp4
  2026-03-06_140525.mp3 ← 20260306_140525.m4a

Skipped (already exist):
  (none)
```
