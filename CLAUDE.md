# Project Instructions

Read `NAVIGATION.md` before exploring the codebase. It documents the full folder structure, service boundaries, and key file locations — use it to narrow down scope of search and exploration.

This is a monorepo with three services under `services/`:
- `services/frontend/` — Next.js (TypeScript)
- `services/api/` — FastAPI (Python)
- `services/ai/` — AI Service (Python)

Each service has its own Dockerfile, dependencies, and tests. They communicate via Redis Pub/Sub and share a PostgreSQL database.

When working on the frontend, read `services/frontend/FRONTEND.md` first and follow its design system, styling, and component guidelines.

## Ticket Workflow
- When picking up a ticket: transition status to **In progress** on the project board
- When done with a ticket: transition status to **Done** on the project board and close the issue
- If a ticket needs to change or needs to be updated, just change the description, don't add a comment to the ticket

## Creating Tickets
- **Epic vs Story**: An epic is a large user-facing goal or milestone — done when its stories are all complete. A story is a deliverable slice of work that provides value on its own, belonging to an epic.
- **Naming**: Name tickets from the user's perspective (developers are users too). Describe the benefit, not the technical implementation. E.g. "Reproducible database setup across environments" not "Set up Alembic".
- **Context-rich descriptions**: Every ticket description must contain enough context for a brand new Claude Code session to pick it up and know exactly what to do — current state, what to build, file paths, data model references, and verification steps.
