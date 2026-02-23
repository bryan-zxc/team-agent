# ADR-0008: Repo Ownership via Manifest File

## Context

Projects in Team Agent are backed by a cloned git repository. Agent profiles (`.md` files) and workload branches all live in this repo. Nothing previously prevented two project instances — whether in the same environment or across environments (e.g. dev and prod) — from operating on the same git repo. This would cause agent profile collisions, merge conflicts between workloads, and general data integrity issues.

Additionally, when a user creates a project from a repo that already contains agent profiles from a previous project instance, the application had no way to detect this or decide how to handle the orphaned files.

A cross-environment ownership mechanism was needed that doesn't rely on a shared database, since dev and prod environments have separate databases.

## Alternatives Considered

**Database-only uniqueness constraint on `git_repo_url`**: Adding a `UNIQUE` constraint on the `projects.git_repo_url` column prevents duplicate repos within a single environment. Necessary but insufficient — two environments with separate databases could still both claim the same repo.

**Git tags as ownership markers**: Using tags like `team-agent/owned-by/<project-id>` to mark ownership. Lighter than committed files and doesn't pollute the working tree. Rejected because tags are easy to miss during inspection, harder to read programmatically, and don't carry structured metadata (environment, timestamps).

**No ownership model**: Rely on users to not reuse repos. Rejected — leads to silent data corruption when it inevitably happens.

## Decision

Every project claims ownership of its git repo by writing a **manifest file** at `.team-agent/manifest.json`. The manifest is committed and pushed on project creation. All project-scoped files (agent profiles, future configuration) live under `.team-agent/` rather than multiple dotfile directories at the repo root.

### Directory structure

```
.team-agent/
├── manifest.json
└── agents/
    ├── zimomo.md
    ├── vos.md
    └── ...
```

This replaces the previous `.agent/` directory. Agent profiles move to `.team-agent/agents/`.

### Manifest schema

```json
{
  "version": 1,
  "env": "dev",
  "project_id": "eb91f6be-...",
  "project_name": "popmart",
  "claimed_at": "2026-02-23T00:00:00Z"
}
```

A `version` field allows the schema to evolve without breaking older projects.

### Ownership check trigger points

1. **Project creation** — after cloning, inspect the manifest before any agent setup
2. **Project entry** — when a user navigates into a project from the selection page
3. **Before starting a workload** — belt-and-suspenders check before an agent makes commits
4. **Refresh action** — user-triggered git pull + re-validation on project cards (recovery path from lockdown)

### Pre-creation checks

The `projects` table has a `UNIQUE` constraint on `git_repo_url` to prevent duplicates within the same environment. Before setting up a project, the repo is cloned and the manifest inspected:

- **No manifest**: repo is unclaimed — proceed with project creation, write and push the manifest.
- **Manifest with `env: "prod"`**: hard block — the repo is owned by a production instance. Clone is removed and the user must pick a different repo.
- **Manifest with any other env**: the user is offered a choice to overwrite the manifest, purge `.team-agent/agents/`, and start fresh.

### Enforcement on project entry

On every project entry, the manifest is validated against the database record. If ownership doesn't match:

- **Production**: force-correct the manifest from the database and push. If the push fails, the project enters lockdown. The correct manifest JSON is shown to the user with an explanation of the situation, and the user resolves it offline.
- **Dev/other environments**: immediate lockdown. Developers can fix the repo offline or create a new project with a different repo.

### Lockdown mode

A locked project is read-only — users can browse chat history and files but cannot send messages, create rooms, edit files, or trigger workloads. The project view shows a persistent warning banner explaining the lockdown reason and displaying the correct manifest. On the project selection page, locked projects have a distinct visual treatment. A refresh button on project cards triggers a git pull followed by manifest re-validation; if the manifest is now correct, lockdown is lifted.

### Agent profile commits

When an agent profile is created (coordinator on project setup, delegate agents on-the-fly), the profile file is committed to the repo and pushed. This ensures the main branch always has commit history (required for worktree branching and merges) and that agent profiles are version-controlled.

## Consequences

- Repos cannot be silently shared between project instances — ownership is explicit and enforced
- Production environments are protected from accidental or rogue changes to the manifest
- Dev environments fail fast on ownership conflicts rather than accumulating subtle corruption
- The `.team-agent/` directory becomes the single namespace for all project-scoped repo files, avoiding dotfile proliferation at the repo root
- All existing references to `.agent/` must be migrated to `.team-agent/agents/`
- Projects that cannot push the manifest (e.g. due to branch protection rules or missing write access) cannot be created — write access to the repo is now a hard requirement
- The manifest file is a new committed file in user repos, which some users may find unexpected — the `.team-agent/` namespace makes its purpose clear
