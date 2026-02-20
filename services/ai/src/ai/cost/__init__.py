"""Cost tracking module for the AI service."""

from .models import Base, LLMUsage
from .tracker import CostTracker

__all__ = ["Base", "CostTracker", "LLMUsage"]

_cost_tracker: CostTracker | None = None


def get_cost_tracker() -> CostTracker:
    """Get the singleton CostTracker instance."""
    global _cost_tracker
    if _cost_tracker is None:
        from ..database import async_session

        _cost_tracker = CostTracker(async_session)
    return _cost_tracker
