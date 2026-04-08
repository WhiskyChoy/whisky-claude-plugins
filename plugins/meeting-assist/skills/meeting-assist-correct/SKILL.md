---
name: meeting-assist-correct
description: >-
  Correct ASR transcription errors using parallel agents — fix misrecognized
  terms, predict speaker identities, and generate review tables for user
  confirmation. Invocable as /meeting-assist:meeting-assist-correct (Claude Code)
  or $meeting-assist-correct (Codex).
user-invocable: true
allowed_tools:
  - Bash
  - Read
  - Write
  - Glob
  - Grep
  - Agent
  - AskUserQuestion
arguments:
  - name: unified_dir
    description: "Path to unified directory (default: unified/)"
    required: false
  - name: file
    description: "Specific transcription basename to correct (optional, default: all pending)"
    required: false
---

# Meeting Assist — Correct

See [`PLATFORM_COMPAT.md`](https://github.com/WhiskyChoy/whisky-claude-plugins/blob/master/PLATFORM_COMPAT.md) for the full cross-platform tool mapping.

## Purpose

Correct ASR transcription errors between the transcribe and summarize steps. Uses parallel agents to analyze the transcript, then generates compact review tables for the user to confirm.

Respond in the user's language (detect from their messages). The correction data formats (JSON field names, glossary categories, speaker-map special values) always use Chinese keys regardless of conversation language, as the scripts depend on them.

## Design Principles

1. **Balance coverage and review effort** — table size adapts to meeting length and error density (see sizing formula below)
2. **Two-layer review** — global glossary (must review, 1-2 min) + per-line corrections (optional)
3. **AI predicts, user confirms** — speaker identities are pre-filled, user just edits wrong ones
4. **Unfilled = skip** — any row with empty or `？` in the correction column is not applied

## Table sizing

Table sizes adapt to three factors: **meeting scale** (longer meetings produce more errors), **actual error density** (some recordings are cleaner than others), and **human review budget** (diminishing returns beyond a threshold).

### Glossary sizing

```
base = segments / 200        # ~1 row per 200 segments (scales with meeting length)
cap  = min(base × 2, 80)     # hard cap at 80 rows (beyond this, review fatigue outweighs value)
floor = 10                    # minimum to catch key terms even in short meetings

glossary_rows = clamp(actual_unique_terms, floor, cap)
```

| Meeting length | Segments | Base | Typical range |
|---------------|----------|------|---------------|
| 15 min        | ~300     | ~2   | 10-15 rows    |
| 1 hour        | ~1200    | ~6   | 10-25 rows    |
| 3 hours       | ~5700    | ~29  | 20-60 rows    |

If the analysis produces more unique terms than `cap`, prioritize by: count descending → person names always included → low-count terms dropped first.

### Corrections sizing

```
base = segments / 300        # ~1 correction per 300 segments
cap  = min(base × 2, 40)     # hard cap at 40 rows
floor = 5

corrections_rows = clamp(actual_corrections_above_threshold, floor, cap)
```

Only include corrections with confidence ≥ 0.8. If more candidates than `cap`, sort by confidence descending and truncate.

### Confidence threshold

Not all analysis results should reach the user. Apply a minimum confidence threshold:
- **Glossary terms**: include if count ≥ 2 OR confidence ≥ 0.9 (single-occurrence high-confidence terms are OK)
- **Corrections**: include only if confidence ≥ 0.8
- **Speaker predictions**: always include (user must review all speakers regardless of confidence)

## Prerequisites

All dependencies are documented in the main `/meeting-assist` skill. Quick verify for this step:

```bash
python -c "import openpyxl; print(openpyxl.__version__)"
```

## Input

Transcription files in `<unified_dir>/transfer/` — both `.json` and `.txt`.

## Output

For each transcription `<basename>`:
- `<unified_dir>/transfer/<basename>_speakers.md` — speaker profile cards
- `<unified_dir>/transfer/<basename>_glossary.xlsx` — global term + speaker mapping table (★ must review)
- `<unified_dir>/transfer/<basename>_corrections.xlsx` — per-line high-confidence corrections (optional review)

After user confirms, updates are applied to the original `.json` and `.txt`.

## Script Reference

### `scripts/identify_speakers.py` — Speaker identification HTML page

```bash
python scripts/identify_speakers.py \
    --transcript <basename>.json \
    --audio <basename>.mp3 \
    --output <basename>_identify.html \
    --speakers-md <basename>_speakers.md \
    --open   # starts local server, Save button auto-saves to <basename>_speaker-map.json
```

HTML features: audio clips per speaker, editable name inputs, quick-value dropdown (合并到…/混合多人/声音未录入/幻听), Save via POST to local server.

Output: `<basename>_speaker-map.json`

### `scripts/generate_review_xlsx.py` — XLSX generation with consistent formatting

```bash
# From nested merged_results.json (auto-extracts "glossary" key):
python scripts/generate_review_xlsx.py glossary \
    --input merged_results.json --key glossary \
    --speaker-map <basename>_speaker-map.json \
    --transcript <basename>.json \
    --output <basename>_glossary.xlsx

# Corrections from same nested JSON:
python scripts/generate_review_xlsx.py corrections \
    --input merged_results.json --key corrections \
    --output <basename>_corrections.xlsx
```

Glossary features:
- Auto-sorts by category (术语→人名→说话人→口语简化), then count descending
- `--speaker-map` injects speaker mapping rows (green, with segment counts from transcript)
- `--fillers` injects filler word rows (gray)
- Supports both flat `[{...}]` and nested `{"glossary": [...]}` JSON input
- List values (e.g. `originals: ["a","b"]`) auto-joined with " / "

### JSON formats

**Glossary row** (flat or under `"glossary"` key):
```json
{"类别": "术语", "原文/变体": "行线 / 横线", "修正": "航线", "出现次数": 85, "示例上下文": "..."}
```
Categories: `术语`(orange), `人名`(blue), `说话人`(green), `口语简化`(gray)

**Corrections row** (flat or under `"corrections"` key):
```json
{"时间戳": "00:01:26", "说话人": "SPEAKER_01", "原文": "...", "修正": "...", "置信度": "high", "类型": "误识别"}
```

**Speaker-map** (`_speaker-map.json`):
```json
{
  "SPEAKER_01": "张三丰",
  "SPEAKER_13": "合并到 SPEAKER_01",
  "SPEAKER_03": "混合多人(声音未录入)",
  "SPEAKER_07": "(幻听/噪音)"
}
```
Special values: normal name, `合并到 SPEAKER_XX`, `混合多人(声音未录入)`, `(幻听/噪音)`, empty/`？`

## Flow

```
*.json,txt (raw transcript)
  │
  ├──▶ [identify]  cut audio clips → HTML page → user confirms speakers
  │
  ▼ [analyze]      split into chunks → parallel agents → merge results
  │
  ▼ [web-verify]   WebSearch uncertain terms (company names, acronyms)
  │
  ▼ [generate]     glossary.xlsx + corrections.xlsx + speakers.md
  │
  ▼ [user review]  user edits XLSX → confirms
  │
  ▼ [apply]        find-replace terms, map speakers, remove fillers
  │
  ▼ *.json,txt (corrected)
```

## Agent Architecture

### Model routing

Use the `model` parameter on the Agent tool to route each subagent appropriately. The main conversation (Opus) acts as planner/orchestrator only — never spawn Opus subagents.

Three tiers — Planner / Worker / Sweeper — each with a default model and cost profile:

**Planner** — opus (main conversation only, ~1x cost)

| Task | Rationale |
|------|-----------|
| Task decomposition, chunking strategy | Needs full pipeline context |
| Result merge, quality gates | Cross-task coherence, judgment calls |
| User interaction (AskUserQuestion, review) | Requires conversational context |

**Worker** — `sonnet` (~0.2x cost)

| Task | Rationale |
|------|-----------|
| Chunk analysis (term extraction, speaker clues) | Domain understanding without deep reasoning |
| Result aggregation (merge, deduplicate, rank) | Structured data merging, moderate complexity |
| Per-chunk summarization | Good quality/cost balance for structured extraction |
| Summary merge (combine chunks into final) | Deduplication and coherence check |

**Sweeper** — `haiku` (~0.04x cost)

| Task | Rationale |
|------|-----------|
| Full-text correction sweep | Mechanical find-replace with context; high volume |
| Schema validation of agent outputs | Structural check, no reasoning needed |

### Parallelism DAG

Launch independent tasks in a **single message** for true parallel execution. The correction pipeline has this dependency structure:

```
[transcript.json + audio.mp3]
       │                │
       ▼                ▼
  ┌─ identify_speakers.py (Bash, ffmpeg clips)
  │         │
  │    ┌────┴──── chunk analysis × N (Worker agents, ALL in one message)
  │    │
  │    ▼
  │  merge results (Planner)
  │    │
  │    ├─ generate glossary XLSX ─┐
  │    └─ generate corrections XLSX ─┤ (parallel Bash calls)
  │                              │
  └──► [user reviews HTML + XLSX]
              │
              ▼
         apply corrections (Planner)
              │
              ▼
         Haiku full-text sweep × 4-6 (Sweeper agents, ALL in one message)
              │
              ▼
         [corrected transcript ready for summarize]
```

**Anti-pattern** — do NOT launch agents in batches:
```
# BAD: 3 batches of 4 = serialized wall-clock time
Agent(chunk_0..3) → wait → Agent(chunk_4..7) → wait → Agent(chunk_8..11)

# GOOD: 1 batch of 12 = truly parallel
Agent(chunk_0, model=sonnet, bg=true)
Agent(chunk_1, model=sonnet, bg=true)
...
Agent(chunk_11, model=sonnet, bg=true)
```

### Quality gates

#### Gate 1: Schema validation (after each chunk agent returns)
Before merging any chunk's output:
- JSON parseable? Required keys (`terms`, `speakers`, `corrections`) present?
- Term count in sane range (3-40 per 500 segments)? Too few → missed errors; too many → low confidence
- Speaker IDs match `SPEAKER_\d+` pattern?
- **On failure**: retry that chunk once with error feedback, then skip and log warning

#### Gate 2: Cross-chunk consistency (during merge)
When aggregating results:
- Same term corrected **differently** across chunks → flag both variants for user review in glossary
- Same speaker predicted as **different people** → include both predictions, note conflict
- Term count per chunk varies >5x → investigate (one chunk may have garbled output)

#### Gate 3: Post-apply coherence (after corrections applied)
After applying glossary + speaker-map + per-line corrections:
- Spot-check: sample 10 random segments, verify no obviously broken text
- Speaker list: all mapped speakers appear in at least one segment?
- No empty segments created by over-aggressive filler removal?

### Haiku full-text correction sweep (Step 5.5)

After applying user-reviewed corrections (Step 5), launch **Haiku-tier** agents to sweep the entire corrected transcript for residual errors. This catches the long tail — low-frequency ASR errors that parallel analysis missed.

**What Haiku sweepers fix**:
- Garbled characters mixed into Chinese text (e.g. lone `j`, `g`, `z` in Chinese sentences)
- Nonsense syllable sequences that aren't real words
- Known term variants not covered by glossary (catch remaining instances)
- Obvious grammar breaks from ASR (e.g. "的的的" → "的")

**What they do NOT fix**: anything uncertain. If unsure, leave it.

**Implementation**:
1. Split corrected transcript into 4-6 chunks (~200-300 segments each)
2. Launch ALL Haiku agents in one message with `model: haiku, run_in_background: true`
3. Each agent receives: chunk text + glossary (as domain context) + instructions
4. Each agent returns: corrected segments (only changed ones, with original for diff)
5. Merge back, apply only segments that changed

**Cost**: ~60K tokens for 1200 segments ≈ $0.015 (negligible)

## Algorithm

### Step 1: Parallel Agent Analysis

Read the transcription `.txt` file. Determine the total segment count and split into chunks of ~500 segments each. Launch ALL chunk agents in parallel using `model: sonnet` and `run_in_background: true`. For meetings > 3000 segments, increase chunk count (up to 12 concurrent agents).

**Each agent's instructions:**

> You are analyzing a chunk of meeting transcription for errors. Read the segments carefully and produce TWO outputs as JSON:
>
> **Output 1: Aggregated terms** — group repeated misrecognitions:
> ```json
> {
>   "terms": [
>     {"originals": ["三万空间", "三完空间"], "correction": "三维空间", "count": 12, "example": "从二维到三万空间的映射"},
>     {"originals": ["张仨轰"], "correction": "张三丰（人名）", "count": 8, "example": "张仨轰要看一下审批"}
>   ],
>   "filler_words": [
>     {"pattern": "可能可能可能+", "simplified": "可能", "count": 5},
>     {"pattern": "呃|啊|嗯（独立段落）", "action": "删除", "count": 20}
>   ]
> }
> ```
>
> **Output 2: Speaker analysis** — for each SPEAKER_XX in your chunk:
> ```json
> {
>   "speakers": {
>     "SPEAKER_01": {
>       "segment_count": 150,
>       "called_by_others": [{"caller": "SPEAKER_02", "timestamp": "00:00:07", "quote": "张仨轰要看一下"}],
>       "self_identification": [{"timestamp": "01:05:00", "quote": "我们实验室这边..."}],
>       "role_clues": ["主要汇报人", "低空规则领域"],
>       "distinctive_quotes": [
>         {"timestamp": "00:00:29", "text": "我们提取的是一个移动闭塞的一个概念"},
>         {"timestamp": "01:15:30", "text": "串行方式在500毫秒内可完成十万架在空"}
>       ],
>       "predicted_identity": "张三丰",
>       "confidence": "high"
>     }
>   }
> }
> ```
>
> **Output 3: One-off corrections** — single-occurrence errors not covered by terms:
> ```json
> {
>   "corrections": [
>     {"timestamp": "00:00:55", "speaker": "SPEAKER_01", "original": "被机咬出这个航段", "correction": "编辑划出这个航段", "reason": "口音误识别"}
>   ]
> }
> ```
>
> Rules:
> - Only output HIGH confidence corrections. Skip anything uncertain.
> - Group similar errors as terms, don't list each occurrence separately.
> - For speaker identification: focus on **distinguishing features** — what makes this speaker different from others.

### Step 2: Main Agent Aggregation

After all agents complete, aggregate their outputs:

1. **Merge term tables** — deduplicate, sum counts, keep best example
2. **Merge speaker analyses** — combine clues from all chunks per speaker, resolve conflicts
3. **Predict speaker identities** — from all collected clues (names heard, self-introductions, role signals)
4. **Rank one-off corrections** — sort by confidence, apply sizing formula below

### Step 3: Generate Review Files

#### 3a. Speaker Profile Cards (`_speakers.md`)

For each speaker, generate a card:

```markdown
## SPEAKER_01 → 张三丰（预测，置信度：高）

- **发言占比**：35%（1,990 / 5,684 段）
- **首次发言**：00:00:00
- **角色线索**：
  - 主要汇报人，连续汇报低空规则体系
  - 被 SPEAKER_02 称为"张仨轰"
- **高辨识度发言**：
  - [00:00:29] "我们提取的是一个移动闭塞的一个概念"
  - [01:15:30] "串行方式在500毫秒内可完成十万架在空"
- **被他人称呼**：
  - SPEAKER_02 [00:00:07]: "张仨轰要看一下审批的过程中"
```

Sort speakers by segment count (most active first). Skip speakers with < 5 segments (group as "其他").

#### 3b. Global Glossary Table (`_glossary.xlsx`)

XLSX with formatted headers (blue header row, color-coded categories, freeze panes, auto-filter). Requires `openpyxl`. Size determined by the sizing formula below:

```
类型	原文（可能多种写法）	修正为	出现次数	示例上下文
```

Row types: `术语`, `人名`, `说话人`, `口语简化`

For `说话人` rows: put predicted identity in "修正为" column with "(预测，置信度：X)".

#### 3c. Per-line Corrections Table (`_corrections.xlsx`)

XLSX with same formatting as glossary. Size determined by the sizing formula below:

```
时间戳	说话人	原文片段	修正为	原因
```

### Step 4: User Review

Tell the user the three files have been generated. Suggest they:

1. **Read `_speakers.md`** first — identify who's who, note any corrections
2. **Edit `_glossary.xlsx`** — confirm/modify/delete rows. This is the most important file.
3. **Optionally edit `_corrections.xlsx`** — for fine-grained fixes

Tell the user: "编辑完成后告诉我，我会把修正应用到转录文件。不确定的行删掉即可，不会被应用。"

Wait for the user to confirm they are done editing.

### Step 5: Apply Corrections

**Reading XLSX files**: Use openpyxl to read user-edited XLSX:

```python
import openpyxl
wb = openpyxl.load_workbook("glossary.xlsx")
rows = [list(r) for r in wb.active.iter_rows(values_only=True)]
headers, data = rows[0], rows[1:]  # headers = ['类别', '原文/变体', '修正', ...]
```

Apply corrections to the `.json` and `.txt`:

1. **Speaker mapping** — read `说话人` rows from glossary. Handle by correction value:
   - **Normal name** (e.g. "令狐冲"): replace SPEAKER_XX with name in all segments
   - **Contains `未录入`** (e.g. "黄药师(声音未录入...)"): extract the name part ("黄药师"), map the speaker, AND add to `unreliable_speakers` list in JSON. These speakers' content will be flagged in summaries (see summarize skill)
   - **Contains `幻听`/`噪音`/`非真实`**: delete ALL segments from this speaker
   - **Contains `合并到 SPEAKER_XX`**: merge all segments into the target speaker, sorted by timestamp
   - **Empty / `？` / `未能识别`**: skip, keep original SPEAKER_XX label
2. **Term corrections** — for each `术语`/`人名` row, do global find-replace across all segment texts. Skip rows with empty correction.
3. **Filler removal** — for `口语简化` rows marked `（删除）`, remove matching standalone segments entirely.
4. **Per-line corrections** — apply `_corrections.xlsx` entries by matching timestamp + original text.
5. **Rebuild** `labeled_text` and `full_text` fields in JSON from updated segments.
6. **Regenerate** `.txt` from updated JSON.
7. **Write** `unified/.speaker-map.json` from confirmed speaker mappings (for use by summarize step).

8. **Residual error sweep** — after applying user-reviewed corrections, do a final pass over ALL segment texts. Auto-fix obvious residual ASR artifacts WITHOUT user review:
   - Non-Chinese characters mixed into Chinese sentences (e.g., `九二j省` → remove or replace)
   - Nonsensical syllable strings that are clearly garbled (e.g., `成共` in a context where no such word exists)
   - Untranslated English fragments that should be Chinese (e.g., `complaace` → remove)
   - This sweep is conservative: only fix text that is unambiguously garbled. If uncertain, leave it.

Report what was changed:
```
Applied corrections:
  - 15 术语 replacements (45 occurrences)
  - 3 人名 replacements (18 occurrences)
  - 8 说话人 mappings applied
  - 42 filler segments removed
  - 12 per-line corrections applied
```

## Incremental Processing

- Skip transcriptions that already have `_glossary.xlsx` files (unless user explicitly re-runs)
- If corrections have already been applied (check for `_corrected` flag in JSON), warn and ask before re-applying

## Edge Cases

- **Very short transcription** (< 50 segments): Skip parallel agents, analyze in a single pass
- **No errors found**: Still generate speaker profiles, but glossary/corrections tables may be very short or empty
- **User deletes all rows**: Apply nothing, proceed to summarize with original transcript
