import logging

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    TextBlock,
    query,
)

from src.ai.config import settings

logger = logging.getLogger("ai-service")


async def run_agent(conversation: list[dict]) -> str:
    """Run a Claude agent with the full conversation as context.

    Each entry in *conversation* should have 'display_name' and 'content' keys.
    Returns the agent's text response.
    """
    transcript = "\n".join(
        f"{m['display_name']}: {m['content']}" for m in conversation
    )

    prompt = (
        "You are Zimomo, an AI team member in a group chat. "
        "Below is the conversation so far. Respond naturally and concisely "
        "to the latest message that mentioned you (@zimomo).\n\n"
        f"{transcript}"
    )

    options = ClaudeAgentOptions(
        model=settings.model,
        allowed_tools=[],
    )

    parts: list[str] = []
    try:
        async for msg in query(prompt=prompt, options=options):
            if isinstance(msg, AssistantMessage):
                for block in msg.content:
                    if isinstance(block, TextBlock):
                        parts.append(block.text)
    except Exception:
        logger.exception("Agent query failed")
        return "Sorry, I encountered an error processing your request."

    return "".join(parts)
