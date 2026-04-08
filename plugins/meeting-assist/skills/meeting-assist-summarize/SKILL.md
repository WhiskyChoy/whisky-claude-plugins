---
name: meeting-assist-summarize
description: >-
  Generate structured meeting minutes from transcription files. Extracts key
  points, action items, decisions, and topics using Claude. Invocable as
  /meeting-assist:meeting-assist-summarize (Claude Code) or
  $meeting-assist-summarize (Codex).
user-invocable: true
allowed_tools:
  - Read
  - Write
  - Glob
  - Grep
  - AskUserQuestion
arguments:
  - name: unified_dir
    description: "Path to unified directory (default: unified/)"
    required: false
  - name: file
    description: "Specific transcription file to summarize (optional, default: all pending)"
    required: false
---

# Meeting Assist — Summarize

See [`PLATFORM_COMPAT.md`](https://github.com/WhiskyChoy/whisky-claude-plugins/blob/master/PLATFORM_COMPAT.md) for the full cross-platform tool mapping.

## Purpose

Generate structured meeting minutes from transcription JSON/TXT files. You (Claude) ARE the AI generating the summary — read the transcript and extract information using your own language understanding.

## Input

Transcription files in `<unified_dir>/transfer/` (default: `unified/transfer/`). Prefer `.json` for structured data; fall back to `.txt` if JSON is unavailable.

## Output

`<unified_dir>/summary/<basename>.md` — structured meeting minutes in Markdown.

## Algorithm

### Step 1: Find pending transcriptions

```
Glob: <unified_dir>/transfer/*.json
```

For each `.json` file, check if `<unified_dir>/summary/<same-basename>.md` exists. Skip if it does (incremental processing).

### Step 1.5: Language preference

Use `AskUserQuestion` to ask the user's preferred report language before generating any summary. Options:

- **中文** (recommended for Chinese-language meetings)
- **English**

Store the choice as `{lang}` for template selection below. If the user has already stated a preference in conversation, skip asking.

### Step 2: Speaker name resolution

Check if `<unified_dir>/transfer/<basename>_speaker-map.json` or `<unified_dir>/.speaker-map.json` exists. If so, load it and replace all `SPEAKER_XX` labels with mapped names.

If the map does not exist:
1. After reading the first transcription, show the user a sample of each speaker's text
2. Ask if they want to assign real names to speakers
3. If yes, create the map and apply it

### Step 2.5: Prepare context for parallel summarization

**Model routing**: Use `model: sonnet` for per-chunk summary agents (good quality/cost balance). The main conversation (Opus) handles only task decomposition and final merge.

**Parallelism**: For long meetings (> 1 hour), split transcript into chunks and launch ALL summary agents in a **single message** with `run_in_background: true` — do NOT batch them. Each summary agent MUST receive:

1. **Transcript chunk** — the corrected text for its time range
2. **Glossary reference** (`_glossary.xlsx` or equivalent JSON) — domain terminology, so agents understand specialized terms and can fix residual ASR errors when quoting
3. **Speaker-map** (`_speaker-map.json`) — who is who, which speakers have uncaptured audio
4. **Meeting metadata** — date, total duration, participant list, chunk position (e.g. "part 2/4, 51:15-99:11")
5. **Language preference** — `{lang}` from Step 1.5

After all chunks complete, merge into a single summary: deduplicate decisions/commitments, unify topic numbering, consolidate keyword list.

**Post-merge coherence check**:
- All speakers in "Attendees" appear at least once in detailed content?
- Commitments table has no duplicate entries (same person + same content)?
- Timestamps across sections are monotonically ordered?
- No commitment references a speaker not in the attendees list?

### Step 3: Read transcript and generate summary

Read the transcription JSON. Use the `labeled_text` and `segments` fields to understand who said what and when.

#### Handling uncaptured-audio speakers

Check for the `unreliable_speakers` field in the JSON. If present, these speakers' audio was not captured by the recording device — their transcribed content may be misattributed from other sound sources.

For each section of the summary, handle these speakers as follows:

- **Participants section**: list them normally, but append a warning parenthetical after their name.
  - zh: `（录音未采集）`
  - en: `(audio not captured)`
- **Detailed content**: include their contributions but prefix each mention with a warning marker.
  - zh: `⚠（录音未采集）`
  - en: `⚠ (audio not captured)`
- **Commitments table**: keep the committer's name, add a warning note.
  - zh: `⚠ {name}（该讲话人声音未被录音设备采集，此承诺可能为系统误识别，请线下确认）`
  - en: `⚠ {name} (this speaker's audio was not captured; commitment may be misattributed — please verify offline)`
- **Key decisions**: same treatment — keep the name, add the warning. Never delete or anonymize.
- Never describe these speakers as "unreliable" or "不可靠" — the issue is with the recording equipment, not the person.

#### Template selection

Use the template matching `{lang}` from Step 1.5.

<details>
<summary><b>Chinese template (zh)</b></summary>

```markdown
# 会议纪要 — {YYYY-MM-DD}

## 基本信息
- **日期**：{YYYY-MM-DD HH:MM}
- **时长**：约 {duration} 分钟
- **参会人**：{speaker list}

## 议题概览
1. {topic}

## 详细内容

### 1. {topic}
- **{Speaker}** [{HH:MM:SS}]：{key point}
- **结论**：{conclusion if reached}

## 承诺与待办事项

| 承诺人 | 承诺对象 | 承诺内容 | 强度 | 截止 | 原文 |
|--------|---------|---------|------|------|------|
| {name} | {target} | {what} | {strength} | {deadline} | {corrected quote} |

## 关键决策
1. {decision}

## 风险与问题
- {risk}

## 关键词
{keywords}
```

</details>

<details>
<summary><b>English template (en)</b></summary>

```markdown
# Meeting Minutes — {YYYY-MM-DD}

## Overview
- **Date**: {YYYY-MM-DD HH:MM}
- **Duration**: ~{duration} minutes
- **Attendees**: {speaker list}

## Agenda
1. {topic}

## Detailed Discussion

### 1. {topic}
- **{Speaker}** [{HH:MM:SS}]: {key point}
- **Conclusion**: {conclusion if reached}

## Commitments & Action Items

| Committer | To | Commitment | Strength | Deadline | Quote |
|-----------|-----|-----------|----------|----------|-------|
| {name} | {target} | {what} | {strength} | {deadline} | {corrected quote} |

## Key Decisions
1. {decision}

## Risks & Open Issues
- {risk}

## Keywords
{keywords}
```

</details>

#### Commitment strength detection

Use the following labels based on `{lang}`. Detection patterns are listed for Chinese-language meetings; for other languages, apply equivalent semantic rules.

| zh | en | Detection pattern (zh) | Detection pattern (en) |
|----|-----|------------------------|------------------------|
| 明确承诺 | Firm commitment | "我来做"、"包在我身上"、"我下周交" | "I'll do it", "I'll handle this", "I'll deliver by..." |
| 条件承诺 | Conditional | "如果你们给我数据，我就能做" | "If you give me X, I can do Y" |
| 被分配 | Assigned (accepted) | A: "你来做XX" → B: "好/行/没问题" | A: "Can you do X?" → B: "Sure / Will do" |
| 被分配（未确认） | Assigned (unconfirmed) | A: "你来做XX" → B: no response ⚠ | A: "You should do X" → B: no response ⚠ |
| 建议 | Suggestion | "我觉得应该…"、"建议XX来做" | "I think we should...", "Maybe X could..." |

### Summary Guidelines

1. **Accuracy** — only include information actually discussed. Never fabricate decisions or quotes.
2. **Fix ASR errors in quotes** — the correction step only covers high-frequency errors; residual garbled text may remain. When quoting transcript text (especially in the "Quote" column of the commitments table), always fix obvious ASR errors before quoting. If the original is unintelligible, omit the quote or note it as unclear.
3. **Action items** — extract concrete tasks with owners. If no person is assigned, mark as TBD (zh: "待定").
4. **Decisions vs. discussions** — clearly distinguish agreed decisions from open discussions.
5. **Brevity** — the summary should be significantly shorter than the transcript. Each bullet should be concise.
6. **Timestamps** — optionally include `[HH:MM:SS]` references for key moments to help locate them in the recording.
7. **Preserve original-language quotes** — when the report language differs from the meeting language (e.g. English report for a Chinese meeting), keep quoted speech in its original language and provide a brief translation or paraphrase in the report language.

## Edge Cases

- **Very short meetings** (< 5 minutes): simplify the template — skip empty sections.
- **Single speaker**: omit speaker labels, focus on content structure.
- **No clear action items**: state explicitly (zh: "无明确待办事项", en: "No action items identified").
- **Mixed-language meetings**: use the user's chosen `{lang}` for headings and structure; preserve quotes in their original language.
