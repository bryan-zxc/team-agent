"""Unified cost tracker for all LLM providers."""

import logging
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from .models import LLMUsage

logger = logging.getLogger(__name__)


class CostTracker:
    """Tracks LLM costs from Gemini/OpenAI providers and Claude Agent SDK."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self._session_factory = session_factory

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
            async with self._session_factory() as session:
                usage = LLMUsage(
                    model=model,
                    provider=provider,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    cost=cost,
                    request_type=request_type,
                    caller=caller,
                )
                session.add(usage)
                await session.commit()
        except Exception:
            logger.exception("Failed to track LLM cost")

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
            async with self._session_factory() as session:
                record = LLMUsage(
                    model=model,
                    provider="claude_sdk",
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    cost=total_cost_usd,
                    request_type="agent_query",
                    caller=caller,
                    session_id=session_id,
                    num_turns=num_turns,
                    duration_ms=duration_ms,
                )
                session.add(record)
                await session.commit()
        except Exception:
            logger.exception("Failed to track SDK cost")

    async def get_usage_stats(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        caller_filter: str | None = None,
        model_filter: str | None = None,
    ) -> dict:
        """Query aggregated usage statistics."""
        async with self._session_factory() as session:
            query = select(
                LLMUsage.provider,
                LLMUsage.model,
                func.count().label("total_requests"),
                func.sum(LLMUsage.input_tokens).label("total_input_tokens"),
                func.sum(LLMUsage.output_tokens).label("total_output_tokens"),
                func.sum(LLMUsage.cost).label("total_cost"),
            ).group_by(LLMUsage.provider, LLMUsage.model)

            if start_date:
                query = query.where(LLMUsage.created_at >= start_date)
            if end_date:
                query = query.where(LLMUsage.created_at <= end_date)
            if caller_filter:
                query = query.where(LLMUsage.caller == caller_filter)
            if model_filter:
                query = query.where(LLMUsage.model == model_filter)

            result = await session.execute(query)
            rows = result.all()

            return {
                "by_model": [
                    {
                        "provider": row.provider,
                        "model": row.model,
                        "total_requests": row.total_requests,
                        "total_input_tokens": row.total_input_tokens,
                        "total_output_tokens": row.total_output_tokens,
                        "total_cost": row.total_cost,
                    }
                    for row in rows
                ],
                "grand_total_cost": sum(row.total_cost for row in rows),
            }
