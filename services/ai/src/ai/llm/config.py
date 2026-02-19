"""LLM configuration — model mappings, pricing, and retry settings."""

from typing import Any


# Provider model mappings
# Maps friendly names to (provider, actual_model_name) tuples
PROVIDER_MODELS = {
    "gemini-3-pro": ("google", "gemini-3-pro-preview"),
    "gpt-5.2": ("openai", "gpt-5.2"),
}

# Provider pricing configurations (USD per 1M tokens)
PROVIDER_PRICING = {
    "google": {
        "gemini-3-pro-preview": {
            "input_low": 2.00,    # ≤200k tokens
            "output_low": 12.00,  # ≤200k tokens
            "input_high": 4.00,   # >200k tokens
            "output_high": 18.00, # >200k tokens
            "threshold": 200_000,
        },
    },
    "openai": {
        "gpt-5.2": {
            "input": 1.75,
            "output": 14.00,
        },
    },
}

# Provider requirements — maps providers to required config fields
PROVIDER_REQUIREMENTS = {
    "google": ["gemini_api_key"],
    "openai": ["openai_api_key"],
}

# Default model ID for API calls
GEMINI_MODEL = "gemini-3-pro-preview"

# Retry configuration
MAX_LLM_RETRIES = 3
FAIL_STRUCTURE_RESPONSE_RETRIES = 2


def get_provider_for_model(model: str) -> str:
    """Get the provider name for a given model.

    Args:
        model: Friendly model name or actual model identifier

    Returns:
        Provider name (e.g. "google")

    Raises:
        ValueError: If model is not recognised
    """
    if model in PROVIDER_MODELS:
        return PROVIDER_MODELS[model][0]

    # Fallback to prefix matching
    if model.startswith("gemini"):
        return "google"
    elif model.startswith("claude") or model.startswith("sonnet"):
        return "anthropic"
    elif model.startswith("gpt"):
        return "openai"
    else:
        raise ValueError(f"Unknown model: {model}")


def get_actual_model_name(model: str) -> str:
    """Get the actual API model name for a friendly model name.

    Args:
        model: Friendly model name

    Returns:
        Actual model name for API calls
    """
    if model in PROVIDER_MODELS:
        return PROVIDER_MODELS[model][1]

    # If not in mapping, return as-is (assume it's already an actual name)
    return model


def validate_provider_config(provider: str, settings: Any) -> bool:
    """Validate that required settings exist for a provider.

    Args:
        provider: Provider name
        settings: Settings object with API keys

    Returns:
        True if all required settings are present
    """
    requirements = PROVIDER_REQUIREMENTS.get(provider, [])

    for req in requirements:
        if not getattr(settings, req, None):
            return False

    return True
