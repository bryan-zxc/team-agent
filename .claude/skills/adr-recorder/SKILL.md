---
name: adr-recorder
description: Record architecture decision records (ADRs) after completing tasks. Use this skill proactively at the end of any task that involved an architectural or design decision — technology choices, patterns, trade-offs, structural changes, or infrastructure decisions. Do NOT trigger for routine code changes, bug fixes, or minor refactors that don't involve a design choice.
---

# ADR Recorder

Record architecture decisions in `docs/adr/`.

## Workflow

### 1. Assess

After completing a task, assess whether any design decisions were made that are worth recording. A decision is worth recording if it:

- Chose between multiple viable approaches
- Established a pattern others should follow
- Has consequences that affect future work
- Would be non-obvious to someone joining the project

If no decision is worth recording, stop here.

### 2. Confirm with user

Present the proposed ADR title and a one-sentence summary. Ask the user to confirm before proceeding. If the user declines, stop.

### 3. Scan for conflicts

Read `docs/adr/adr.md` and all existing ADR files. Check whether the new decision contradicts or supersedes any existing decision. If a conflict is found:

- Present the conflict to the user: the new decision vs the existing ADR
- Ask the user how to proceed: supersede the old ADR, modify the new one, or skip
- If superseding: delete the old ADR file and its row from `docs/adr/adr.md`

### 4. Determine the next ADR number

Read `docs/adr/adr.md` and find the highest existing ADR number. The new ADR gets that number + 1.

### 5. Create the ADR file

Create `docs/adr/NNNN-kebab-case-title.md` with this structure:

```markdown
# ADR-NNNN: Title of Decision

## Context

What prompted this decision. What existed before. What constraints applied.
Include historical context so the reader understands the full picture without
needing to find prior ADRs.

## Alternatives Considered

(Optional — only include if alternatives were actually evaluated.)

What other options were considered, with brief pros/cons for each.

## Decision

What was decided and why. Be specific — name technologies, patterns, trade-offs.

## Consequences

What follows — positive and negative. What becomes easier, what becomes harder.
```

Rules:
- No date inside the ADR file — the date lives only in `docs/adr/adr.md`
- Alternatives Considered section is optional — omit it entirely if no alternatives were evaluated
- Use Australian English spelling

### 6. Update the index

Add a new row to the **top** of the table in `docs/adr/adr.md` (newest first):

```markdown
| NNNN | YYYY-MM-DD | Title | One-line description | [ADR-NNNN](NNNN-kebab-case-title.md) |
```
