# ADR-0001: Gemini Primary with OpenAI Fallback on 503

## Context

Zimomo (the coordinator agent) originally used the Claude Agent SDK for all LLM responses. We needed to switch to a dedicated LLM provider for Zimomo while keeping Claude Agent SDK available for other agents. During initial testing with Google Gemini 3.0 Pro, the model returned intermittent 503 UNAVAILABLE errors during high-demand periods. The existing retry logic (exponential backoff on the same model) didn't help when the model was capacity-constrained — it just waited and hit the same 503 again.

## Decision

Use Google Gemini 3.0 Pro as the primary model and OpenAI GPT-5.2 as an immediate fallback activated specifically on 503 errors. The retry loop in `a_get_response` handles this per iteration:

1. Try Gemini
2. On 503 → immediately try GPT-5.2 (no delay)
3. If GPT-5.2 also fails → exponential backoff, then retry from step 1
4. On non-503 errors → exponential backoff, then retry Gemini

Providers raise `ServiceUnavailableError` on 503 to distinguish from other failures.

## Consequences

- Zimomo remains responsive during Gemini demand spikes — users see a response from GPT-5.2 instead of a timeout
- Cost tracking must handle two different pricing models (Gemini tiered vs OpenAI flat)
- Two API keys required (`GEMINI_API_KEY`, `OPENAI_API_KEY`) — both must be configured for full resilience
- If both providers are down simultaneously, the fallback error string is returned after all retries
