"""LLM service — main interface for AI service LLM calls."""

import logging
from typing import Any

from pydantic import BaseModel

from ..config import settings
from .base import BaseLLMProvider, ServiceUnavailableError, delay_exp
from .config import MAX_LLM_RETRIES, get_provider_for_model
from .google import GoogleProvider
from .models import TextResponse
from .openai import OpenAIProvider

logger = logging.getLogger(__name__)


class LLM:
    """Main LLM service with automatic provider routing.

    Initialises providers from settings and routes requests to the
    correct provider based on the model name. On 503 errors from
    the primary model, immediately falls back to the backup model.
    """

    def __init__(self):
        """Initialise the LLM service from settings."""
        self.model = settings.gemini_model
        self.backup_model = settings.openai_model

        self._providers: dict[str, BaseLLMProvider] = {}

        if settings.gemini_api_key:
            self._providers["google"] = GoogleProvider(
                api_key=settings.gemini_api_key
            )

        if settings.openai_api_key:
            self._providers["openai"] = OpenAIProvider(
                api_key=settings.openai_api_key
            )

    def _get_provider(self, model: str) -> BaseLLMProvider:
        """Get the provider for a given model.

        Args:
            model: Model identifier

        Returns:
            The appropriate provider instance

        Raises:
            ValueError: If no provider is configured for the model
        """
        provider_name = get_provider_for_model(model)
        provider = self._providers.get(provider_name)
        if not provider:
            raise ValueError(
                f"No provider configured for model {model} "
                f"(provider: {provider_name})"
            )
        return provider

    async def a_get_response(
        self,
        messages: list[dict[str, Any]],
        temperature: float = 0,
        response_format: type[BaseModel] | str | None = None,
        system_instruction: str | None = None,
    ) -> TextResponse | BaseModel | str:
        """Async LLM response with retry logic and 503 fallback.

        This is the primary entry point for the AI service.

        On each retry iteration:
        1. Try primary model (Gemini)
        2. On 503 → immediately try backup model (OpenAI), no delay
        3. If backup fails → exponential backoff, then retry from step 1
        4. On non-503 error → exponential backoff, then retry primary

        Returns:
            TextResponse if no response_format specified
            BaseModel or str if response_format specified
            Fallback error string if all retries exhausted
        """
        for retry in range(MAX_LLM_RETRIES):
            try:
                result = await self._call_provider(
                    self.model, messages, temperature,
                    response_format, system_instruction,
                )

                if result is not None and result != "":
                    return result

                logger.warning(
                    f"Attempt {retry + 1}/{MAX_LLM_RETRIES}: "
                    f"Got None or empty content from {self.model}"
                )

            except ServiceUnavailableError:
                # 503 — immediately try backup model, no delay
                backup_provider_name = get_provider_for_model(self.backup_model)
                if self._providers.get(backup_provider_name):
                    logger.warning(
                        f"Primary model unavailable, falling back to "
                        f"backup: {self.backup_model}"
                    )
                    try:
                        result = await self._call_provider(
                            self.backup_model, messages, temperature,
                            response_format, system_instruction,
                        )

                        if result is not None and result != "":
                            return result

                        logger.warning(
                            f"Backup model {self.backup_model} returned "
                            f"None or empty content"
                        )
                    except Exception as backup_err:
                        logger.error(
                            f"Backup model {self.backup_model} also failed: "
                            f"{backup_err}"
                        )
                else:
                    logger.error(
                        "Primary model returned 503 but no backup provider "
                        "configured"
                    )

            except Exception as e:
                logger.error(
                    f"Attempt {retry + 1}/{MAX_LLM_RETRIES} failed "
                    f"with exception: {e}"
                )

            # Exponential backoff before next retry (except on last iteration)
            if retry < MAX_LLM_RETRIES - 1:
                await delay_exp(retry)

        # All retries exhausted
        logger.error(
            f"Failed to get valid response from {self.model} "
            f"after {MAX_LLM_RETRIES} attempts"
        )
        return "Sorry, I encountered an error processing your request."

    async def _call_provider(
        self,
        model: str,
        messages: list[dict[str, Any]],
        temperature: float,
        response_format: type[BaseModel] | str | None,
        system_instruction: str | None,
    ) -> TextResponse | BaseModel | str | None:
        """Route a request to the correct provider based on model."""
        provider = self._get_provider(model)

        if response_format:
            return await provider.structured_response(
                messages=messages,
                model=model,
                temperature=temperature,
                response_format=response_format,
                system_instruction=system_instruction,
            )
        else:
            return await provider.text_response(
                messages=messages,
                model=model,
                temperature=temperature,
                system_instruction=system_instruction,
            )
