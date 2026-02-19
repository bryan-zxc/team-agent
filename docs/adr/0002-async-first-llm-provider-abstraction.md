# ADR-0002: Async-First LLM Provider Abstraction

## Context

A reference LLM abstraction existed in a separate repo with OpenAI, Anthropic, and Google providers using synchronous API clients. The async entry point (`a_get_response`) wrapped the sync calls. Both the Google GenAI SDK and OpenAI SDK provide native async clients (`client.aio` and `AsyncOpenAI` respectively), making the sync-then-wrap approach unnecessary.

## Decision

Build the LLM provider abstraction async from bottom up:

- `BaseLLMProvider` defines `async def text_response()` and `async def structured_response()` as abstract methods
- `GoogleProvider` uses `client.aio.models.generate_content()`
- `OpenAIProvider` uses `AsyncOpenAI` with `await client.responses.create()`
- `LLM` service exposes only `a_get_response()` — no sync `get_response()` wrapper
- `LLM` reads all configuration (API keys, model names) from settings directly — no constructor parameters
- Provider routing is automatic: `LLM` resolves the correct provider from the model name via `get_provider_for_model()`

## Consequences

- The event loop is free during API calls, enabling future concurrent message processing without refactoring
- No sync entry point exists — callers must be in an async context (this is fine since `listener.py` is already async)
- Adding a new provider means subclassing `BaseLLMProvider` with async methods and registering it in `LLM.__init__`
- Provider instances are created once at startup and reused across requests
