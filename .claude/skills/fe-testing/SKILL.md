---
name: fe-testing
description: Frontend testing workflow for the Team Agent project. Use when verifying frontend features with Playwright, setting up test database state, or running UI tests. Triggers on frontend testing, Playwright verification, UI testing, test setup, seed database, or verifying a feature in the browser.
---

# Frontend Testing

For Playwright command reference, use `/playwright-cli`.

## Headed mode

Always run Playwright in headed mode so the user can watch the test in real time:

```bash
PLAYWRIGHT_MCP_SANDBOX=false playwright-cli open http://localhost:3000 --headed
```

Both `--headed` and `PLAYWRIGHT_MCP_SANDBOX=false` are required — without them the browser is invisible to the user.

## Seed Scenarios

Seeds run inside Docker. Each drops all tables and rebuilds from scratch, but **does not** clean up cloned project files on disk. Always wipe `/data/projects/` before re-seeding to avoid stale directories from previous runs.

### Seed commands

Always run the cleanup command first, then the seed:

```bash
docker compose exec api rm -rf /data/projects/*
docker compose exec api .venv/bin/python db/seeds/with_project.py
```

| Scenario | Seed command | State |
|---|---|---|
| **clean** | `db/seeds/clean.py` | Users only (Alice, Bob). No projects. |
| **with_project** | `db/seeds/with_project.py` | Users + popmart project (git clone, manifest, Zimomo AI, 3 members, initial commit). |

### Choosing a scenario

- **clean** — project creation flow, empty states, landing page with no projects
- **with_project** — chat, member management, agent interactions, room navigation

## Pre-test checklist

1. Services running: `docker compose up -d`
2. Wipe stale project files: `docker compose exec api rm -rf /data/projects/*`
3. Run the appropriate seed
4. Open: `PLAYWRIGHT_MCP_SANDBOX=false playwright-cli open http://localhost:3000 --headed`

Always wipe and re-seed before a test run — seeds are destructive (DROP + CREATE) but only clean the database, not the filesystem.

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

## Test Scenarios

Detailed, repeatable test scenarios live in the `scenarios/` folder. Each file covers setup, step-by-step instructions, verification commands, and common failure modes.

| Scenario | File | Seed | What it tests |
|---|---|---|---|
| **Workload Creates a File** | [workload-creates-file.md](scenarios/workload-creates-file.md) | `with_project` | Full workload pipeline: @mention → agent assignment → file creation → auto-commit → merge → push to GitHub |
| **Project Lockdown** | [project-lockdown.md](scenarios/project-lockdown.md) | `with_project` | Locked card treatment, workbench lockdown banner, disabled controls, refresh-to-unlock flow |

## Notes

- `with_project` seed performs a real git clone — requires network access from Docker
- `with_project` writes `.team-agent/manifest.json` and `.team-agent/agents/zimomo.md`, then commits locally (no push)
- User selection is stored in `localStorage` as `user_id` — persists across navigations
- Projects have `is_locked` / `lock_reason` columns — set `is_locked=true` in DB to test lockdown UI
- Use `playwright-cli snapshot` after each navigation to inspect element tree
- Use `playwright-cli screenshot` to capture visual state
