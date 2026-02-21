---
name: fe-testing
description: Frontend testing workflow for the Team Agent project. Use when verifying frontend features with Playwright, setting up test database state, or running UI tests. Triggers on frontend testing, Playwright verification, UI testing, test setup, seed database, or verifying a feature in the browser.
---

# Frontend Testing

For Playwright command reference, use `/playwright-cli`.

## Seed Scenarios

Seeds run inside Docker. Each drops all tables and rebuilds from scratch.

| Scenario | Command | State |
|---|---|---|
| **clean** | `docker compose exec api .venv/bin/python db/seeds/clean.py` | Users only (Alice, Bob). No projects. |
| **with_project** | `docker compose exec api .venv/bin/python db/seeds/with_project.py` | Users + popmart project (git clone, Zimomo AI, General room, 3 members). |

### Choosing a scenario

- **clean** — project creation flow, empty states, landing page with no projects
- **with_project** — chat, member management, agent interactions, room navigation

## Pre-test checklist

1. Services running: `docker compose up -d`
2. Run the appropriate seed
3. Open: `playwright-cli open http://localhost:3000`

Always re-seed before a test run — seeds are destructive (DROP + CREATE).

## Common flows

### Project creation (clean seed)

1. Select user from picker (e.g. click Alice)
2. Click "+ New Project"
3. Fill project name and git repo URL (`https://github.com/bryan-zxc/popmart.git`)
4. Submit → redirects to project dashboard
5. Verify: sidebar shows General room, members (creator + Zimomo)

### Chat with AI mention (with_project seed)

1. Select user, click popmart project card
2. Click General room in sidebar
3. Type message with `@Zimomo` → send
4. Verify: Zimomo's response appears in chat

### Member profile (with_project seed)

1. Select user, enter popmart project
2. Click a member name in sidebar
3. Verify: profile page renders with name and content

## Notes

- `with_project` seed performs a real git clone — requires network access from Docker
- User selection is stored in `localStorage` as `user_id` — persists across navigations
- Use `playwright-cli snapshot` after each navigation to inspect element tree
- Use `playwright-cli screenshot` to capture visual state
