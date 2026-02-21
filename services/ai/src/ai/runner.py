import logging
from pathlib import Path

from .config import settings
from .llm import llm, AgentResponse

logger = logging.getLogger(__name__)


def _load_all_agent_profiles(project_name: str) -> str:
    """Load all agent markdown files and concatenate them."""
    agents_dir = Path(settings.agents_dir) / project_name
    if not agents_dir.exists():
        return ""

    profiles = []
    for md_file in sorted(agents_dir.glob("*.md")):
        profiles.append(md_file.read_text())

    return "\n---\n".join(profiles)


async def run_agent(conversation: list[dict], project_name: str) -> AgentResponse:
    """Run Zimomo agent with the full conversation as context.

    Each entry in *conversation* should have 'display_name' and 'content' keys.
    Returns an AgentResponse with .response and optional .workloads.
    """
    # Build transcript for context
    transcript = "\n".join(
        f"{m['display_name']}: {m['content']}" for m in conversation
    )

    # Load all agent profiles for context
    all_profiles = _load_all_agent_profiles(project_name)

    system_instruction = (
        "You are responding to the latest message that mentioned you (@zimomo) "
        "in a group chat.\n\n"
        "Response rules:\n"
        "- For simple questions you can answer directly (e.g. maths, factual questions, "
        "summarising what someone said), respond with just the 'response' field and "
        "no workloads.\n"
        "- For complex tasks that would benefit from delegation, include workloads "
        "assigning work to available agents. Each workload needs an owner (agent name), "
        "a short title, a description, background context, and optionally a problem/challenge.\n"
        "- If a specific agent is @mentioned in the message, assign workloads to that agent.\n"
        "- If only @zimomo is mentioned, decide which agent(s) are best suited based on "
        "their specialisations.\n"
        "- Keep your response concise and natural.\n\n"
        f"Agents you can pick from:\n\n{all_profiles}"
    )

    messages = [{"role": "user", "content": transcript}]

    try:
        result = await llm.a_get_response(
            messages=messages,
            response_format=AgentResponse,
            system_instruction=system_instruction,
        )

        if isinstance(result, AgentResponse):
            return result

        # Fallback — if we got a string back, wrap it
        return AgentResponse(response=str(result))

    except Exception:
        logger.exception("Agent query failed")
        return AgentResponse(response="Sorry, I encountered an error processing your request.")
