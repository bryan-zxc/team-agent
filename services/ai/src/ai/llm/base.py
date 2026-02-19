"""Base classes and interfaces for LLM providers."""

import asyncio
import random
import logging
import enum
from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel

from .models import TextResponse

logger = logging.getLogger(__name__)


class ServiceUnavailableError(Exception):
    """Raised when a provider receives a 503/UNAVAILABLE response."""

    pass


class RequestType(enum.Enum):
    """Types of LLM requests for tracking purposes."""

    TEXT = "text"
    STRUCTURED = "structured"


async def delay_exp(x: int) -> None:
    """Async exponential backoff delay.

    Args:
        x: The retry attempt number (0-based)
    """
    delay_secs = 5 * (x + 1)
    randomness_collision_avoidance = random.randint(0, 1000) / 1000.0
    sleep_dur = delay_secs + randomness_collision_avoidance
    logger.warning(f"Retrying in {round(sleep_dur, 2)} seconds...")
    await asyncio.sleep(sleep_dur)


class BaseLLMProvider(ABC):
    """Abstract base class for LLM providers."""

    provider_name: str = ""

    def __init__(self, api_key: str):
        """Initialise the provider with API credentials.

        Args:
            api_key: API key for the provider
        """
        self.api_key = api_key
        self._setup_client()

    @abstractmethod
    def _setup_client(self) -> None:
        """Set up the provider-specific client."""
        pass

    @abstractmethod
    async def text_response(
        self,
        messages: list[dict[str, Any]],
        model: str,
        temperature: float,
        system_instruction: str | None = None,
    ) -> TextResponse | None:
        """Get a simple text response from the model.

        Args:
            messages: Conversation messages
            model: Model to use
            temperature: Temperature for response generation
            system_instruction: Optional system instruction

        Returns:
            TextResponse or None if failed
        """
        pass

    @abstractmethod
    async def structured_response(
        self,
        messages: list[dict[str, Any]],
        model: str,
        temperature: float,
        response_format: type[BaseModel] | str,
        system_instruction: str | None = None,
    ) -> BaseModel | str | None:
        """Get a structured response (Pydantic model or JSON).

        Args:
            messages: Conversation messages
            model: Model to use
            temperature: Temperature for response generation
            response_format: Either a Pydantic model class or "json" for generic JSON
            system_instruction: Optional system instruction

        Returns:
            Structured response or None if failed
        """
        pass

    @abstractmethod
    def track_cost(
        self, model: str, usage_metadata: Any, request_type: RequestType
    ) -> None:
        """Calculate cost and track usage.

        Args:
            model: Model used
            usage_metadata: Provider-specific usage metadata from response
            request_type: Type of request (text, structured)
        """
        pass
