"""Terminal session management — PTY lifecycle, I/O relay via Redis."""

import asyncio
import base64
import fcntl
import json
import logging
import os
import pty
import signal
import struct
import termios
import uuid

import redis.asyncio as aioredis

logger = logging.getLogger(__name__)

# Session registry: session_id → {pid, master_fd, reader_task, cwd}
_terminal_sessions: dict[str, dict] = {}


def _ensure_claude_onboarding_complete() -> None:
    """Set hasCompletedOnboarding and theme in ~/.claude.json so Claude Code
    skips the first-run onboarding flow (theme picker → auth screen).
    The subscription credentials in ~/.claude/.credentials.json handle auth."""
    config_path = os.path.expanduser("~/.claude.json")
    config: dict = {}
    try:
        with open(config_path) as f:
            config = json.loads(f.read())
    except (FileNotFoundError, json.JSONDecodeError):
        pass

    changed = False
    if not config.get("hasCompletedOnboarding"):
        config["hasCompletedOnboarding"] = True
        changed = True
    if not config.get("theme"):
        config["theme"] = "dark"
        changed = True

    if changed:
        with open(config_path, "w") as f:
            f.write(json.dumps(config, indent=2))
        logger.info("Set Claude Code onboarding flags in %s", config_path)


async def create_terminal_session(
    cwd: str,
    redis_client: aioredis.Redis,
) -> str:
    """Spawn a PTY running bash with Claude Code auto-launched."""
    session_id = str(uuid.uuid4())

    # Strip ANTHROPIC_API_KEY — CLI uses its own subscription auth (ADR-0011)
    cli_env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
    cli_env["TERM"] = "xterm-256color"
    cli_env["PLAYWRIGHT_MCP_SANDBOX"] = "false"

    # Ensure Claude Code skips onboarding (theme picker + auth screen)
    _ensure_claude_onboarding_complete()

    # Create PTY pair
    master_fd, slave_fd = pty.openpty()

    # Set initial terminal size (80x24 default)
    _set_winsize(master_fd, 24, 80)

    pid = os.fork()
    if pid == 0:
        # Child process
        os.close(master_fd)
        os.setsid()

        # Set slave as controlling terminal
        fcntl.ioctl(slave_fd, termios.TIOCSCTTY, 0)

        # Redirect stdio to slave
        os.dup2(slave_fd, 0)
        os.dup2(slave_fd, 1)
        os.dup2(slave_fd, 2)
        if slave_fd > 2:
            os.close(slave_fd)

        os.chdir(cwd)
        os.execvpe("/bin/bash", ["/bin/bash", "--login"], cli_env)
        # execvpe never returns

    # Parent process
    os.close(slave_fd)

    # Start reader task
    reader_task = asyncio.create_task(
        _read_pty_output(session_id, master_fd, redis_client),
        name=f"terminal-reader-{session_id[:8]}",
    )

    _terminal_sessions[session_id] = {
        "pid": pid,
        "master_fd": master_fd,
        "reader_task": reader_task,
        "cwd": cwd,
    }

    # Auto-launch Claude Code
    os.write(master_fd, b"claude\n")

    logger.info("Terminal session %s created (pid=%d, cwd=%s)", session_id[:8], pid, cwd)
    return session_id


async def _read_pty_output(
    session_id: str,
    master_fd: int,
    redis_client: aioredis.Redis,
) -> None:
    """Read PTY output in a thread and publish to Redis."""
    loop = asyncio.get_event_loop()
    channel = f"terminal:output:{session_id}"

    try:
        while True:
            try:
                data = await loop.run_in_executor(None, os.read, master_fd, 4096)
            except OSError:
                break
            if not data:
                break

            encoded = base64.b64encode(data).decode("ascii")
            await redis_client.publish(
                channel,
                json.dumps({"type": "output", "data": encoded}),
            )
    except asyncio.CancelledError:
        pass
    except Exception:
        logger.exception("Terminal reader error for session %s", session_id[:8])
    finally:
        # Notify that session has closed
        try:
            await redis_client.publish(
                channel,
                json.dumps({"type": "closed"}),
            )
        except Exception:
            pass
        logger.info("Terminal reader stopped for session %s", session_id[:8])


def write_terminal_input(session_id: str, data: bytes) -> bool:
    """Write data to the PTY master fd."""
    session = _terminal_sessions.get(session_id)
    if not session:
        return False
    try:
        os.write(session["master_fd"], data)
        return True
    except OSError:
        logger.warning("Failed to write to terminal %s", session_id[:8])
        return False


def resize_terminal(session_id: str, cols: int, rows: int) -> bool:
    """Resize the PTY window."""
    session = _terminal_sessions.get(session_id)
    if not session:
        return False
    try:
        _set_winsize(session["master_fd"], rows, cols)
        # Send SIGWINCH to the child process group
        os.kill(session["pid"], signal.SIGWINCH)
        return True
    except OSError:
        logger.warning("Failed to resize terminal %s", session_id[:8])
        return False


def _set_winsize(fd: int, rows: int, cols: int) -> None:
    """Set the terminal window size on a file descriptor."""
    winsize = struct.pack("HHHH", rows, cols, 0, 0)
    fcntl.ioctl(fd, termios.TIOCSWINSZ, winsize)


async def destroy_terminal_session(session_id: str) -> bool:
    """Tear down a terminal session."""
    session = _terminal_sessions.pop(session_id, None)
    if not session:
        return False

    # Cancel the reader task
    session["reader_task"].cancel()
    try:
        await session["reader_task"]
    except asyncio.CancelledError:
        pass

    # Kill the child process
    pid = session["pid"]
    try:
        os.kill(pid, signal.SIGHUP)
        # Give it a moment to exit gracefully
        await asyncio.sleep(0.5)
        try:
            os.kill(pid, signal.SIGKILL)
        except OSError:
            pass  # Already exited
    except OSError:
        pass  # Already exited

    # Wait for child to avoid zombie
    try:
        os.waitpid(pid, os.WNOHANG)
    except ChildProcessError:
        pass

    # Close the master fd
    try:
        os.close(session["master_fd"])
    except OSError:
        pass

    logger.info("Terminal session %s destroyed", session_id[:8])
    return True


async def shutdown_all_terminal_sessions() -> None:
    """Destroy all active terminal sessions (called during service shutdown)."""
    session_ids = list(_terminal_sessions.keys())
    for sid in session_ids:
        await destroy_terminal_session(sid)
    logger.info("All terminal sessions shut down (%d)", len(session_ids))
