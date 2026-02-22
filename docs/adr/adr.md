# Architecture Decision Records

Active design decisions for the team-agent project. Newest first. When a decision is superseded, its entry and file are both deleted — the replacement ADR captures historical context.

| # | Date | Title | Description | Link |
|---|------|-------|-------------|------|
| 0005 | 2026-02-22 | Workbench infrastructure libraries | dockview, react-arborist, and Monaco for VS Code-style workbench instead of extracting from VS Code source or building from scratch | [ADR-0005](0005-workbench-infrastructure-libraries.md) |
| 0004 | 2026-02-21 | Hybrid inter-service communication | Redis pub/sub for asynchronous events, HTTP for synchronous commands between services | [ADR-0004](0004-hybrid-inter-service-communication.md) |
| 0003 | 2026-02-20 | Shared database access between services | Both services connect directly to PostgreSQL as peers with database constraints enforcing integrity | [ADR-0003](0003-shared-database-access-between-services.md) |
| 0002 | 2026-02-19 | Async-first LLM provider abstraction | Native async clients with settings-driven provider routing by model name | [ADR-0002](0002-async-first-llm-provider-abstraction.md) |
| 0001 | 2026-02-19 | Gemini primary with OpenAI fallback on 503 | Google Gemini 3.0 Pro as Zimomo's LLM, OpenAI GPT-5.2 as immediate fallback on 503 errors | [ADR-0001](0001-gemini-primary-openai-fallback.md) |
