import logging

from .llm import LLM

logger = logging.getLogger(__name__)

# Module-level LLM instance (initialised once)
_llm: LLM | None = None


def _get_llm() -> LLM:
    """Lazy-initialise the LLM service."""
    global _llm
    if _llm is None:
        _llm = LLM()
    return _llm


async def run_agent(conversation: list[dict]) -> str:
    """Run Zimomo agent with the full conversation as context.

    Each entry in *conversation* should have 'display_name' and 'content' keys.
    Returns the agent's text response.
    """
    llm = _get_llm()

    # Build transcript for context
    transcript = "\n".join(
        f"{m['display_name']}: {m['content']}" for m in conversation
    )

    system_instruction = (
        "You are Zimomo, an AI team member in a group chat. "
        "Respond naturally and concisely to the latest message "
        "that mentioned you (@zimomo)."
    )

    messages = [{"role": "user", "content": transcript}]

    try:
        result = await llm.a_get_response(
            messages=messages,
            system_instruction=system_instruction,
        )

        # Handle TextResponse or plain string
        if hasattr(result, "output_text"):
            return result.output_text
        return str(result)

    except Exception:
        logger.exception("Agent query failed")
        return "Sorry, I encountered an error processing your request."
