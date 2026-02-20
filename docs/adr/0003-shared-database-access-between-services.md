# ADR-0003: Shared Database Access Between Services

## Context

The API service and AI service both need access to PostgreSQL data. The API service owns the core data models (users, projects, project_members, rooms, messages) and serves the frontend. The AI service needs to read chat history and member identity for the listener pipeline, write to its own `llm_usage` table for cost tracking, and insert new `project_members` records when generating agent profiles.

The question was whether the AI service should access the database directly or route all operations through the API service via HTTP endpoints.

## Alternatives Considered

**API-mediated writes**: AI service reads the database directly but routes all writes through API endpoints. This centralises mutation logic but adds HTTP roundtrips, failure modes, and requires building internal endpoints that serve no other purpose.

**Full API mediation**: AI service has no database access at all — all reads and writes go through the API. This adds latency to the real-time listener pipeline (which needs full chat history on every @mention trigger) and creates unnecessary coupling for fire-and-forget operations like cost tracking.

## Decision

Both services connect directly to the same PostgreSQL instance as peers. Each service can read and write any table. Database constraints (unique constraints, foreign keys) enforce integrity regardless of which service performs the operation.

In practice:
- The AI service uses **SQLAlchemy** for tables it owns (`llm_usage`) and **raw asyncpg** for shared tables (`project_members`, `messages`, etc.)
- The API service uses SQLAlchemy for everything
- Each write operation lives in the service where the operation logically belongs — e.g. agent creation is an AI concern, so the `project_members` insert lives in the AI service's `agents.py`

## Consequences

- The listener pipeline stays fast — no HTTP roundtrip to fetch chat history on every @mention
- Cost tracking writes happen in the hot path without added latency
- Agent profile generation atomically creates both the database record and markdown file without cross-service coordination
- If business logic around shared tables grows (e.g. validation rules on member creation), it may need to be duplicated across services or consolidated later
- Schema changes to shared tables require awareness across both services
