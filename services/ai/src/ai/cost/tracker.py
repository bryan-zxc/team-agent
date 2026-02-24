"""Unified cost tracker — publishes usage data to Redis for API service to persist."""

import json
import logging

import redis.asyncio as aioredis

logger = logging.getLogger(__name__)


class CostTracker:
    """Publishes LLM cost records to Redis for persistence by the API service."""

    def __init__(self, redis_client: aioredis.Redis):
        self._redis = redis_client

    async def track_llm_cost(
        self,
        model: str,
        provider: str,
        input_tokens: int,
        output_tokens: int,
        cost: float,
        request_type: str,
        caller: str,
    ) -> None:
        """Track cost from Google Gemini or OpenAI LLM calls."""
        try:
            await self._redis.publish(
                "cost:usage",
                json.dumps({
                    "model": model,
                    "provider": provider,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "cost": cost,
                    "request_type": request_type,
                    "caller": caller,
                }),
            )
        except Exception:
            logger.exception("Failed to publish LLM cost")

    async def track_sdk_cost(
        self,
        total_cost_usd: float | None,
        model: str,
        usage: dict | None,
        caller: str,
        session_id: str,
        num_turns: int,
        duration_ms: int,
    ) -> None:
        """Track cost from Claude Agent SDK ResultMessage."""
        if total_cost_usd is None:
            return

        input_tokens = None
        output_tokens = None
        if usage:
            input_tokens = usage.get("input_tokens")
            output_tokens = usage.get("output_tokens")

        try:
            await self._redis.publish(
                "cost:usage",
                json.dumps({
                    "model": model,
                    "provider": "claude_sdk",
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "cost": total_cost_usd,
                    "request_type": "agent_query",
                    "caller": caller,
                    "session_id": session_id,
                    "num_turns": num_turns,
                    "duration_ms": duration_ms,
                }),
            )
        except Exception:
            logger.exception("Failed to publish SDK cost")
