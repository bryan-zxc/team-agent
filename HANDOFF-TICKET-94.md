# Handoff: Ticket #94 — Playwright Live View in the Workbench

## Ticket

GitHub issue: `gh issue view 94 --repo bryan-zxc/team-agent`

**Parent epic:** #57 (Rich File Previews)

**Goal:** Stream live CDP Screencast frames from the headless Chromium inside Docker to a new dockview panel in the frontend, so users can watch AI agents interact with web pages in real time.

## Branch

All work is on `develop`. No feature branch.

## Status: Debugging — screencast module not connecting to CDP

The full pipeline is built end-to-end (13 files changed). The detection of `playwright-cli open` in the relay loop is now **working** — confirmed in logs. But the screencast module's `start_screencast()` function runs as a background asyncio task and produces **no log output** after being launched. The task appears to be either failing silently or getting stuck.

## Architecture

```
Agent (Claude Code CLI in Docker)
  → runs `playwright-cli open https://...` as Bash tool
  → playwright-cli MCP server launches Chromium with --remote-debugging-port=XXXXX

Relay loop in workload.py
  → detects ToolUseBlock(name="Bash") with "playwright-cli open" in command
  → when matching ToolResultBlock comes back (not error), calls screencast.launch_screencast()

screencast.py (background asyncio task)
  → discovers CDP port via `ps aux | grep --remote-debugging-port`
  → HTTP GET http://localhost:{port}/json/list → finds page target webSocketDebuggerUrl
  → connects via websockets to CDP
  → sends Page.startScreencast
  → publishes screencast_started event to workload:status Redis channel (room-scoped)
  → frame receive loop: publish base64 JPEG frames to screencast:frames:{workload_id} Redis channel
  → ack each frame with Page.screencastFrameAck

API service (screencast_handler.py)
  → WebSocket endpoint /ws/screencast/{workload_id}
  → subscribes to screencast:frames:{workload_id} Redis channel
  → relays frames to WebSocket client

Frontend
  → ChatTab listens for workload_status events with screencast_started flag
  → calls onScreencastStarted(workloadId) → Workbench.openLiveView()
  → opens LiveViewTab dockview panel
  → useScreencastWebSocket connects to /ws/screencast/{workloadId}
  → receives frames → updates <img> src with base64 JPEG data URI
