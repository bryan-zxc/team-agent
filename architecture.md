# Team Agent — Architecture

## Vision

A multi-user group chat system where multiple people on different machines converse together, with AI as one (or more) of the members in the group. The AI participates as a genuine team member — not just a tool to be queried, but an active participant in the conversation.

---

## Design Decisions

### Decided

| Decision | Choice |
|---|---|
| Conversation model | Multi-threaded |
| AI personas | Multiple (design TBD) |
| AI participation | @mention + selective always-listening (design TBD) |
| Context management | Custom design (TBD) |
| Transport layer | Custom WebSocket server |
| Frontend | Next.js (React / TypeScript) |
| Backend API + WebSocket | FastAPI (Python) |
| AI service | Separate Python process |
| AI agent framework | Claude Agent SDK (claude-agent-sdk-python) |
| Agent instances | Ephemeral — spawned per task, discarded on completion |
| Agent tools | Always enabled — tool use is core to persona capability |
| Persona memory | Custom skills backed by PostgreSQL |
| Transcript persistence | Saved to PostgreSQL on every message received |
| Database | PostgreSQL |
| Message broker | Redis (Pub/Sub) for events |
| Inter-service commands | HTTP (FastAPI) |
| Containerisation | Docker Compose |
| Network access (dev) | Tailscale |

### To Be Designed

- AI participation logic — when and how each persona decides to respond
- Context window management — how conversation history is compressed/retrieved for AI calls
- AI persona definitions — roles, personalities, system prompts
- Memory skill design — what memory is stored, how it's queried, how it's injected into agent context
- Authentication and user identity
- Room/space organisation

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────┐
│  User's Browser                                      │
│                                                      │
│  Next.js Frontend (React)                            │
│  - Renders the chat UI                               │
│  - Opens WebSocket connection directly to FastAPI     │
│  - Makes HTTP calls to FastAPI for REST operations    │
└──────────┬─────────────────────┬─────────────────────┘
           │ HTTP (REST)          │ WebSocket (real-time)
           ▼                      ▼
┌─────────────────────────────────────────────────────┐
│  FastAPI Server (Python)                             │
│                                                      │
│  REST API:                                           │
│  - Authentication / session management               │
│  - Fetch message history                             │
│  - User and room management                          │
│                                                      │
│  WebSocket Endpoint:                                 │
│  - Manages active connections                        │
│  - Routes messages to rooms/threads                  │
│  - Broadcasts messages to connected clients          │
│  - Publishes all messages to Redis                   │
└──────────┬─────────────────────┬─────────────────────┘
           │                      │
           ▼                      ▼
     ┌───────────┐         ┌─────────────┐
     │ PostgreSQL │         │ Redis       │
     │            │         │ (Pub/Sub)   │
     │ - Users    │         │             │
     │ - Rooms    │         │ - Chat      │
     │ - Threads  │         │   events    │
     │ - Messages │         │             │
     │ - Personas │         └──────┬──────┘
     └───────────┘                │ subscribes
                           ┌──────▼──────┐
                    HTTP    │ AI Service   │
              ◄───────────►│ (Python)     │
              (commands)   │              │
                           │ - Subscribes │
                           │   to messages│
                           │ - Manages    │
                           │   personas   │
                           │ - Decides    │
                           │   when to    │
                           │   respond    │
                           │ - Spawns     │
                           │   ephemeral  │
                           │   Claude     │
                           │   agents     │
                           │ - Publishes  │
                           │   responses  │
                           │   back via   │
                           │   Redis      │
                           │ - HTTP API   │
                           │   for agent  │
                           │   management │
                           └─────────────┘
```

---

## Services (Docker Compose)

| Service | Technology | Port | Purpose |
|---|---|---|---|
| `frontend` | Next.js | 3000 | Serves the chat UI |
| `api` | FastAPI (Python) | 8000 | REST API + WebSocket server |
| `ai-service` | Python | 8001 | AI persona management and response generation |
| `postgres` | PostgreSQL | 5432 | Persistent data storage |
| `redis` | Redis | 6379 | Message broker (Pub/Sub) |

All services run in the same Docker network and communicate by service name.

---

## Network Topology (Development)

Tailscale runs on the **host machine**, not inside Docker. Docker exposes ports to the host, and Tailscale makes the host reachable to all team members via a private IP.

```
Teammate's Browser
       │
       ▼
Tailscale Private Network
       │
       ▼
Host Machine (100.x.x.x)
       │
       ├── port 3000 → Docker: frontend (Next.js)
       └── port 8000 → Docker: api (FastAPI)
