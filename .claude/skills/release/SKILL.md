---
name: release
description: Create a release by merging develop into main and tagging a version. Triggers the CI/CD pipeline which builds Docker images and deploys to production. Use when the user asks to release, deploy, cut a release, bump a version, or ship to production.
---

# Release

Merge develop into main, tag a semver release, and push to trigger the CI/CD
deployment pipeline (`.github/workflows/deploy.yml`).

## Usage

```
/release [major|minor|patch|vX.Y.Z]
```

If a bump type or specific version is provided, use it as the starting
recommendation. If no argument is given, analyse the changes to recommend a
version. In all cases, present the recommendation and wait for user approval.

## Workflow

### 1. Ensure working tree is clean and sync local branches

```bash
git status --porcelain
```

If there are uncommitted changes, warn the user and stop.

Then sync local branches with origin so all comparisons are accurate:

```bash
git fetch origin main develop
git checkout develop
git pull origin develop
git checkout main
git pull origin main
git checkout develop
```

### 2. Determine the current version

Read the latest version tag from git:

```bash
git tag --list 'v*' --sort=-version:refname | head -1
```

If no tags exist, the current version is `v0.0.0`.

### 3. Analyse changes

Run:

```bash
git log main..develop --oneline
git diff main..develop --stat
```

Read the commit list and file-level diff summary. For key files with
significant changes, read the full diff to understand the scope:

```bash
git diff main..develop -- <file>
```

Based on the analysis, recommend a bump type:

- **major** — breaking changes, API contract changes, incompatible migrations
- **minor** — new features, new endpoints, new UI capabilities
- **patch** — bug fixes, refactors, dependency updates, config changes

Compute the proposed next version by bumping from the current version.

### 4. Confirm with the user

Present:
- Current version (latest tag, or "no previous release")
- Proposed next version and bump type
- Why this bump type was recommended (brief summary of what changed)
- Commit list
- Files changed summary (`--stat` output)

Wait for the user to approve, change the version, or cancel. Never proceed
without explicit approval.

### 5. Merge develop into main

```bash
git checkout main
git merge develop --ff-only
```

Fast-forward only. If it fails (main has diverged), stop and explain.

### 6. Create the annotated tag

```bash
git tag -a vX.Y.Z -m "Release vX.Y.Z"
```

### 7. Push main and tag

```bash
git push origin main --follow-tags
```

This triggers the GitHub Actions deploy workflow automatically.

### 8. Switch back to develop

```bash
git checkout develop
```

### 9. Monitor deployment

Poll the workflow run until it completes:

```bash
# Get the latest run triggered by the push
RUN_ID=$(gh run list --repo bryan-zxc/team-agent --branch main --limit 1 --json databaseId --jq '.[0].databaseId')

# Poll until complete (check every 30s)
gh run watch "$RUN_ID" --repo bryan-zxc/team-agent
```

If the run **succeeds**, report the result and finish.

If the run **fails**:

1. Fetch the logs to identify the failure:
   ```bash
   gh run view "$RUN_ID" --repo bryan-zxc/team-agent --log-failed
   ```
2. Diagnose the root cause from the logs
3. Fix the issue on develop, commit and push
4. Re-merge develop into main and push (no new tag — reuse the existing one):
   ```bash
   git checkout main && git pull origin main
   git merge develop --ff-only
   git push origin main
   git checkout develop
   ```
5. This triggers a new workflow run — go back to the polling step
6. Repeat until deployment succeeds

### 10. Report result

Print:
- The version released (e.g. `v0.2.0`)
- Link to the successful run
- Confirm deployment is live

## Rules

- Never auto-decide a version — always present a recommendation and wait for user approval
- Never force-push to main
- Always use `--ff-only` for the merge — if it fails, stop and explain
- Always return to the develop branch after the release
- If any step fails, stop immediately and report the error
- Production deploys from **main only** — the CI/CD pipeline triggers on push to main, builds from main, and the Mac Mini checks out and runs main. Never deploy from develop.
