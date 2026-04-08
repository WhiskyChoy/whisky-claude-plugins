---
name: meeting-assist-transcribe
description: >-
  Transcribe meeting audio files using FunASR with speaker diarization. Produces
  JSON transcripts with speaker labels, timestamps, and plain text output.
  Invocable as /meeting-assist:meeting-assist-transcribe (Claude Code) or
  $meeting-assist-transcribe (Codex).
user-invocable: true
allowed_tools:
  - Bash
  - Read
  - Write
  - Glob
arguments:
  - name: unified_dir
    description: "Path to unified directory (default: unified/)"
    required: false
  - name: device
    description: "Inference device: cuda:0 or cpu (default: cuda:0)"
    required: false
---

# Meeting Assist — Transcribe

See [`PLATFORM_COMPAT.md`](https://github.com/WhiskyChoy/whisky-claude-plugins/blob/master/PLATFORM_COMPAT.md) for the full cross-platform tool mapping.

## Purpose

Transcribe meeting audio files using FunASR (Paraformer + VAD + punctuation + cam++ speaker diarization). Outputs structured JSON with per-sentence speaker labels and timestamps, plus a human-readable TXT version.

## Prerequisites

All dependencies (Python, torch, funasr, models) are documented in the main `/meeting-assist` skill. Run prerequisite checks there first.

Quick verify:

```bash
python -c "import funasr, torch; print(f'FunASR {funasr.__version__}, CUDA: {torch.cuda.is_available()}')"
```

Before first transcription, ensure models are pre-downloaded:

```bash
python "$SKILL_DIR/scripts/funasr_transcribe.py" --check --device "cuda:0"
```

## Script Location

The `scripts/funasr_transcribe.py` script is in the `scripts/` subdirectory of this skill. Locate it at runtime:

```bash
# Claude Code
SKILL_DIR="$HOME/.claude/skills/meeting-assist-transcribe"

# Codex / Generic — find dynamically
SKILL_DIR="$(dirname "$(find ~ -path '*/meeting-assist-transcribe/scripts/funasr_transcribe.py' -maxdepth 7 2>/dev/null | head -1)")/.."

# Fallback: check plugin repo or cwd
[ -z "$SKILL_DIR" ] && SKILL_DIR="$(dirname "$(find . -path '*/meeting-assist-transcribe/scripts/funasr_transcribe.py' 2>/dev/null | head -1)")/.."
```

## Execution

The script includes a built-in browser progress page (`--progress-ui`). **Always use this flag** — it opens a local web page showing real-time per-file status, so the user has visual feedback during long transcriptions.

Run via Bash tool with `timeout: 600000` (10 min max). The script handles all user-facing progress display through the browser.

### Basic (batch mode with progress UI)

**Always use `--progress-ui`** to open a browser-based progress page so the user can see real-time status:

```bash
python "$SKILL_DIR/scripts/funasr_transcribe.py" \
  --input "<unified_dir>/audio" \
  --output "<unified_dir>/transfer" \
  --device "cuda:0" \
  --progress-ui
```

The progress page shows:
- Overall progress bar (N/M files)
- Per-file status (pending → transcribing → done)
- Duration, elapsed time, segment count, speaker count
- Auto-refreshes every second

### With speaker name mapping

If `<unified_dir>/.speaker-map.json` exists:

```bash
python "$SKILL_DIR/scripts/funasr_transcribe.py" \
  --input "<unified_dir>/audio" \
  --output "<unified_dir>/transfer" \
  --device "cuda:0" \
  --speaker-map "<unified_dir>/.speaker-map.json"
```

### Single file

```bash
python "$SKILL_DIR/scripts/funasr_transcribe.py" \
  --input "unified/audio/2026-03-27_140600.wav" \
  --output "unified/transfer/2026-03-27_140600.json" \
  --device "cuda:0"
```

## Output Format

### JSON (`<name>.json`)

```json
{
  "file": "2026-03-27_140600.wav",
  "speakers": ["SPEAKER_00", "SPEAKER_01"],
  "segments": [
    {
      "speaker": "SPEAKER_00",
      "start": 0.0,
      "end": 5.2,
      "text": "今天我们讨论一下项目进度"
    }
  ],
  "full_text": "今天我们讨论一下项目进度...",
  "labeled_text": "[SPEAKER_00] 今天我们讨论一下项目进度...\n\n[SPEAKER_01] 好的..."
}
```

### TXT (`<name>.txt`)

```
[00:00:00 - 00:00:05] [SPEAKER_00] 今天我们讨论一下项目进度
[00:00:05 - 00:00:12] [SPEAKER_01] 好的，我先汇报一下当前的开发状态
```

## Incremental Processing

The script automatically skips audio files that already have a corresponding `.json` in the output directory.

## Troubleshooting

| Problem | Solution |
|---------|----------|
| CUDA out of memory | Use `--device cpu` or close other GPU processes |
| Model download stalls | Check network; models are ~1-2 GB from ModelScope |
| Wrong speaker count | cam++ auto-detects speakers; audio quality affects accuracy |
| Import error for funasr | Ensure `pip install -U funasr torch torchaudio modelscope` |

## Fallback: WhisperX

If FunASR cannot be installed (e.g., platform incompatibility), use WhisperX:

```bash
pip install whisperx
```

WhisperX requires a Hugging Face token for pyannote speaker diarization. Chinese accuracy is lower than FunASR.
