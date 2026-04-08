---
name: meeting-assist-search
description: >-
  Search and ask questions across meeting transcripts and summaries. Find
  specific topics, decisions, or action items from past meetings. Invocable as
  /meeting-assist:meeting-assist-search (Claude Code) or
  $meeting-assist-search (Codex).
user-invocable: true
allowed_tools:
  - Read
  - Glob
  - Grep
arguments:
  - name: query
    description: "The question or search query about meeting content"
    required: true
  - name: unified_dir
    description: "Path to unified directory (default: unified/)"
    required: false
---

# Meeting Assist — Search

See [`PLATFORM_COMPAT.md`](https://github.com/WhiskyChoy/whisky-claude-plugins/blob/master/PLATFORM_COMPAT.md) for the full cross-platform tool mapping.

## Purpose

Search across meeting transcripts and summaries to answer user questions about past meetings. Supports keyword search, topic lookup, and cross-meeting synthesis.

Respond in the user's language (detect from their messages).

## Algorithm

### Step 1: Extract keywords

From the user's query, extract 2-5 key terms (Chinese and/or English).

### Step 2: Search summaries first

```
Grep pattern: <keywords>
Path: <unified_dir>/summary/
```

Summaries are shorter and more structured — search them first for quick matches.

### Step 3: Search transcripts for detail

If summaries don't contain enough context, or the user needs verbatim quotes:

```
Grep pattern: <keywords>
Path: <unified_dir>/transfer/
```

### Step 4: Read and synthesize

For files with matches, read the surrounding context. If the query spans multiple meetings, read chronologically and synthesize.

## Response Format

Answer the user's question directly, citing specific meetings by date and speaker:

```
关于 API 设计的讨论出现在两次会议中：

**2026-03-06 会议**：张三提出使用 RESTful 架构。
**2026-03-27 会议**：王五汇报了实现进展，决定引入游标分页。
```

Include:
1. **Direct answer** to the question
2. **Source references** — which meeting, who said it, with `[HH:MM:SS]` timestamps when available
3. **Timeline** (if applicable) — how the topic evolved

## No Results

If no relevant information is found:
1. Tell the user clearly
2. Suggest: checking if meetings are transcribed, trying different keywords, or broadening scope
3. List available meeting dates for reference