```

## Files Changed (13 total)

### New files (5)

| File | Purpose |
|------|---------|
| `services/ai/src/ai/screencast.py` | CDP screencast lifecycle — port discovery, WebSocket to CDP, frame streaming to Redis |
| `services/api/src/api/websocket/screencast_handler.py` | WebSocket relay endpoint `/ws/screencast/{workload_id}` — Redis sub → WebSocket |
| `services/frontend/src/hooks/useScreencastWebSocket.ts` | React hook — connects to screencast WebSocket, routes frame/stopped messages |
| `services/frontend/src/components/workbench/LiveViewTab.tsx` | Dockview panel — status dot, viewport with `<img>`, direct DOM mutation for frames |
| `services/frontend/src/components/workbench/LiveViewTab.module.css` | Styles — dark viewport, status dot with pulse animation, frame with object-fit contain |

### Modified files (8)

| File | Changes |
|------|---------|
| `services/ai/src/ai/workload.py` | Detect `playwright-cli open` in relay loop, trigger/stop screencast. **Contains debug logging that should be cleaned up.** |
| `services/ai/src/ai/main.py` | Import and call `shutdown_all_screencasts()` in lifespan shutdown |
| `services/ai/pyproject.toml` | Added `websockets` and `aiohttp` dependencies (via `uv add`) |
| `services/ai/uv.lock` | Lock file updated for new dependencies |
| `services/api/src/api/main.py` | Register `screencast_ws_router` |
| `services/frontend/src/components/workbench/Workbench.tsx` | Register `liveViewTab` component, add `openLiveView` callback, pass `onScreencastStarted` to ChatTab |
| `services/frontend/src/components/workbench/ChatTab.tsx` | Handle `screencast_started` event in `handleRoomEvent`, call `onScreencastStarted` |
| `.claude/settings.local.json` | Auto-updated |

## Current Bug: screencast.py background task produces no output

### What works

1. **Detection** — The relay loop in `workload.py` correctly detects `playwright-cli open` in AssistantMessage ToolUseBlocks and correlates with ToolResultBlocks in UserMessages.
2. **Launch** — `screencast.launch_screencast()` is called with the correct workload_id and room_id.
3. **Frontend type-check passes** — No TypeScript errors.
4. **All services build and run.**

### What doesn't work

After `launch_screencast()` creates the background asyncio task, `start_screencast()` produces **zero log output**. Not even the "Discovered CDP port" or "Could not discover CDP port after 10 attempts" messages appear. The task seems to either:

1. **Never actually run** — but `asyncio.create_task()` should schedule it, and there are plenty of `await` points in the relay loop.
2. **Fail immediately with an import/setup error** — since it's a fire-and-forget task, unhandled exceptions would only appear if there's a task exception handler, which there isn't.
3. **Get stuck in port discovery** — `ps aux` might behave differently inside Docker.

### Likely root cause theories

**Theory A: Unhandled task exception.** The `asyncio.create_task` creates a fire-and-forget task. If `start_screencast()` raises an exception before any logging, it would be silently swallowed. This is the most likely cause. Add a task exception callback or wrap in try/except at the top level.

**Theory B: `ps aux` doesn't see Chromium.** The Chromium process is launched by the playwright-cli MCP server which runs as a subprocess of the Claude Code CLI. Inside Docker, it should be visible to `ps aux`, but this needs verification. You can test by running `docker compose exec ai-service ps aux | grep remote-debugging` while a workload is using Playwright.

**Theory C: Module import error.** If `websockets` or `aiohttp` failed to install correctly, the import might fail silently when the task starts. But `import` errors would likely appear at service startup, not at task creation time — and we already see the module being called. Less likely.

### Recommended debugging steps

1. **Add a task done callback to catch exceptions:**
   ```python
   def _on_task_done(task: asyncio.Task):
       if task.exception():
           logger.error("Screencast task failed: %s", task.exception(), exc_info=task.exception())

   task = asyncio.create_task(...)
   task.add_done_callback(_on_task_done)
   ```

2. **Add an early log line at the very top of `start_screencast()`** — before any other logic:
   ```python
   logger.info("start_screencast entered for workload %s", workload_id[:8])
   ```

3. **Test `ps aux` inside the container** while Playwright is running:
   ```bash
   docker compose exec ai-service ps aux | grep remote-debugging
   ```

4. **Test CDP port discovery manually** — exec into the container and run the relevant commands while a Playwright workload is active.

5. **Consider that Chromium might use a pipe transport** instead of `--remote-debugging-port`. The playwright-cli daemon has an `injectCdpPort()` function that's supposed to set a random port, but check what actually gets passed. Look at the playwright-cli daemon source:
   ```
   /Users/bryanye/Library/Caches/ms-playwright/daemon/
   ```

## Debug logging to clean up

The unstaged changes in `workload.py` contain verbose INFO-level debug logging. After fixing the screencast bug:

1. Remove all the `logger.info("ToolUseBlock for workload ...")` lines
2. Remove the `logger.info("UserMessage for workload ...")` lines
3. Remove the `logger.info("  UserMessage block type=...")` lines
4. Remove the `logger.info("  ToolResultBlock tool_use_id=...")` lines
5. Keep the `logger.info("Detected playwright-cli open ...")` line (useful for production)
6. Keep the `logger.info("Launching screencast ...")` line (useful for production)
7. The original detection code before debug logging was simpler — check git staged version for the clean form

The staged version of workload.py has the clean detection code. The unstaged version has the debug logging. You can either:
- `git checkout --staged services/ai/src/ai/workload.py` to go back to clean version
- Or keep the debug logging while you fix the screencast bug, then clean up

## Key reference files for patterns

- `services/ai/src/ai/terminal.py` — Session registry, background task, Redis pub/sub pattern (screencast.py follows this)
- `services/frontend/src/hooks/useTerminalWebSocket.ts` — WebSocket hook pattern
- `services/api/src/api/websocket/terminal_handler.py` — WebSocket relay handler pattern
- `services/api/src/api/websocket/manager.py` — `broadcast_room()` for room-scoped events
- `services/api/src/api/websocket/handler.py` — WebSocket room registration via `connect_room()`
- `services/api/src/api/main.py` — `_listen_for_workload_status()` adds `_event: "workload_status"` and broadcasts to room

## Approved plan

The full implementation plan is at: `/Users/bryanye/.claude/plans/encapsulated-riding-wozniak.md`

## Remaining work

1. **Fix the screencast background task** — diagnose why `start_screencast()` produces no output (see debugging steps above)
2. **Verify frames stream** — once CDP connection works, verify frames arrive on Redis and reach the frontend WebSocket
3. **Verify Live View panel opens** — the `screencast_started` event via `workload:status` should trigger the panel
4. **Clean up debug logging** — remove verbose INFO logs from workload.py
5. **End-to-end test** — full flow: send @mention → workload → playwright-cli open → Live View panel opens with live frames → panel shows "Browser session ended" when done
6. **Commit and push** to develop
7. **Update ticket #94 description** to reflect what was delivered
8. **Transition ticket #94 to Done** via `/github-board`
9. **Check if epic #57 is fully complete** — if all sub-issues are Done, transition epic to Done and release

## Test procedure

```bash
# 1. Start services
docker compose up -d

# 2. Seed
docker compose exec api bash -c 'rm -rf /data/projects/*'
docker compose exec api .venv/bin/python db/seeds/with_project.py

# 3. Open app
PLAYWRIGHT_MCP_SANDBOX=false playwright-cli open http://localhost:3000 --headed

# 4. Login as Bob, click popmart project, create a room
# 5. @mention an AI agent (e.g. @Zimomo) asking to open a URL in the browser
# 6. Approve tool approvals as they appear
# 7. When the agent runs `playwright-cli open`, verify:
#    - AI logs show "Launching screencast for workload ..."
#    - AI logs show "Screencast started for workload ..."
#    - A "Live View" panel auto-opens in the workbench
#    - Live frames stream into the panel
# 8. When the workload completes, verify panel shows "Browser session ended"
```

## Log commands for debugging

```bash
# Watch AI service logs in real time
docker compose logs ai-service -f

# Filter for screencast-related
docker compose logs ai-service | grep -i screencast

# Filter for detection
docker compose logs ai-service | grep -E "ToolUseBlock|playwright|screencast|launch"

# Rebuild AI service after changes
docker compose up -d ai-service --build
```
