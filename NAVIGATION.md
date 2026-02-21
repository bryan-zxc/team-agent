# Project Navigation

## Folder Structure

```
team-agent/
├── docker-compose.yml
├── .env.example
├── architecture.md
├── NAVIGATION.md                       ← you are here
│
├── services/
│   ├── frontend/                       # Next.js (React / TypeScript)
│   │   ├── Dockerfile
│   │   ├── frontend-design.md          # UX/navigation design reference
│   │   ├── public/
│   │   └── src/
│   │       ├── app/                    # Next.js app router (pages)
│   │       │   ├── page.tsx            # Landing page (project list + user picker)
│   │       │   └── project/
│   │       │       └── [projectId]/
│   │       │           ├── page.tsx            # Project dashboard (rooms, members)
│   │       │           ├── chat/
│   │       │           │   └── [roomId]/       # Chat page (structured messages)
│   │       │           └── members/
│   │       │               └── [memberId]/     # Member profile page
│   │       ├── components/
│   │       │   ├── chat/               # Chat UI components (message list, input, threads)
│   │       │   ├── agent/              # Agent chat window components
│   │       │   ├── members/            # Member list, profile, add modal
│   │       │   ├── project/            # Project creation modal
│   │       │   └── sidebar/            # Shared sidebar component
│   │       ├── hooks/                  # React hooks (e.g. WebSocket connection)
│   │       ├── lib/                    # Utility functions, API client
│   │       └── types/                  # TypeScript type definitions
│   │
│   ├── api/                            # FastAPI (Python)
│   │   ├── Dockerfile
│   │   ├── src/
│   │   │   └── api/
│   │   │       ├── main.py             # FastAPI app entry point
│   │   │       ├── config.py           # Environment/config loading
│   │   │       ├── routes/             # REST API endpoints (auth, rooms, messages)
│   │   │       ├── websocket/          # WebSocket connection manager and handlers
│   │   │       ├── models/             # Database models (user, room, message, persona)
│   │   │       └── services/           # Business logic (Redis pub/sub, message handling)
│   │   └── tests/
│   │
│   └── ai/                             # AI Service (Python)
│       ├── Dockerfile
│       ├── src/
│       │   └── ai/
│       │       ├── main.py             # Entry point — starts the Listener
│       │       ├── config.py           # Environment/config loading
│       │       ├── listener.py         # Redis subscriber, trigger/filter logic
│       │       ├── runner.py           # Runs Zimomo via Google Gemini LLM
│       │       ├── transcript.py       # Read/save transcripts to PostgreSQL
│       │       ├── llm/               # LLM provider abstraction
│       │       │   ├── base.py        # BaseLLMProvider ABC
│       │       │   ├── config.py      # Model mappings and pricing
│       │       │   ├── google.py      # Google Gemini provider
│       │       │   ├── openai.py     # OpenAI provider (backup for 503s)
│       │       │   ├── models.py      # TextResponse model
│       │       │   └── service.py     # LLM service (primary entry point)
│       │       ├── personas/           # Persona loading and registry
│       │       └── skills/             # Custom agent skills (.md files)
│       └── tests/
│
├── docs/
│   └── adr/                            # Architecture Decision Records
│       └── adr.md                      # Index of all active decisions
│
├── db/
│   ├── seed.py                         # Dev seed script (global users only)
│   └── migrations/                     # Database migrations (shared schema for api + ai)
│
├── scripts/
│   └── setup-external-repos.sh
│
└── external/
    ├── README.md
    └── claude-agent-sdk-python/        # Vendored SDK (gitignored)
```

## Service Boundaries

| Directory | Language | Docker Service | Purpose |
|---|---|---|---|
| `services/frontend/` | TypeScript | `frontend` | Chat UI served to browsers |
| `services/api/` | Python | `api` | REST API + WebSocket server |
| `services/ai/` | Python | `ai-service` | Listener + ephemeral agent runners |
| `db/` | SQL | — | Shared database migrations |

## Key Locations

| Looking for... | Go to |
|---|---|
| Overall architecture and design decisions | `architecture.md` |
| Architecture decision records (ADRs) | `docs/adr/adr.md` |
| REST API endpoints | `services/api/src/api/routes/` |
| WebSocket handling | `services/api/src/api/websocket/` |
| Database schema / models | `services/api/src/api/models/` |
| AI trigger/filter logic | `services/ai/src/ai/listener.py` |
| Agent lifecycle (spawn, run, save) | `services/ai/src/ai/runner.py` |
| Transcript persistence | `services/ai/src/ai/transcript.py` |
| Persona definitions and loading | `services/ai/src/ai/personas/` |
| Agent memory skills | `services/ai/src/ai/skills/` |
| Database migrations | `db/migrations/` |
| Docker orchestration | `docker-compose.yml` |
| Landing page (projects + user picker) | `services/frontend/src/app/page.tsx` |
| Project dashboard | `services/frontend/src/app/project/[projectId]/page.tsx` |
| Chat UI components | `services/frontend/src/components/chat/` |
| Project creation modal | `services/frontend/src/components/project/` |
| Agent chat window UI | `services/frontend/src/components/agent/` |
| Member management UI | `services/frontend/src/components/members/` |
| Shared sidebar component | `services/frontend/src/components/sidebar/` |
| Frontend design guidelines | `.claude/skills/fe-dev/SKILL.md` |
| UX/navigation design | `services/frontend/frontend-design.md` |
