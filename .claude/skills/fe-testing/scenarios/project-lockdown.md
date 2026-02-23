# Scenario: Project Lockdown

Verifies the lockdown UI: locked project card treatment, workbench lockdown banner, disabled mutating controls, and the refresh button unlocking flow.

## Setup

```bash
docker compose exec api bash -c 'rm -rf /data/projects/*'
docker compose exec api .venv/bin/python db/seeds/with_project.py
```

## Steps

### Lock the project

```bash
docker compose exec postgres psql -U teamagent -d teamagent -c \
  "UPDATE projects SET is_locked = true, lock_reason = 'Manifest mismatch — another environment claimed this repo';"
```

### Verify locked project card

1. `playwright-cli open http://localhost:3000`
2. Select a user (Alice)
3. Observe the project card — should show:
   - Lock icon instead of initial letter
   - "Locked" badge next to the project name
   - Reduced opacity
   - Red-tinted border

### Verify workbench lockdown

4. Click the locked project card to enter
5. Observe:
   - Red lockdown banner at top: "Project locked — Manifest mismatch — ..."
   - Create room "+" button hidden
6. Click Members tab
7. Observe: "Add Member" button hidden

### Verify unlock via refresh

8. Navigate back to home: `playwright-cli open http://localhost:3000`
9. Click the refresh button on the project card
10. Observe: lock icon, badge, and reduced opacity disappear (manifest is valid, project unlocks)
11. Click the project card to enter
12. Observe: no lockdown banner, "+" button visible, Add Member visible

## Verification

### DB state after lock

```bash
docker compose exec postgres psql -U teamagent -d teamagent -c "SELECT name, is_locked, lock_reason FROM projects;"
```

### DB state after refresh (unlock)

```bash
docker compose exec postgres psql -U teamagent -d teamagent -c "SELECT name, is_locked, lock_reason FROM projects;"
```

Expected: `is_locked = false`, `lock_reason` empty.

## What Can Go Wrong

| Symptom | Cause |
|---|---|
| Refresh doesn't unlock | Manifest file missing or `project_id` mismatch in `.team-agent/manifest.json` |
| Banner doesn't show | Frontend not rebuilt after code changes — `docker compose up -d --build frontend` |
| Mutating controls still visible when locked | `isLocked` not propagated to child components |
