"""Google Gemini LLM provider implementation."""

import json
import re
import base64
import logging
from typing import Any

from google import genai
from google.genai import types
from pydantic import BaseModel, ValidationError

from .base import BaseLLMProvider, RequestType, ServiceUnavailableError
from .config import PROVIDER_PRICING, MAX_LLM_RETRIES
from .models import TextResponse
from ..cost import get_cost_tracker

logger = logging.getLogger(__name__)


class GoogleProvider(BaseLLMProvider):
    """Google provider implementation for Gemini models."""

    provider_name = "google"

    def _setup_client(self) -> None:
        """Set up Google Gemini client."""
        self.client = genai.Client(api_key=self.api_key)

    def _convert_messages(self, messages: list[dict]) -> list:
        """Convert OpenAI format messages to Gemini format."""
        gemini_contents = []

        role_map = {
            "user": "user",
            "assistant": "model",
        }

        for message in messages:
            role = message.get("role")

            if role == "system" or role not in role_map:
                continue

            gemini_role = role_map[role]
            content = message.get("content", "")

            parts = []

            if isinstance(content, list):
                # Handle structured content
                for block in content:
                    block_type = block.get("type")

                    if block_type in ["text", "input_text"]:
                        text = block.get("text", "")
                        if text:
                            parts.append(types.Part.from_text(text=text))

                    elif block_type in ["image", "input_image"]:
                        # Handle base64 images
                        image_url = block.get("image_url", "")
                        if image_url and image_url.startswith("data:"):
                            try:
                                header, base64_data = image_url.split(",", 1)
                                mime_type = header.split(";")[0].split(":")[1]
                                image_bytes = base64.b64decode(base64_data)
                                parts.append(
                                    types.Part.from_bytes(
                                        data=image_bytes, mime_type=mime_type
                                    )
                                )
                            except Exception as e:
                                logger.warning(f"Failed to process image: {e}")
            else:
                # Simple text content
                if content:
                    parts.append(types.Part.from_text(text=str(content)))

            if parts:
                gemini_contents.append(types.Content(role=gemini_role, parts=parts))

        return gemini_contents

    async def text_response(
        self,
        messages: list[dict[str, Any]],
        model: str,
        temperature: float,
        system_instruction: str | None = None,
    ) -> TextResponse | None:
        """Get text response from Gemini.

        Returns TextResponse with messages and output_text.
        Raises ServiceUnavailableError on 503/UNAVAILABLE.
        """
        try:
            gemini_contents = self._convert_messages(messages)

            config = types.GenerateContentConfig(
                temperature=temperature,
                system_instruction=system_instruction if system_instruction else None,
            )

            response = await self.client.aio.models.generate_content(
                model=model,
                contents=gemini_contents,
                config=config,
            )

            # Track usage
            if hasattr(response, "usage_metadata"):
                await self.track_cost(model, response.usage_metadata, RequestType.TEXT)

            # Extract text using native Google format
            text_content = response.text

            # Return TextResponse with native Google extraction
            return TextResponse(
                messages=[{
                    "technical_message": {
                        "role": "assistant",
                        "content": text_content,
                    },
                    "display_message": text_content,
                    "message_from": "Zimomo",
                }],
                output_text=text_content,
            )

        except Exception as e:
            if "503" in str(e) or "UNAVAILABLE" in str(e):
                logger.warning(f"Gemini 503 UNAVAILABLE: {e}")
                raise ServiceUnavailableError(str(e)) from e
            logger.error(f"Gemini text response error: {e}")
            return None

    async def structured_response(
        self,
        messages: list[dict[str, Any]],
        model: str,
        temperature: float,
        response_format: type[BaseModel] | str,
        system_instruction: str | None = None,
    ) -> BaseModel | str | None:
        """Get structured response from Gemini."""
        try:
            gemini_contents = self._convert_messages(messages)

            config = types.GenerateContentConfig(
                temperature=temperature,
                response_mime_type="application/json",
                system_instruction=system_instruction if system_instruction else None,
            )

            # Handle response format
            is_pydantic = isinstance(response_format, type) and issubclass(
                response_format, BaseModel
            )

            if is_pydantic:
                config.response_schema = response_format
            elif response_format != "json":
                logger.warning(
                    f"Unsupported response_format for Gemini: {response_format}"
                )
                return None

            for attempt in range(MAX_LLM_RETRIES):
                response = await self.client.aio.models.generate_content(
                    model=model,
                    contents=gemini_contents,
                    config=config,
                )

                # Track usage immediately after API call (captures all retry attempts)
                if hasattr(response, "usage_metadata"):
                    await self.track_cost(
                        model, response.usage_metadata, RequestType.STRUCTURED
                    )

                json_content = response.text

                # First validation attempt
                try:
                    if is_pydantic:
                        json_data = json.loads(json_content)
                        return response_format.model_validate(json_data)
                    else:
                        json.loads(json_content)
                        return json_content
                except Exception:
                    # Clean control characters and retry
                    json_content = re.sub(r"[\x00-\x1F]+", "", json_content)

                try:
                    if is_pydantic:
                        json_data = json.loads(json_content)
                        return response_format.model_validate(json_data)
                    else:
                        json.loads(json_content)
                        return json_content
                except (json.JSONDecodeError, ValidationError) as e:
                    if attempt < MAX_LLM_RETRIES - 1:
                        logger.warning(f"Attempt {attempt + 1} failed: {e}")
                        # Add error feedback for retry
                        gemini_contents.append(
                            types.Content(
                                role="user",
                                parts=[
                                    types.Part.from_text(
                                        text=f"The JSON returned is:\n{json_content}\n\n"
                                        f"It cannot be converted by json.loads with the "
                                        f"following error:\n{e}\n\n"
                                        f"Generate a new JSON without the error."
                                    )
                                ],
                            )
                        )
                    else:
                        logger.error(f"Failed after {MAX_LLM_RETRIES} attempts: {e}")
                        return None

        except ServiceUnavailableError:
            raise
        except Exception as e:
            if "503" in str(e) or "UNAVAILABLE" in str(e):
                logger.warning(f"Gemini 503 UNAVAILABLE: {e}")
                raise ServiceUnavailableError(str(e)) from e
            logger.error(f"Gemini structured response error: {e}")
            return None

    async def track_cost(
        self, model: str, usage_metadata: Any, request_type: RequestType
    ) -> None:
        """Calculate cost and log usage for Google Gemini."""
        if not usage_metadata:
            return

        # Aggregate Google's multiple input token types (handle None values)
        input_tokens = (
            (usage_metadata.prompt_token_count or 0)
            + (usage_metadata.thoughts_token_count or 0)
            + (getattr(usage_metadata, "tool_use_prompt_token_count", 0) or 0)
        )
        output_tokens = usage_metadata.candidates_token_count or 0

        # Calculate cost with tiered pricing
        cost = 0.0
        pricing = PROVIDER_PRICING.get("google", {}).get(model, {})

        if "threshold" in pricing:
            # Tiered pricing based on input tokens
            if input_tokens <= pricing["threshold"]:
                input_rate = pricing["input_low"]
                output_rate = pricing["output_low"]
            else:
                input_rate = pricing["input_high"]
                output_rate = pricing["output_high"]

            cost = (input_tokens * input_rate + output_tokens * output_rate) / 1_000_000
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
