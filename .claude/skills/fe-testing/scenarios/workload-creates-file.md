# Scenario: Workload Creates a File

Verifies the full workload pipeline: user sends an @mention → Zimomo assigns a delegate agent → agent creates a file in its worktree → Stop hook auto-commits, merges to main, and pushes to GitHub.

## Prerequisites

- `gh auth login` completed inside the ai-service container (persisted in `gh_auth` volume)
- Services running with ai-service rebuilt: `docker compose up -d --build ai-service`

## Setup

```bash
docker compose exec api bash -c 'rm -rf /data/projects/*'
docker compose exec api .venv/bin/python db/seeds/with_project.py
```

Push the seed commit so GitHub has a baseline:

```bash
docker compose exec ai-service bash -c 'cd /data/projects/*/repo && git push'
```

## Steps

1. `playwright-cli open http://localhost:3000`
2. Select a user (e.g. Alice) from the picker
3. Click the popmart project card
4. Create a room: click "+" → press Enter (accepts random name)
5. Click the new room to open the chat tab
6. Click the message input, type a message like:
   ```
   @Zimomo create a markdown file called ARCHITECTURE.md in the repo root that describes a simple 3-tier web architecture
   ```
7. Press Enter to send
8. Wait ~40 seconds for the workload to complete

## Verification

### Logs (ai-service)

```bash
docker compose logs ai-service --tail 20
```

Expected log lines (in order):
- `Committed: Add agent profile: <name>` — delegate agent created
- `Pushed to remote` — agent profile pushed to GitHub
- `Persisted 1 workloads: <name>: <title>` — workload created
- `Created worktree at ...` — isolated worktree for the agent
- `auto-committed uncommitted changes` — Stop hook committed the agent's work
- `merge succeeded on attempt 1` — merged worktree branch into main
- `pushed merged changes to remote` — pushed to GitHub
- `completed (session: ..., error: False, turns: N)` — workload finished
- `POST .../check-manifest?pull=false "HTTP/1.1 200 OK"` — manifest check passed

### Local repo

```bash
docker compose exec ai-service bash -c 'cd /data/projects/*/repo && git log --oneline -5 && echo "---" && cat ARCHITECTURE.md'
```

Expected: 3 commits (seed, agent profile, workload auto-commit) and the file content.

### GitHub

```bash
gh api repos/bryan-zxc/popmart/contents/ARCHITECTURE.md --jq '.name + " (" + (.size | tostring) + " bytes)"'
```

Expected: file exists with non-zero size.

### Chat UI

Take a snapshot and verify:
- Zimomo's assignment message: "Workloads assigned: - <agent>: <title>"
- Zimomo's summary message: "Workload **<title>** has finished and its changes have been merged to main."

### Worktree cleanup

```bash
docker compose exec ai-service bash -c 'cd /data/projects/*/repo && git worktree list'
```

Expected: only the main repo listed (worktree was removed after merge).

## What Can Go Wrong

| Symptom | Cause |
|---|---|
| `git push failed (non-blocking): fatal: could not read Username` | `gh auth login` not done in ai-service container |
| No "auto-committed" log line, merge is no-op | Agent didn't write any files (check permission mode, agent turns) |
| `merge conflict` in logs | Unlikely for a new file — check if the file already exists on main |
| Workload status `error` in DB | Claude Code subprocess crashed — check full ai-service logs |
