---
name: ticket-workflow
description: End-to-end workflow for picking up and delivering a ticket. Use when the user says "pick up ticket", "work on ticket N", "start ticket", "grab the next ticket", or similar. Covers the full lifecycle from reading the ticket through to commit, push, and closing the issue.
---

# Ticket Workflow

Use `/github-board` for all ticket operations (status transitions, closing, editing descriptions).

## Workflow

### 1. Read and claim

- Fetch the ticket: `gh issue view <number> --repo bryan-zxc/team-agent`
- Transition to **In progress** via `/github-board`

### 2. Explore and discuss

Explore the codebase as needed — read files, trace code paths, check existing patterns. Use internet research (web search, documentation fetches) when the ticket involves unfamiliar libraries, APIs, or external integrations. Do **not** enter plan mode or start writing code yet.

Present findings to the user in conversation form:
- Summarise what the ticket requires
- Describe the intended approach
- If the solution is not obvious, present options with pros and cons and ask the user to choose

### 3. Mockup (frontend features)

For any ticket that changes the UI, create an HTML mockup **before** proceeding:

1. Write the mockup to `.mockups/<ticket-number>-<slug>.html` (self-contained, inline CSS)
2. Open with `/playwright-cli`: `playwright-cli open file://<absolute-path>`
3. Take a screenshot for the user: `playwright-cli screenshot`
4. Share the screenshot and discuss — iterate until the user is happy
5. When approved, delete the mockup file and close the browser

Only proceed once the user approves the mockup.

### 4. Plan and implement

Only after the user agrees with the approach (and mockup if applicable):

1. Enter plan mode
2. Write the plan, exit for approval
3. On approval, implement the changes

### 5. Test

Every ticket must be tested before completion.

**Frontend changes:** Use `/fe-testing` seed setup, then validate with `/playwright-cli` — open the app, navigate to the feature, interact, take screenshots, and verify the expected behaviour.

**Backend changes:** Run relevant backend tests. Unless the change is trivial, **also** do a frontend validation via `/playwright-cli` to confirm the backend change is reflected in the UI.

### 6. Complete

1. Commit and push to the current branch
2. Update the ticket description to reflect what was delivered (use `/github-board`)
3. Transition to **Done** and close the issue (use `/github-board`)
4. Check if the ticket belongs to an epic — if all sibling sub-issues are now closed, close the epic and trigger a release with `/release`
