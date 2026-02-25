# Architecture Decision Records

Active design decisions for the team-agent project. Newest first. When a decision is superseded, its entry and file are both deleted — the replacement ADR captures historical context.

| # | Date | Title | Description | Link |
|---|------|-------|-------------|------|
| 0010 | 2026-02-25 | GitHub Actions deployment via Tailscale SSH | GitHub-hosted runners build multi-platform Docker images and deploy to the Mac Mini via ephemeral Tailscale SSH, reusing the existing deploy.sh script | [ADR-0010](0010-github-actions-deployment-via-tailscale-ssh.md) |
| 0009 | 2026-02-25 | Session cookie authentication | HTTP-only session cookies with a PostgreSQL sessions table for instant revocation and XSS-immune auth, chosen over stateless JWTs | [ADR-0009](0009-session-cookie-authentication.md) |
| 0008 | 2026-02-23 | Repo ownership via manifest file | Projects claim git repo ownership through .team-agent/manifest.json with environment-differentiated enforcement and lockdown on mismatch | [ADR-0008](0008-repo-ownership-via-manifest-file.md) |
| 0007 | 2026-02-22 | Tool approval persistence via project settings | Persist tool approvals to .claude/settings.local.json in the cloned project repo, shared between web app and CLI users | [ADR-0007](0007-tool-approval-persistence-via-project-settings.md) |
| 0006 | 2026-02-22 | Workload session lifecycle with worktree auto-merge | SDK Stop hook triggers deterministic merge with conflict resolution; packaged session function detects/creates worktrees independently of conversation context | [ADR-0006](0006-workload-session-lifecycle-with-worktree-auto-merge.md) |
| 0005 | 2026-02-22 | Workbench infrastructure libraries | dockview, react-arborist, and Monaco for VS Code-style workbench instead of extracting from VS Code source or building from scratch | [ADR-0005](0005-workbench-infrastructure-libraries.md) |
| 0004 | 2026-02-21 | Hybrid inter-service communication | Redis pub/sub for asynchronous events, HTTP for synchronous commands between services | [ADR-0004](0004-hybrid-inter-service-communication.md) |
| 0003 | 2026-02-20 | Shared database access between services | Both services connect directly to PostgreSQL as peers with database constraints enforcing integrity | [ADR-0003](0003-shared-database-access-between-services.md) |
| 0002 | 2026-02-19 | Async-first LLM provider abstraction | Native async clients with settings-driven provider routing by model name | [ADR-0002](0002-async-first-llm-provider-abstraction.md) |
| 0001 | 2026-02-19 | Gemini primary with OpenAI fallback on 503 | Google Gemini 3.0 Pro as Zimomo's LLM, OpenAI GPT-5.2 as immediate fallback on 503 errors | [ADR-0001](0001-gemini-primary-openai-fallback.md) |
