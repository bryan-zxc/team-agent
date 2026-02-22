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

## Tickets
Always use the `github-board` skill (`/github-board`) for any ticket operations — creating, updating, transitioning status, or closing. If a ticket needs to change, edit the description to the correct version — describe clearly what is eventually done, not what changed from before. Never add comments to tickets.
