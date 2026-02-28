"""CDP Screencast — stream live browser frames to Redis for frontend consumption."""

import asyncio
import json
import logging
import re

import aiohttp
import redis.asyncio as aioredis
import websockets

logger = logging.getLogger(__name__)

# Session registry: workload_id → {"task": asyncio.Task}
_screencast_sessions: dict[str, dict] = {}

# CDP command ID counter (per module, not per session — just needs to be unique)
_next_cdp_id = 1


def _cdp_id() -> int:
    global _next_cdp_id
    _next_cdp_id += 1
    return _next_cdp_id


async def _discover_cdp_port() -> int | None:
    """Find the Chromium --remote-debugging-port from the running process.

    Retries up to 10 times with 1s delay to allow the browser to finish launching.
    """
    for attempt in range(10):
        try:
            proc = await asyncio.create_subprocess_exec(
                "ps", "aux",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
            stdout, _ = await proc.communicate()
            output = stdout.decode("utf-8", errors="replace")

            for line in output.splitlines():
                if "remote-debugging-port" in line:
                    match = re.search(r"--remote-debugging-port=(\d+)", line)
                    if match:
                        port = int(match.group(1))
                        logger.info("Discovered CDP port %d (attempt %d)", port, attempt + 1)
                        return port
        except Exception:
            logger.debug("Port discovery attempt %d failed", attempt + 1, exc_info=True)

        if attempt < 9:
            await asyncio.sleep(1)

    logger.warning("Could not discover CDP port after 10 attempts")
    return None


async def _get_page_ws_url(port: int) -> str | None:
    """Fetch the first page target's webSocketDebuggerUrl from CDP."""
    url = f"http://localhost:{port}/json/list"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                targets = await resp.json()
                for target in targets:
                    if target.get("type") == "page":
                        return target.get("webSocketDebuggerUrl")
    except Exception:
        logger.debug("Failed to fetch page targets from %s", url, exc_info=True)
    return None


async def start_screencast(
    workload_id: str,
    room_id: str,
    redis_client: aioredis.Redis,
) -> None:
    """Connect to CDP, start Page.startScreencast, and stream frames to Redis.

    Publishes a screencast_started notification via workload:status (room-scoped),
    then streams frames to screencast:frames:{workload_id}.
    """
    if workload_id in _screencast_sessions:
        logger.debug("Screencast already active for workload %s", workload_id[:8])
        return

    frames_channel = f"screencast:frames:{workload_id}"
    ws = None

    try:
        # 1. Discover CDP port
        port = await _discover_cdp_port()
        if port is None:
            return

        # 2. Find page target
        page_ws_url = await _get_page_ws_url(port)
        if not page_ws_url:
            logger.warning("No page target found on CDP port %d for workload %s", port, workload_id[:8])
            return

        # 3. Connect to page via CDP WebSocket
        ws = await websockets.connect(page_ws_url, max_size=10 * 1024 * 1024)

        # 4. Start screencast
        await ws.send(json.dumps({
            "id": _cdp_id(),
            "method": "Page.startScreencast",
            "params": {
                "format": "jpeg",
                "quality": 50,
                "maxWidth": 1280,
                "maxHeight": 720,
                "everyNthFrame": 2,
            },
        }))

        logger.info("Screencast started for workload %s on CDP port %d", workload_id[:8], port)

        # 5. Notify frontend via room-scoped event
        await redis_client.publish("workload:status", json.dumps({
            "workload_id": workload_id,
            "room_id": room_id,
            "screencast_started": True,
        }))

        # 6. Frame receive loop
        async for raw_msg in ws:
            try:
                msg = json.loads(raw_msg)
            except (json.JSONDecodeError, TypeError):
                continue

            if msg.get("method") != "Page.screencastFrame":
                continue

            params = msg.get("params", {})
            frame_data = params.get("data")
            session_id = params.get("sessionId")

            if not frame_data or session_id is None:
                continue

            # Publish frame to Redis
            await redis_client.publish(
                frames_channel,
                json.dumps({"type": "frame", "data": frame_data}),
            )

            # Acknowledge frame so CDP sends the next one
            await ws.send(json.dumps({
                "id": _cdp_id(),
                "method": "Page.screencastFrameAck",
                "params": {"sessionId": session_id},
            }))

    except asyncio.CancelledError:
        # Graceful shutdown — send stop command if still connected
        if ws and not ws.closed:
            try:
                await ws.send(json.dumps({
                    "id": _cdp_id(),
                    "method": "Page.stopScreencast",
                }))
            except Exception:
                pass
        raise
    except websockets.exceptions.ConnectionClosed:
        logger.info("CDP connection closed for workload %s (browser shut down)", workload_id[:8])
    except Exception:
        logger.exception("Screencast error for workload %s", workload_id[:8])
    finally:
        # Close WebSocket
        if ws and not ws.closed:
            try:
                await ws.close()
            except Exception:
                pass

        # Publish stopped sentinel
        try:
            await redis_client.publish(
                frames_channel,
                json.dumps({"type": "stopped"}),
            )
        except Exception:
            pass

        _screencast_sessions.pop(workload_id, None)
        logger.info("Screencast stopped for workload %s", workload_id[:8])


async def stop_screencast(workload_id: str) -> None:
    """Cancel an active screencast for the given workload."""
    session = _screencast_sessions.pop(workload_id, None)
    if not session:
        return

    task = session.get("task")
    if task and not task.done():
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    logger.info("Screencast cancelled for workload %s", workload_id[:8])


async def shutdown_all_screencasts() -> None:
    """Cancel all active screencasts (called during service shutdown)."""
    workload_ids = list(_screencast_sessions.keys())
    for wid in workload_ids:
        await stop_screencast(wid)
    logger.info("All screencasts shut down (%d)", len(workload_ids))


def launch_screencast(
    workload_id: str,
    room_id: str,
    redis_client: aioredis.Redis,
) -> None:
    """Launch a screencast as a background task and register it in the session registry."""
    if workload_id in _screencast_sessions:
        return

    task = asyncio.create_task(
        start_screencast(workload_id, room_id, redis_client),
        name=f"screencast-{workload_id[:8]}",
    )
    _screencast_sessions[workload_id] = {"task": task}
