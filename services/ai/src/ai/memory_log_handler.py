"""In-memory ring-buffer log handler for diagnostics."""

import logging
from collections import deque
from datetime import datetime, timezone
from typing import Optional


class MemoryLogHandler(logging.Handler):
    """Stores the last N formatted log records in a thread-safe deque."""

    def __init__(self, capacity: int = 1000):
        super().__init__()
        self._buffer: deque[dict] = deque(maxlen=capacity)

    def emit(self, record: logging.LogRecord) -> None:
        self._buffer.append(
            {
                "timestamp": datetime.fromtimestamp(
                    record.created, tz=timezone.utc
                ).isoformat(),
                "level": record.levelname,
                "logger": record.name,
                "message": self.format(record),
            }
        )

    def get_records(
        self,
        *,
        level: Optional[str] = None,
        limit: int = 100,
        since: Optional[datetime] = None,
    ) -> list[dict]:
        """Return filtered records as plain dicts, newest last."""
        since_iso = since.isoformat() if since else None
        results: list[dict] = []
        for rec in self._buffer:
            if level and rec["level"] != level.upper():
                continue
            if since_iso and rec["timestamp"] < since_iso:
                continue
            results.append(rec)
        return results[-limit:]
