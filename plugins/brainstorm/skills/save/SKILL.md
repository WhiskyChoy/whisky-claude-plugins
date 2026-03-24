---
name: brainstorm-save
description: Save the current brainstorm discussion as a specification document. Use when the user wants to persist brainstorm progress — either a final spec or a partial checkpoint. Invocable as /brainstorm:save (Claude Code) or $brainstorm-save (Codex).
user-invocable: true
---

# Save Brainstorm Spec

Save the current state of the brainstorm discussion to `brainstorming/` under the project root.

## Behavior

1. Determine the spec filename from the discussion topic. Use kebab-case: `brainstorming/<topic>-spec.md`.
   - If a spec file was already written during this session, update it in place.
2. Write (or overwrite) the spec using the Phase 4 template from the main brainstorm skill:

```markdown
# [Name] — Implementation Specification

## Problem Statement
## Solution Overview
## Algorithm / Design Description
## Data Structures
## Interface Contract
## Design Decisions & Rationale
## Complexity Analysis
## Edge Cases and Boundary Conditions
## Verification Criteria
## Open Risks
```

3. Adjust depth per section — put detail where the real complexity lives. Omit sections that don't apply.
4. If the discussion is **incomplete** (not yet converged):
   - Save what's been decided so far.
   - Add `## TODO` sections for unresolved questions.
   - Note at the top: `> **Status: Draft** — discussion ongoing, open questions remain.`
5. After saving, report the file path and remain in brainstorm mode. Saving does NOT exit.

## Multi-Session Support

When resuming a brainstorm across sessions, the saved spec serves as the starting point. The next session can read the partial spec and continue from where the discussion left off rather than restarting.
