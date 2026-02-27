# ADR-0011: Subscription-only Claude authentication

## Context

The AI service runs Claude Code both programmatically (via the Agent SDK for workloads) and interactively (via the CLI in browser-based terminal sessions). An `ANTHROPIC_API_KEY` environment variable exists in the container but is intended only as a legacy artefact — it must never be used for authentication.

During implementation of browser-based terminals, the API key was briefly passed through to the PTY environment to shortcut Claude Code CLI authentication. This was incorrect: the API key is pay-per-token billing, whereas the project operates on a Claude Max subscription with flat-rate usage. Using the API key would bypass subscription entitlements and incur unexpected costs.

## Decision

All Claude Code authentication — Agent SDK, CLI, and any future integration — uses the Max subscription credentials exclusively. These credentials are stored in the `claude_auth` Docker volume mounted at `/home/agent/.claude/.credentials.json` and contain OAuth tokens tied to the subscription account.

Specific rules:

- **Strip `ANTHROPIC_API_KEY`** from any environment where users have visibility (e.g. terminal PTY sessions)
- **Never pass `ANTHROPIC_API_KEY`** to Claude Code CLI or SDK invocations
- **Use `seed-auth` skill** to provision subscription credentials into the `claude_auth` volume after volume resets
- The Agent SDK authenticates via the same subscription credentials, not API keys

## Consequences

- Terminal sessions and workloads share a single authentication mechanism (subscription OAuth tokens)
- After a `docker compose down -v`, credentials must be re-seeded via the `seed-auth` skill before Claude Code can authenticate
- Token refresh is handled by Claude Code itself — no manual rotation needed
- Cost is predictable (flat subscription rate) regardless of usage volume
- First-run onboarding (theme picker) may appear once per fresh `claude_auth` volume until `claude.json` settings are established
