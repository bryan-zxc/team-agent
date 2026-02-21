# ADR-0005: Structured Message Format

## Context

Chat messages were stored and transmitted as plain text strings. AI mention detection relied on brittle string matching (`@zimomo` substring search) in the AI service listener. This approach breaks when display names contain spaces, overlap with other words, or change. It also provides no machine-readable way to distinguish message content from metadata like mentions. Ticket #22 will introduce tool_use, tool_result, and thinking blocks in AI responses — plain text cannot represent these.

## Alternatives Considered

**Plain text with separate mentions column**: Add a `mentions` column to the messages table alongside the existing text `content`. Simple, but forces two sources of truth for the same message and doesn't support future block types.

**Inline tokens (Slack-style)**: Replace `@zimomo` with `<@UUID>` tokens in the text. Parseable, but mixes display and data concerns — every consumer must parse the same token format, and extending to non-text blocks requires a different mechanism.

**Structured JSON with blocks and mentions**: Store content as `{"blocks": [...], "mentions": [...]}`. Blocks are typed and extensible. Mentions are a flat array of member IDs, separate from the display text.

## Decision

Messages use a structured JSON format stored in `messages.content`:

```json
{
  "blocks": [
    { "type": "text", "value": "@zimomo what is 7 + 13?" }
  ],
  "mentions": ["uuid-of-zimomo"]
}
```

- `blocks` — ordered array of typed content blocks. Currently only `text`; future types include `tool_use`, `tool_result`, `thinking`.
- `mentions` — array of member UUIDs explicitly referenced. The machine-readable trigger for AI routing — no string matching.
- The `@name` in text blocks is for human readability only. The frontend matches `@name` substrings against the members list to populate the mentions array before sending.

## Consequences

- AI mention detection becomes a UUID lookup instead of string matching — no ambiguity, no false positives
- The format is extensible: adding new block types (tool_use, thinking) requires no schema migration, only new rendering logic
- Legacy plain-text messages (pre-migration) are handled by a fallback parser that returns the raw string when JSON parsing fails
- Every consumer of message content must handle JSON parsing, but the `getMessageText` / `_extract_text` helpers centralise this
