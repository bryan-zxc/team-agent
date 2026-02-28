---
name: ticket-workflow
description: End-to-end workflow for picking up and delivering a ticket. Use when the user says "pick up ticket", "work on ticket N", "start ticket", "grab the next ticket", or similar. Covers the full lifecycle from reading the ticket through to commit, push, and completing the ticket on the board.
---

# Ticket Workflow

Use `/github-board` for all ticket operations (status transitions, completing, editing descriptions).

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
2. Start a local HTTP server in the `.mockups/` directory:
   ```bash
   cd <repo-root>/.mockups && python3 -m http.server 8765 &>/dev/null &
   ```
3. Open in **headed** Playwright so the user can see it:
   ```bash
   PLAYWRIGHT_MCP_SANDBOX=false playwright-cli open http://localhost:8765/<filename>.html --headed
   ```
4. Take a screenshot for the user: `playwright-cli screenshot`
5. Share the screenshot and discuss — iterate until the user is happy
6. When approved, delete the mockup file, close the browser, and kill the HTTP server

Only proceed once the user approves the mockup.

### 4. Plan and implement

Only after the user agrees with the approach (and mockup if applicable):

1. Enter plan mode
2. Write the plan, exit for approval
3. On approval, implement the changes

### 5. Test

Every ticket must be tested before completion.

**Frontend changes:** Use `/fe-testing` for seed setup and Playwright validation — open the app, navigate to the feature, interact, take screenshots, and verify the expected behaviour.

**Backend changes:** Run relevant backend tests. Unless the change is trivial, **also** do a frontend validation via `/fe-testing` to confirm the backend change is reflected in the UI.

### 6. Complete

1. Commit and push to the current branch
2. Update the ticket description to reflect what was delivered
3. Transition board status to **Done** via `/github-board`

### 7. Check for epic completion

After completing the ticket, check whether it belongs to a parent epic and whether that epic is now fully delivered.

**Find the parent epic (must use GraphQL — REST API does not expose the parent field):**

```bash
PARENT=$(gh api graphql -f query='
  query {
    repository(owner: "bryan-zxc", name: "team-agent") {
      issue(number: <TICKET_NUMBER>) {
        parent { number }
      }
    }
  }' --jq '.data.repository.issue.parent.number // empty')
```

If `PARENT` is empty, there is no parent epic — stop here.

**Check if all sub-issues of the epic are Done on the board:**

```bash
gh api graphql -f query='
  query {
    repository(owner: "bryan-zxc", name: "team-agent") {
      issue(number: <EPIC_NUMBER>) {
        subIssues(first: 50) {
          nodes {
            number
            title
            projectItems(first: 5) {
              nodes {
                fieldValueByName(name: "Status") {
                  ... on ProjectV2ItemFieldSingleSelectValue {
                    name
                  }
                }
              }
            }
          }
        }
      }
    }
  }' --jq '.data.repository.issue.subIssues.nodes[] | select(.projectItems.nodes[0].fieldValueByName.name != "Done") | .number'
```

If the output is empty (all sub-issues have board status "Done"), transition the epic to **Done** via `/github-board` and trigger a release with `/release`.
