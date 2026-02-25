# ADR-0009: Session cookie authentication

## Context

The app had no authentication. A dropdown of pre-seeded users stored the selected `user_id` in localStorage, and the API accepted any `member_id` on WebSocket connections without validation. For the alpha release, Google OAuth was added, which required a mechanism to persist authenticated sessions across requests.

## Alternatives Considered

**Stateless JWTs** — sign a JWT containing the user ID and expiry, store it in localStorage or a cookie, verify the signature on each request without a database lookup. Pros: no server-side session state, horizontally scalable. Cons: cannot revoke a token before expiry without a blocklist (which reintroduces server-side state), token refresh adds frontend complexity (silent refresh, race conditions), storing in localStorage exposes tokens to XSS.

**HTTP-only session cookies with a sessions table** — generate a random session ID (`secrets.token_urlsafe(48)`), store it in an HTTP-only `SameSite=Lax` cookie, look up the session in PostgreSQL on each request. Pros: instant revocation (delete the row), no token refresh logic on the frontend, immune to XSS (JavaScript cannot read HTTP-only cookies), simpler CORS with `credentials: "include"`. Cons: requires a database lookup per authenticated request, sessions table grows over time.

## Decision

Use HTTP-only session cookies with a PostgreSQL `sessions` table. The session ID is a `token_urlsafe(48)` value (64 characters of URL-safe base64). The cookie is set with `HttpOnly=True`, `SameSite=Lax`, and `Secure` only in production. Sessions expire after 7 days. A `get_current_user` FastAPI dependency reads the cookie, validates the session against the database, and returns the authenticated `User` or raises 401.

This was chosen because:
- The app is a single-deployment monolith — horizontal scaling is not a concern, so server-side sessions add negligible cost
- Instant revocation matters for a collaborative tool where users may need to be logged out
- The frontend is simpler without token refresh logic — every `fetch` call just includes `credentials: "include"`
- HTTP-only cookies eliminate an entire class of XSS token-theft attacks

## Consequences

- Every authenticated request performs a database lookup on the `sessions` table. This is mitigated by indexing on the primary key (the session ID) and the small table size expected for the alpha
- Expired sessions accumulate in the database. A periodic cleanup job or TTL-based deletion will be needed eventually
- The `SameSite=Lax` setting works in dev (localhost:3000 and localhost:8000 are same-site) and in production (Caddy proxies both services under the same domain). If the frontend and API are ever served from different domains, this will need revisiting
- WebSocket authentication reads the session cookie from the handshake request, which works because browsers send cookies on WebSocket upgrade requests to the same origin
