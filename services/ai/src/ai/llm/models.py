"""Response models for LLM providers."""

from pydantic import BaseModel
from typing import Any


class TextResponse(BaseModel):
    """Standardised response format from LLM providers for text-only responses.

    This model encapsulates the dual nature of LLM responses:
    1. Technical format (native API format for storage and future LLM calls)
    2. Human-readable text (convenient for immediate use and display)
    """

    messages: list[dict[str, Any]]
    output_text: str
