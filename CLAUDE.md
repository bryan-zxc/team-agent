# Project Instructions

**Every mistake you make must be recorded in this file as a lesson learned. When you discover you did something wrong — wrong assumption, wasted effort, broken change — add it to the Lessons Learned section below so it never happens again.**

Read `NAVIGATION.md` before exploring the codebase. It documents the full folder structure, service boundaries, and key file locations — use it to narrow down scope of search and exploration.

This is a monorepo with three services under `services/`:
- `services/frontend/` — Next.js (TypeScript)
- `services/api/` — FastAPI (Python)
- `services/ai/` — AI Service (Python)

Each service has its own Dockerfile, dependencies, and tests. They communicate via Redis Pub/Sub and share a PostgreSQL database.

## Dependencies
Always use `uv add <package>` to add Python dependencies. Never edit `pyproject.toml` directly — `uv add` resolves the latest version and updates the lock file automatically.

When working on the frontend, the `fe-dev` skill provides the design system, styling rules, and component guidelines.

## Git
Always include `.claude/settings.local.json` when committing — do not exclude it from staged changes.

## Playwright
Never use `--no-sandbox` when running Playwright. Always use the `PLAYWRIGHT_MCP_SANDBOX=false` environment variable instead when sandbox restrictions need to be lifted (e.g. headed mode, file:// URLs).

## Errors
If you discover an error — console errors, hydration warnings, type errors, lint failures, runtime exceptions — fix it immediately regardless of what task you are currently working on. Errors are never acceptable to leave behind. This applies even if the error is unrelated to your current ticket or was pre-existing.

## Tickets
Always use the `github-board` skill (`/github-board`) for any ticket operations — creating, updating, transitioning status, or closing. If a ticket needs to change, edit the description to the correct version — describe clearly what is eventually done, not what changed from before. Never add comments to tickets.

## Lessons Learned
Hard-won lessons from real mistakes. Read these before starting work.

1. **Frontend changes require a Docker rebuild.** The frontend container has no volume mount — source is baked into the image. Editing `services/frontend/src/...` locally does nothing until you run `docker compose build frontend && docker compose up -d frontend`. Three separate frontend fixes (markdown rendering, remark-breaks, tool description display) were all silently ineffective because this step was skipped.

2. **AI agents escape backticks when writing files.** When an AI agent (Claude Code) writes a file containing JavaScript template literals (backticks), it escapes them as `\``, producing invalid JS. Never design templates where the agent substitutes content into JS code. Instead, use a `<script type="application/json">` tag with a single JSON placeholder — the agent only writes JSON (no backticks), and all JS stays static in the template.

3. **WebSocket broadcast must handle stale connections.** A single closed WebSocket in the connection list will crash the entire broadcast with `RuntimeError: Cannot call "send" once a close message has been sent`, preventing all other clients from receiving messages (including tool approval requests). Always wrap `ws.send_json()` in try/except and evict dead connections.

4. **The api container needs git credential configuration too.** The ai-service Dockerfile configured `gh auth git-credential` as the git credential helper, but the api Dockerfile didn't — even though it also runs git operations (seeds, file serving). Both containers need the same git config: `git config --system credential.helper '!/usr/bin/gh auth git-credential'`.

5. **Text blocks use `value` not `content`.** The block format is `{ type: "text", value: "..." }`. The frontend renderer reads `block.value`, and `convert_text_blocks` in `blocks.py` reads `block.get("value", "")`. Using `content` instead of `value` produces empty message bubbles.
