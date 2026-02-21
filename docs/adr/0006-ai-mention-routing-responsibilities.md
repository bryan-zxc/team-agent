# ADR-0006: AI Mention Routing Responsibilities

## Context

When a user sends a message mentioning an AI agent, something needs to detect the mention, trigger the AI service, and determine who responds. The previous design had the AI service listener subscribing to all chat messages, performing string matching to detect `@name` mentions, looking up member info, and deciding whether to respond. This mixed routing logic (should AI respond?) with domain logic (who responds and how?) and duplicated member data across services.

## Alternatives Considered

**AI service owns everything**: The listener subscribes to all messages, checks for mentions, resolves members, runs the agent, and publishes the response. This is what existed before — it works but the listener receives every message (wasteful), does brittle string matching, and needs access to member type data that belongs to the API domain.

**API resolves full context**: The API checks for AI mentions and publishes the mentioned member's identity (id, display_name, project_name) to Redis. The listener uses this pre-resolved context directly. Cleaner, but the API is making decisions about AI service internals — which member responds is the AI service's domain, not the API's.

**API does binary check, AI service resolves everything from DB**: The API checks one thing — does this message mention any AI member? If yes, it publishes just the `chat_id`. The AI service derives everything from the database: project (via `chat → room → project`), orchestrator identity (Zimomo's member_id), conversation history.

## Decision

Adopt the minimal-payload approach. Each service has a single, clear responsibility:

**API service**: Binary gate. After persisting a message, check if any UUID in the `mentions` array belongs to an AI member (`type == 'ai'`). If yes, publish one `{"chat_id": "..."}` event to the `ai:respond` Redis channel. No member identity, no project info — just the chat_id.

**Redis `ai:respond` channel**: Carries only `{chat_id}`. Replaces the old `chat:messages` channel which broadcast every message. Redis is only used when AI actually needs to respond.

**AI service listener**: Receives `{chat_id}` and resolves everything from the database:
- Project name via `chats → rooms → projects`
- Orchestrator identity (Zimomo) via `chats → rooms → project_members`
- Conversation history via `messages` joined to `project_members`

The AI service decides who responds (currently always Zimomo as the orchestrator) and publishes the full response to `chat:responses` with member_id, display_name, and type — all resolved internally.

## Consequences

- The API has zero knowledge of AI service internals — it doesn't know who Zimomo is or how responses are generated
- The Redis payload is minimal (`chat_id` only) — no redundant data, single source of truth is the database
- The AI service is self-contained: given a chat_id, it can derive the full context needed to respond
- Only one `ai:respond` event fires per message, regardless of how many AI members are mentioned
- The message must be committed to the database before Redis publish, so the AI service always sees the triggering message when loading history — this is guaranteed by the sequential flow in the WebSocket handler
- Changing the orchestrator logic (e.g. per-project orchestrators, multi-agent responses) only requires changes in the AI service
