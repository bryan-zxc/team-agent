# ADR-0004: Hybrid Inter-Service Communication

## Context

The API service and AI service need to communicate for two distinct purposes: broadcasting chat messages (asynchronous, event-driven) and requesting operations like agent creation (synchronous, request-response). The original architecture routed all inter-service communication through Redis pub/sub, following the principle "all cross-service messaging goes through Redis."

Redis pub/sub works naturally for chat messages — the API service publishes, the AI service subscribes and decides whether to respond. But for request-response operations (e.g. "create an agent and return the result"), pub/sub requires workarounds: generating request IDs, subscribing before publishing to avoid race conditions, looping over messages to match responses, and implementing manual timeouts. As more command-type interactions emerge (agent lifecycle management, status queries), this pattern would need repeating for each one.

## Alternatives Considered

**Pure Redis pub/sub**: All communication through Redis. Natural for events but awkward for commands — simulates HTTP request-response on top of a broadcast mechanism. Error handling is weak (pub/sub silently drops messages if no subscriber is listening). Each new command requires the same request-ID-matching boilerplate.

**Pure HTTP**: All communication through HTTP. Natural for commands but awkward for events — the API service would need to POST every chat message to the AI service, and the AI service would need to POST responses back, creating bidirectional HTTP coupling. Loses the broadcast benefit where multiple subscribers can observe messages without the publisher knowing about them.

**WebSocket between services**: Persistent bidirectional connection. Functionally equivalent to Redis pub/sub but without the broker — requires managing connection lifecycle, reconnection logic, and doesn't scale to multiple subscribers without additional connections.

## Decision

Use Redis pub/sub for asynchronous events and HTTP for synchronous commands. The AI service exposes a lightweight FastAPI server for request-response operations alongside its existing Redis subscriber.

- **Redis pub/sub** for chat message flow: `chat:messages` (API → AI) and `chat:responses` (AI → API). The AI service passively listens and decides when to respond.
- **HTTP** for commands: agent creation, agent management, and any future operations where the caller needs a direct response.

The guiding rule: if the caller needs a response tied to the request, use HTTP. If it's a broadcast event, use Redis.

## Consequences

- Request-response operations get proper HTTP semantics — status codes, error handling, timeouts — without pub/sub workarounds
- The AI service gains a FastAPI dependency and an exposed port (8001), increasing its surface area slightly
- Two communication channels exist between services, but the rule for choosing between them is straightforward
- Future agent lifecycle operations (spawn, status, stop) map naturally to REST endpoints
- The chat message flow remains unchanged — Redis pub/sub continues to handle the event-driven pattern it was designed for