```

---

## Data Flow — Sending a Message

1. User types a message in the Next.js frontend
2. Browser sends the message over WebSocket to FastAPI
3. FastAPI persists the message to PostgreSQL and publishes it to Redis
4. FastAPI broadcasts the message to all other connected clients in the room/thread
5. AI Service (subscribed to Redis) receives the message
6. AI Service decides whether to respond (based on @mention or selective listening logic)
7. If responding, AI Service spawns an ephemeral agent and publishes its responses to Redis
8. FastAPI picks up the AI response from Redis, persists it to PostgreSQL, and broadcasts it to all connected clients

---

## AI Service — Internal Structure

The AI Service has two distinct responsibilities:

```
┌──────────────────────────────────────┐
│ AI Service                            │
│                                       │
│  ┌─────────────┐                      │
│  │ Listener     │ ← Redis subscriber  │
│  │ (always on)  │                     │
│  │              │                     │
│  │ Receives     │                     │
│  │ every message│                     │
│  │ Decides:     │                     │
│  │ trigger? Y/N │                     │
│  └──────┬───────┘                     │
│         │ trigger                     │
│         ▼                             │
│  ┌─────────────┐  ┌─────────────┐    │
│  │ Runner #1   │  │ Runner #2   │    │
│  │ (ephemeral) │  │ (ephemeral) │    │
│  └──────┬──────┘  └──────┬──────┘    │
│         │                │            │
│         └──► Redis pub ◄─┘            │
└──────────────────────────────────────┘
```

**Listener** — a long-lived process subscribed to Redis. It receives every chat message but acts on almost none of them. When a trigger condition is met (e.g. @mention), it spawns a Runner.

**Runner** — a short-lived task that:
1. Builds context from the relevant thread/conversation
2. Spawns a `ClaudeSDKClient` (Claude Agent SDK)
3. The agent gets its own chat window, separate from the main conversation
4. Humans can interact with the agent in this window (approve tool use, adjust direction, ask questions)
5. On every message received from the agent, the transcript is saved to PostgreSQL
6. When the agent finishes (`ResultMessage`), the `ClaudeSDKClient` is discarded
7. A `Stop` hook captures the transcript if a human manually kills the agent

Multiple Runners can operate in parallel — each is independent with its own `ClaudeSDKClient` process.

---

## Agent Lifecycle

```
Main Chat                          Agent Chat Window
────────────                       ──────────────────
User: @alex review this PR
        │
        ▼
Listener detects trigger
        │
        ▼
Runner spawns ClaudeSDKClient
with persona context + memory ──────► Agent: "Looking at the PR now..."
                                      Agent: [uses Read tool on files]
                                      Agent: "I'd like to run the tests"
                                      ◄──── Human: "go ahead"
                                      Agent: [uses Bash tool]
                                      Agent: "Found 2 issues..."
                                      Agent: [ResultMessage — done]
        │                                     │
        ▼                                     ▼
Agent posts summary                  Transcript saved to Postgres
to main chat via Redis               Session ID stored against persona
        │
        ▼
ClaudeSDKClient discarded
Runner ends
```

---

## Persona Memory Model

Personas are **not running processes** — they are datasets in PostgreSQL. An ephemeral agent reconstructs "who it is" at launch time by reading its persona data through custom memory skills.

```
Persona "Alex" (stored in PostgreSQL)
├── Identity: system prompt, personality, role definition
├── Long-term memory: past conversations, decisions, learnings
├── Transcripts: full agent session transcripts from previous tasks
└── Action history: what it's done, outcomes, context

        ↓ loaded via memory skills at agent startup

Ephemeral ClaudeSDKClient
├── system_prompt: persona identity
├── Skill: read_memory → query relevant past context from Postgres
├── Skill: write_memory → persist new learnings to Postgres
├── Skill: search_memory → find relevant past interactions
└── Other tools: Read, Write, Bash, etc.

        ↓ agent runs, finishes, is discarded

Persona "Alex" (updated in PostgreSQL)
├── New transcript saved
├── New memories written via skills during execution
└── Ready for next ephemeral instance
```

The persona persists across ephemeral agent instances. The agent is a temporary body the persona inhabits to do a task — same personality, same memories, different instance every time.

---

## Transcript Persistence

The Claude Code CLI stores conversation transcripts on the filesystem inside the container. Since containers are ephemeral, transcripts are saved to PostgreSQL as the primary store:

- **On every message received** from `receive_response()`, the transcript is read from disk and upserted to PostgreSQL
- **On agent stop** (via `Stop` hook), a final transcript save is triggered as a safety net
- Stored transcripts are accessible to future agent instances via memory skills

The session ID from each `ResultMessage` is stored alongside the transcript, enabling the `resume` feature of the Claude Agent SDK if mid-task continuity is needed (e.g. a human pauses and comes back later).

---

## Key Principles

1. **Separation of concerns** — The chat server and AI service are independent processes communicating only through Redis. Either can be restarted without affecting the other.

2. **AI personas are not special** — From the frontend's perspective, an AI persona is just another user who sends messages.

3. **Events through Redis, commands through HTTP** — Asynchronous events (chat messages) flow through Redis pub/sub. Synchronous commands (agent creation, management) use HTTP between services.

4. **Frontend is a thin client** — Next.js serves the UI and manages the WebSocket connection. All business logic lives server-side.

5. **Ephemeral agents, persistent personas** — Agent instances are short-lived and disposable. Persona identity and memory live in PostgreSQL and survive across any number of ephemeral sessions.

6. **Transcript as the source of truth** — Every agent session's transcript is saved to PostgreSQL on each message received, making it available to future agent instances via memory skills.
