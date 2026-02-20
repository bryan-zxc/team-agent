"""Response models for LLM providers."""

from pydantic import BaseModel, Field
from typing import Any


class TextResponse(BaseModel):
    """Standardised response format from LLM providers for text-only responses.

    This model encapsulates the dual nature of LLM responses:
    1. Technical format (native API format for storage and future LLM calls)
    2. Human-readable text (convenient for immediate use and display)
    """

    messages: list[dict[str, Any]]
    output_text: str


class Workload(BaseModel):
    """A task assigned to an agent by Zimomo."""

    owner: str
    title: str
    description: str
    background_context: str
    problem: str | None = None


class AgentResponse(BaseModel):
    """Structured response from Zimomo."""

    response: str
    workloads: list[Workload] | None = None


class AgentProfile(BaseModel):
    """LLM-generated agent profile fields."""

    name: str = Field(
        description="Either use the provided name or create a name from the Pop Mart universe, prioritising The Monsters series."
    )
    pronoun: str = Field(
        description="Agent's pronoun, e.g. she/her, he/him, they/them."
    )
    personality: str = Field(
        description="The personality should dictate style of interaction with humans such as: "
        "quiet and gets things done, verbose and explanatory like a teacher, never sucks up to humans, etc. "
        "Don't bother with personalities that don't affect how they interact with humans."
    )
    specialisation: str = Field(description="Default to 'analysis and reporting'.")
