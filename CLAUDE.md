# Project Instructions

Read `NAVIGATION.md` before exploring the codebase. It documents the full folder structure, service boundaries, and key file locations — use it to narrow down scope of search and exploration.

This is a monorepo with three services under `services/`:
- `services/frontend/` — Next.js (TypeScript)
- `services/api/` — FastAPI (Python)
- `services/ai/` — AI Service (Python)

Each service has its own Dockerfile, dependencies, and tests. They communicate via Redis Pub/Sub and share a PostgreSQL database.
