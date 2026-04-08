---
name: meeting-assist
description: >-
  Meeting recording pipeline — convert raw audio/video, transcribe with speaker
  diarization, and generate AI meeting minutes. Use when the user wants to
  process meeting recordings, generate transcripts, or create meeting summaries.
  Triggers on: "process meeting", "transcribe recording", "meeting minutes",
  "会议纪要", "会议转录", "处理录音". Invocable as /meeting-assist (Claude Code)
  or $meeting-assist (Codex).
user-invocable: true
allowed_tools:
  - Bash
  - Read
  - Write
  - Edit
  - Glob
  - Grep
  - Agent
  - Skill
arguments:
  - name: step
    description: >-
      Which pipeline step to run: convert, transcribe, summarize, search, or all
      (default: all, which runs convert → transcribe → summarize)
    required: false
  - name: raw_dir
    description: "Path to raw recordings directory (default: raw/)"
    required: false
  - name: unified_dir
    description: "Path to unified output directory (default: unified/)"
    required: false
---

# Meeting Assist

This skill works with **Claude Code CLI**, **OpenAI Codex CLI**, and other SKILL.md-compatible agents.
Instructions use Claude Code tool names by default — see [`PLATFORM_COMPAT.md`](https://github.com/WhiskyChoy/whisky-claude-plugins/blob/master/PLATFORM_COMPAT.md) for the full cross-platform tool mapping.

## Purpose

End-to-end meeting recording processing: raw audio/video → unified audio → transcription with speaker diarization → structured meeting minutes. Benchmarked against commercial tools (讯飞听见, 通义听悟) for feature parity on core capabilities.

Respond in the user's language (detect from their messages). The summarize step will explicitly ask the user's preferred report language via `AskUserQuestion` before generating meeting minutes.

## Pipeline Overview

```
raw/*.mp4,m4a,mp3,...
  │
  ▼ [convert]        ffmpeg → 16kHz mono MP3, date-normalized filenames
unified/audio/*.mp3
  │
  ▼ [transcribe]     FunASR (Paraformer+VAD+punc+cam++) → JSON+TXT
unified/transfer/*.json,txt
  │
  ├──▶ [identify]    HTML audio page (Bash, ffmpeg clips) ──┐
  │                                                         │ parallel
  ├──▶ [analyze]     Sonnet workers × N chunks ─────────────┤
  │                                                         │
  ▼ [merge + generate]  aggregate → glossary.xlsx + corrections.xlsx
  │
  ▼ [user review]    user edits XLSX + confirms speakers
  │
  ▼ [apply]          find-replace terms, map speakers
  │
  ▼ [haiku sweep]    Haiku sweepers × 4-6 → fix residual ASR errors
unified/transfer/*.json,txt (corrected)
  │
  ▼ [summarize]      Sonnet workers × N chunks → merge → MD + XLSX
unified/summary/*.md,xlsx
  │
  ▼ [search]         Grep + Claude → cross-meeting Q&A (on demand)
```

**Model tiers**: Opus = orchestrator only (decompose, merge, user interaction). Sonnet = analysis & summary workers. Haiku = mechanical bulk correction. See correct/SKILL.md Agent Architecture for details.

User intervention point: after `[merge + generate]`, the user edits XLSX and confirms speakers before corrections are applied.

## Prerequisites

Verify at the start of every invocation. **Stop with actionable guidance** if anything is missing.

### System tools

| Tool | Purpose | Check | Install |
|------|---------|-------|---------|
| ffmpeg | Audio/video conversion | `ffmpeg -version` | Windows: `winget install ffmpeg`; macOS: `brew install ffmpeg`; Linux: `sudo apt install ffmpeg` |
| Python 3.10-3.12 | Runtime | `python --version` | 3.14+ may have compatibility issues with FunASR; use `uv venv --python 3.12` if needed |

### Python packages

| Package | Purpose | Check |
|---------|---------|-------|
| torch + torchaudio | Deep learning + audio I/O | `python -c "import torch; print(torch.__version__)"` |
| funasr | ASR engine (Paraformer + VAD + diarization) | `python -c "import funasr; print(funasr.__version__)"` |
| modelscope | Model downloading | (installed with funasr) |
| numpy | Array operations | `python -c "import numpy"` |
| openpyxl | XLSX generation for review tables | `python -c "import openpyxl"` |

**One-shot install** (give this to the user to run):

```bash
# Step 1: Detect CUDA version and install matching PyTorch
#   Check CUDA version: nvidia-smi or nvcc --version
#   Then pick the matching wheel index:
#     CUDA 11.8 → cu118
#     CUDA 12.1 → cu121
#     CUDA 12.4 → cu124
#     CUDA 12.6 → cu126
#     CPU only  → cpu
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu124  # ← adjust cu version

# Step 2: ASR + utilities
pip install funasr modelscope numpy openpyxl
```

Before running the install command, detect the user's CUDA version:

```bash
nvidia-smi | head -3   # shows driver + CUDA version
# or: nvcc --version
```

Then replace `cu124` with the matching version (e.g. `cu121` for CUDA 12.1, `cu118` for CUDA 11.8, `cpu` for no GPU).

### Slow downloads?

If pip/uv is slow (common in mainland China), add a mirror for non-PyTorch packages:

```bash
pip install <package> -i https://pypi.tuna.tsinghua.edu.cn/simple/
```

Note: PyTorch CUDA wheels must use the official index (`--index-url https://download.pytorch.org/whl/cuXXX`), mirrors don't carry them.

### FunASR models (~1-2 GB, requires internet)

Pre-download before first transcription:

```bash
python funasr_transcribe.py --check --device cuda:0
```

Downloads: paraformer-zh (ASR), fsmn-vad (VAD), ct-punc (punctuation), cam++ (speaker diarization).

### Hardware

- **GPU (recommended)**: NVIDIA GPU with CUDA support. Transcription is ~10-50x faster on GPU.
- **CPU fallback**: Works but significantly slower. Use `--device cpu`.
- **Disk space**: ~3 GB for models + output files.

## Directory Layout

```
<cwd>/
  raw/                          # Input: raw recordings (mp3, mp4, m4a, wav, etc.)
  unified/
    audio/                      # Stage 1 output: 16kHz mono WAV
    transfer/                   # Stage 2 output: transcription JSON + TXT
    summary/                    # Stage 3 output: meeting minutes MD
    .speaker-map.json           # Optional: SPEAKER_XX → real name mapping
```

## Sub-Commands

| Command | Purpose |
|---------|---------|
| `/meeting-assist` | Full pipeline (convert → transcribe → correct → summarize) |
| `/meeting-assist:meeting-assist-convert` | Extract and normalize audio from raw recordings |
| `/meeting-assist:meeting-assist-transcribe` | Transcribe audio with FunASR (speaker diarization) |
| `/meeting-assist:meeting-assist-correct` | Correct transcription errors + predict speaker identities |
| `/meeting-assist:meeting-assist-summarize` | Generate structured meeting minutes from transcripts |
| `/meeting-assist:meeting-assist-search` | Search and Q&A across all meetings |

## Entry Logic

On invocation, parse arguments and route:

1. **Determine `step`** — default `all` if not specified
2. **Ensure directories exist** — create `raw/`, `unified/audio/`, `unified/transfer/`, `unified/summary/` if missing
3. **Pre-flight check** — if `transcribe` or `all` is requested, run `funasr_transcribe.py --check` first to ensure models are downloaded before processing any files
4. **Route to sub-commands:**

| Step | Action |
|------|--------|
| `all` | Run convert → transcribe → correct → summarize sequentially |
| `convert` | Invoke `/meeting-assist:meeting-assist-convert` |
| `transcribe` | Invoke `/meeting-assist:meeting-assist-transcribe` |
| `correct` | Invoke `/meeting-assist:meeting-assist-correct` |
| `summarize` | Invoke `/meeting-assist:meeting-assist-summarize` |
| `search` | Invoke `/meeting-assist:meeting-assist-search` (requires a query from the user) |

4. **Incremental processing** — each sub-command handles its own skip logic for already-processed files

## Status Report

After all steps complete, print a summary table:

```
Pipeline complete:
  Audio files:     N converted, M skipped
  Transcriptions:  N generated, M skipped
  Summaries:       N generated, M skipped
```

## Error Handling

- If a sub-command fails for a specific file, log the error and continue with remaining files
- At the end, report which files failed and why
- Common failures: missing ffmpeg, missing FunASR/Python, insufficient GPU memory
- Stop with actionable guidance if a prerequisite is missing — do not silently skip
