---
name: adr-recorder
description: Record architecture decision records (ADRs). Activate this skill in two situations: (1) Before every git commit — always assess whether the changes being committed involve a design decision worth recording. (2) At the end of any task that involved an architectural or design decision — technology choices, patterns, trade-offs, structural changes, or infrastructure decisions.
---

# ADR Recorder

Record architecture decisions in `docs/adr/`.

## Workflow

### 1. Assess

Assess whether any design decisions were made that are worth recording. Do not record routine code changes, bug fixes, or minor refactors that don't involve a design choice. A decision is worth recording if it:

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
- If superseding: delete the old ADR file and its row from `docs/adr/adr.md`. The new ADR must stand on its own - do not reference the superseded ADR or describe what changed

### 4. Determine the next ADR number

Read `docs/adr/adr.md` and find the highest existing ADR number. The new ADR gets that number + 1.

### 5. Create the ADR file

Create `docs/adr/NNNN-kebab-case-title.md` with this structure:

```markdown
# ADR-NNNN: Title of Decision

## Context

Why this decision exists - the problem space, constraints, and requirements that make this decision necessary. Describe the situation a developer faces when this decision is relevant.

DO NOT describe what existed before, what was changed, or migration history. ADRs are forward-looking rules, not change logs. A developer reading this ADR should understand what rule to follow and why, not what the codebase used to look like.

## Alternatives Considered

(Optional — only include if alternatives were actually evaluated.)

Other approaches that were considered, with brief rationale for why each was not chosen. It is irrelevant whether an alternative is something the project previously used - just articulate why it is not the best choice as an approach.

## Decision

What the decision is and why. Be specific - name technologies, patterns, trade-offs. State the end point outcome (what IS), not the journey (what changed).

## Consequences

What follows from this decision. What it enables, what constraints it imposes.
```

Rules:
- No date inside the ADR file — the date lives only in `docs/adr/adr.md`
- Alternatives Considered section is optional — omit it entirely if no alternatives were evaluated
- Use Australian English spelling
- Never describe history - ADRs state teh current decision, not how we got here. A reader should be able to check compliance against the ADR without landing on content regarding out dated decisions which is important as AI is doing the documentation work.

### 6. Update the index

Add a new row to the **top** of the table in `docs/adr/adr.md` (newest first):

```markdown
| NNNN | YYYY-MM-DD | Title | One-line description | [ADR-NNNN](NNNN-kebab-case-title.md) |
```
