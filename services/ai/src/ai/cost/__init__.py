"""Cost tracking module for the AI service."""

from .tracker import CostTracker, set_cost_context

__all__ = ["CostTracker", "set_cost_context"]

_cost_tracker: CostTracker | None = None


def init_cost_tracker(redis_client) -> None:
    """Initialise the singleton CostTracker with a Redis client."""
    global _cost_tracker
    _cost_tracker = CostTracker(redis_client)


def get_cost_tracker() -> CostTracker:
    """Get the singleton CostTracker instance."""
    if _cost_tracker is None:
        raise RuntimeError(
            "CostTracker not initialised — call init_cost_tracker() first"
        )
    return _cost_tracker
