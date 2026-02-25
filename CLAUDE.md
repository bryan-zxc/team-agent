# Project Instructions

Read `NAVIGATION.md` before exploring the codebase. It documents the full folder structure, service boundaries, and key file locations — use it to narrow down scope of search and exploration.

This is a monorepo with three services under `services/`:
- `services/frontend/` — Next.js (TypeScript)
- `services/api/` — FastAPI (Python)
- `services/ai/` — AI Service (Python)

Each service has its own Dockerfile, dependencies, and tests. They communicate via Redis Pub/Sub and share a PostgreSQL database.

## Dependencies
Always use `uv add <package>` to add Python dependencies. Never edit `pyproject.toml` directly — `uv add` resolves the latest version and updates the lock file automatically.

When working on the frontend, the `fe-dev` skill provides the design system, styling rules, and component guidelines.

## Git
Always include `.claude/settings.local.json` when committing — do not exclude it from staged changes.

## Releases
Use the `release` skill (`/release`) to deploy to production. Prefer rapid, small releases over large batches. Bug fixes are always standalone patch releases. Feature work gravitates towards a one-to-one relationship between epic and release.

### Versioning (semver)
- **Minor bump** — users can do something they couldn't before. New feature, new capability, new screen, new endpoint. Completing an epic typically warrants a minor bump.
- **Patch bump** — existing things work better or are fixed. Bug fixes, refactors, infra changes, config tweaks, performance improvements, dependency updates.
- The test: "Can users do something new?" If yes, minor. If no, patch.

## Tickets
Always use the `github-board` skill (`/github-board`) for any ticket operations — creating, updating, transitioning status, or closing. If a ticket needs to change, edit the description to the correct version — describe clearly what is eventually done, not what changed from before. Never add comments to tickets.
