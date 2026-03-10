# ADR-0011: Subscription-only Claude authentication

## Context

The AI service runs Claude Code both programmatically (via the Agent SDK for workloads) and interactively (via the CLI in browser-based terminal sessions). An `ANTHROPIC_API_KEY` environment variable exists in the container but is intended only as a legacy artefact — it must never be used for authentication.

During implementation of browser-based terminals, the API key was briefly passed through to the PTY environment to shortcut Claude Code CLI authentication. This was incorrect: the API key is pay-per-token billing, whereas the project operates on a Claude Max subscription with flat-rate usage. Using the API key would bypass subscription entitlements and incur unexpected costs.

The original approach copied short-lived OAuth tokens from the macOS keychain into the container's `.credentials.json` file. These tokens expired within hours, and if the host machine refreshed its token first, the container's refresh token was invalidated — requiring daily re-seeding.

## Decision

All Claude Code authentication — Agent SDK, CLI, and any future integration — uses the Max subscription credentials exclusively, via the `CLAUDE_CODE_OAUTH_TOKEN` environment variable.

The token is generated on a machine with a browser using `claude setup-token`, which produces a long-lived OAuth token valid for 1 year. The token is stored in `.env.prod` and `.env.local` (both gitignored) and passed to the AI service container via Docker Compose env_file configuration.

Specific rules:

- **Strip `ANTHROPIC_API_KEY`** from any environment where users have visibility (e.g. terminal PTY sessions)
- **Never pass `ANTHROPIC_API_KEY`** to Claude Code CLI or SDK invocations
- **Set `CLAUDE_CODE_OAUTH_TOKEN`** in `.env.prod` and `.env.local` — this is the sole authentication mechanism
- The Agent SDK authenticates via the same token, not API keys
- The `claude_auth` Docker volume (`/home/agent/.claude`) is retained for Claude Code's working data (projects, cache, session state) but is no longer used for credential storage

## Consequences

- Terminal sessions and workloads share a single authentication mechanism (long-lived OAuth token via environment variable)
- Token is valid for 1 year — no daily re-seeding needed
- After token expiry, regenerate with `claude setup-token` on the host and update both env files
- After a `docker compose down -v`, only GitHub CLI credentials need re-seeding (Claude auth comes from the env var)
- Cost is predictable (flat subscription rate) regardless of usage volume
- First-run onboarding (theme picker) may appear once per fresh `claude_auth` volume until `claude.json` settings are established
