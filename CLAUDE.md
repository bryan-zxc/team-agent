# Project Instructions

Read `NAVIGATION.md` before exploring the codebase. It documents the full folder structure, service boundaries, and key file locations — use it to narrow down scope of search and exploration.

This is a monorepo with three services under `services/`:
- `services/frontend/` — Next.js (TypeScript)
- `services/api/` — FastAPI (Python)
- `services/ai/` — AI Service (Python)

Each service has its own Dockerfile, dependencies, and tests. They communicate via Redis Pub/Sub and share a PostgreSQL database.

## Ticket Workflow
- When picking up a ticket: transition status to **In progress** on the project board
- When done with a ticket: transition status to **Done** on the project board and close the issue
- If a ticket needs to change or needs to be updated, just change the description, don't add a comment to the ticket

## Epic vs Story
- **Epic** — a large user-facing goal or milestone (e.g. "Stand up a bare minimum working system"). An epic is done when its stories are all complete.
- **Story** — a deliverable slice of work that provides value on its own (e.g. "Send and receive messages in real-time"). Stories belong to an epic.
- Name tickets from the user's perspective (developers are users too). Describe the benefit, not the technical implementation. E.g. "Reproducible database setup across environments" not "Set up Alembic".
