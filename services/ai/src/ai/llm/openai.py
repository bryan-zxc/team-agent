"""OpenAI LLM provider implementation."""

import json
import re
import logging
from typing import Any

from openai import AsyncOpenAI
from pydantic import BaseModel

from .base import BaseLLMProvider, RequestType
from .config import MAX_LLM_RETRIES, PROVIDER_PRICING
from .models import TextResponse
from ..cost import get_cost_tracker

logger = logging.getLogger(__name__)


class OpenAIProvider(BaseLLMProvider):
    """OpenAI provider implementation for GPT models."""

    provider_name = "openai"

    # Track if we've shown the temperature deprecation warning
    _temperature_warning_shown = False

    def _setup_client(self) -> None:
        """Set up async OpenAI client."""
        self.client = AsyncOpenAI(api_key=self.api_key)

    def _warn_temperature_deprecated(self, temperature: float) -> None:
        """Warn once if temperature is being used with gpt-5 models."""
        if not OpenAIProvider._temperature_warning_shown and temperature != 0:
            logger.warning(
                "Temperature parameter is deprecated for OpenAI gpt-5 models "
                "and will be ignored. The model uses its own internal "
                "temperature settings."
            )
            OpenAIProvider._temperature_warning_shown = True

    def _convert_messages_for_api(
        self, messages: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Convert internal message format to OpenAI API format.

        Transforms content types:
        - "text" -> "input_text"
        - "image_url" -> "input_image"
        """
        converted = []

        for msg in messages:
            converted_msg = {"role": msg["role"]}

            # Handle content that might be a list of content items
            if isinstance(msg.get("content"), list):
                converted_content = []
                for item in msg["content"]:
                    if isinstance(item, dict):
                        if item.get("type") == "text":
                            # Use output_text for assistant, input_text for others
                            text_type = (
                                "output_text"
                                if msg["role"] == "assistant"
                                else "input_text"
                            )
                            converted_content.append(
                                {"type": text_type, "text": item.get("text", "")}
                            )
                        elif item.get("type") == "image_url":
                            # Convert "image_url" to "input_image"
                            image_url = item.get("image_url", {})
                            if isinstance(image_url, dict):
                                url = image_url.get("url", "")
                            else:
                                url = image_url
                            converted_content.append(
                                {"type": "input_image", "image_url": url}
                            )
                        else:
                            # Keep other types as-is
                            converted_content.append(item)
                    else:
                        # Non-dict items, keep as-is
                        converted_content.append(item)
                converted_msg["content"] = converted_content
            else:
                # Simple string content, keep as-is
                converted_msg["content"] = msg.get("content", "")

            converted.append(converted_msg)

        return converted

    async def text_response(
        self,
        messages: list[dict[str, Any]],
        model: str,
        temperature: float,
        system_instruction: str | None = None,
    ) -> TextResponse | None:
        """Get text response using OpenAI Responses API."""
        try:
            # Warn about temperature deprecation
            self._warn_temperature_deprecated(temperature)

            # Temperature is not supported in gpt-5 models, so we don't pass it
            response = await self.client.responses.create(
                model=model,
                instructions=system_instruction,
                input=self._convert_messages_for_api(messages),
            )

            # Track usage
            if hasattr(response, "usage"):
                await self.track_cost(model, response.usage, RequestType.TEXT)

            # Build message list
            message_list = []
            for item in response.output:
                if item.type == "reasoning":
                    message_list.append({
                        "technical_message": item.model_dump(exclude_none=True),
                        "display_message": None,
                        "message_from": "Zimomo",
                    })
                elif item.type == "text":
                    message_list.append({
                        "technical_message": item.model_dump(exclude_none=True),
                        "display_message": response.output_text,
                        "message_from": "Zimomo",
                    })

            # Return TextResponse with native OpenAI output_text field
            return TextResponse(
                messages=message_list,
                output_text=response.output_text,
            )

        except Exception as e:
            logger.error(f"OpenAI text response error: {e}")
            return None

    async def structured_response(
        self,
        messages: list[dict[str, Any]],
        model: str,
        temperature: float,
        response_format: type[BaseModel] | str,
        system_instruction: str | None = None,
    ) -> BaseModel | str | None:
        """Get structured response using OpenAI Responses API."""
        try:
            # Warn about temperature deprecation
            self._warn_temperature_deprecated(temperature)

            # Check if response_format is a Pydantic model or "json" string
            if isinstance(response_format, type) and issubclass(
                response_format, BaseModel
            ):
                # Use parse() for Pydantic models
                response = await self.client.responses.parse(
                    model=model,
                    instructions=system_instruction,
                    input=self._convert_messages_for_api(messages),
                    text_format=response_format,
                )

                # Track usage
                if hasattr(response, "usage"):
                    await self.track_cost(model, response.usage, RequestType.STRUCTURED)

                return response.output_parsed

            elif response_format == "json":
                # Use create() with format for generic JSON
                input_messages = self._convert_messages_for_api(messages.copy())

                for attempt in range(MAX_LLM_RETRIES):
                    response = await self.client.responses.create(
                        model=model,
                        instructions=system_instruction,
                        input=input_messages,
                        text={"format": {"type": "json_object"}},
                    )

                    # Track usage immediately after API call
                    if hasattr(response, "usage"):
                        await self.track_cost(
                            model, response.usage, RequestType.STRUCTURED
                        )

                    json_str = response.output_text

                    # First validation attempt
                    try:
                        json.loads(json_str)
                        return json_str
                    except Exception:
                        # Clean control characters and retry
                        json_str = re.sub(r"[\x00-\x1F]+", "", json_str)

                    try:
                        json.loads(json_str)
                        return json_str
                    except Exception as e:
                        if attempt < MAX_LLM_RETRIES - 1:
                            # Add error feedback for retry
                            input_messages.append({
                                "role": "developer",
                                "content": (
                                    f"The JSON returned is:\n{json_str}\n\n"
                                    f"It cannot be converted by json.loads with "
                                    f"the following error:\n{e}\n\n"
                                    f"Generate a new JSON without the error."
                                ),
                            })
                            logger.warning(
                                f"JSON validation failed, attempt {attempt + 1}: {e}"
                            )
                        else:
                            logger.error(
                                f"Failed to get valid JSON after "
                                f"{MAX_LLM_RETRIES} attempts"
                            )
                            return None
            else:
                logger.error(f"Invalid response_format: {response_format}")
                return None

        except Exception as e:
            logger.error(f"OpenAI structured response error: {e}")
            return None

    async def track_cost(
        self, model: str, usage_metadata: Any, request_type: RequestType
    ) -> None:
        """Calculate cost and log usage for OpenAI."""
        if not usage_metadata:
            return

        # Simple token access for OpenAI
        input_tokens = getattr(usage_metadata, "input_tokens", 0)
        output_tokens = getattr(usage_metadata, "output_tokens", 0)

        # Calculate cost
        cost = 0.0
        pricing = PROVIDER_PRICING.get("openai", {}).get(model, {})

        if pricing:
            input_cost = (input_tokens / 1_000_000) * pricing["input"]
            output_cost = (output_tokens / 1_000_000) * pricing["output"]
            cost = input_cost + output_cost
        else:
            logger.warning(f"No pricing info for model {model}")

        logger.info(
            f"LLM Usage: {model}, Input: {input_tokens}, "
            f"Output: {output_tokens}, Cost: ${cost:.6f}, "
            f"Type: {request_type.value}"
        )

        await get_cost_tracker().track_llm_cost(
            model=model,
            provider=self.provider_name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost=cost,
            request_type=request_type.value,
            caller="zimomo",
        )
