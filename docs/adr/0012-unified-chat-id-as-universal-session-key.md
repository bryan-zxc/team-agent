# ADR-0012: Unified chat_id as universal session key

## Context

The system manages two types of Claude Code sessions: **workload sessions** (task-specific, running on git worktrees) and **admin sessions** (general-purpose, running on the project clone directory). Both are backed by the same SDK, relay loop, tool approval flow, screencast, and heartbeat infrastructure.

Initially, workload sessions were keyed by `workload_id` throughout the stack — the AI service session registry, Redis channels (`workload:messages`), API endpoints (`/workloads/{workload_id}/interrupt`), status events, screencast frames, and frontend props. When admin sessions were introduced (ticket #71), they naturally used `chat_id` as their key, since admin chats have no associated workload record.

This created a dual-key system with two parallel code paths for identical logic: separate Redis channels (`workload:messages` and `admin:messages`), separate listeners, separate API endpoints, separate frontend prop chains, and a `session_key` abstraction that papered over the inconsistency. Every shared function needed both `session_key` and `chat_id` parameters because they could differ for workloads.

There is a strict 1:1 mapping between workloads and their chats — each workload has exactly one chat of type `workload`. The `workload_id` as a routing key was an incidental choice from when workloads were the only session type, not a deliberate design decision.

## Alternatives Considered

**Keep the dual-key system with a `session_key` abstraction.** The `session_key` parameter (workload_id for workloads, chat_id for admin) could unify at the function signature level. However, this leaves duplicate Redis channels, duplicate listeners, duplicate API endpoints, and requires every status event to carry both `session_key` and `chat_id`. The abstraction leaks everywhere — the frontend needs to know which key to send, the API needs to know which AI service endpoint to proxy to, and tool approval events carry `workload_id` even for admin sessions.

**Use `workload_id` for both by creating synthetic workload records for admin sessions.** This preserves the existing key but requires dummy database records and conflates the workload concept (task metadata: title, description, worktree branch) with session identity.

## Decision

Use `chat_id` as the universal session key across the entire stack. `workload_id` becomes pure metadata — it remains as a database foreign key (`Chat.workload_id → Workload.id`) and in API responses for display, but is never used for routing, registry lookups, events, or API endpoints.

Specifically:

- **AI service session registry** (`_sessions` dict): keyed by `chat_id` for both session types
- **Redis channels**: single `chat:messages` channel replaces `workload:messages` + `admin:messages`; `tool:approvals` uses `chat_id` field; `screencast:frames:{chat_id}`
- **AI service endpoints**: unified `/chats/{chat_id}/interrupt` and `/chats/{chat_id}/cancel`
- **API service endpoints**: `/chats/{chat_id}/tool-approval`, `/cancel`, `/interrupt`, `/switch-mode`, `PATCH /chats/{chat_id}`; only `POST /workloads/dispatch` remains workload-specific
- **Status events**: `chat_type` field (`"workload"` or `"admin"`) replaces the presence/absence of `workload_id` for event discrimination
- **Frontend**: all API calls and event matching use `chatId` (already available as `w.id` in the workload list)
- **Unified `stop_session()`**: single function replaces `stop_workload_session()` and `stop_admin_session()`
- **Unified listener**: `listen_chat_messages()` replaces `listen_workload_messages()` + `listen_admin_messages()`, with resume logic branching on chat type from the database

## Consequences

**Positive:**

- Eliminates ~150 lines of duplicated listener, stop, and shutdown code
- Single Redis channel and single listener for all human-to-session messaging
- Frontend components use `w.id` (already available) instead of threading `workload_id` through props
- New session types (if added) automatically work with the existing infrastructure — just register by `chat_id`
- `publish_status_event` drops the confusing `session_key` parameter — only `chat_id` needed
- API endpoint structure is cleaner: `/chats/{chat_id}/*` for session operations, `/workloads/*` only for workload-specific operations (dispatch)

**Negative:**

- `fetch_workload_data_for_resume()` reverses its lookup direction (from `WHERE w.id = $1` to `WHERE c.id = $1`), which is marginally less direct
- The unified `_resume_and_deliver()` must try both workload and admin lookups sequentially to determine session type
- External systems that reference `workload_id` in Redis messages (if any) would break — but all producers are internal
