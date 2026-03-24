---
name: brainstorm-end
description: Exit brainstorm mode. Use when the user says "exit brainstorm", "退出头脑风暴", "结束讨论", "done brainstorming", or any clear intent to leave brainstorm mode. Invocable as /brainstorm:end (Claude Code) or $brainstorm-end (Codex).
user-invocable: true
---

# Exit Brainstorm Mode

1. Summarize what was decided (one paragraph).
2. State whether a spec was written (and its path under `brainstorming/`), or if the discussion is incomplete.
   - If incomplete and substantial discussion occurred, suggest running `/brainstorm:save` first to capture progress.
3. Resume normal coding agent behavior — all brainstorm-specific constraints no longer apply.

**Clean unload (context recovery):**
- Claude Code: suggest `/compact` to compress brainstorm instructions out of context.
- Other environments: suggest starting a new session, or note that brainstorm instructions will naturally fade as context fills with new work.
