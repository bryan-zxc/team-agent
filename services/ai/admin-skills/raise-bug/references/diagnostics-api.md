# Diagnostics API Reference

All endpoints are unauthenticated and internal to the Docker network.

| Service | Base URL |
|---|---|
| API service | `http://api:8000` |
| AI service | `http://ai-service:8001` |

---

## GET /diagnostics/logs

Available on **both** services. Returns recent application logs from an in-memory ring buffer (last 1000 entries).

### Parameters

| Param | Type | Default | Description |
|---|---|---|---|
| `level` | string | all | Filter by log level: `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `limit` | int | 100 | Max entries to return (1–1000) |
| `since` | ISO 8601 | none | Only return entries after this timestamp |

### Examples

```bash
# Recent errors from both services
curl -s 'http://api:8000/diagnostics/logs?level=ERROR&limit=200' | python3 -m json.tool
curl -s 'http://ai-service:8001/diagnostics/logs?level=ERROR&limit=200' | python3 -m json.tool

# Warnings from the AI service
curl -s 'http://ai-service:8001/diagnostics/logs?level=WARNING&limit=100' | python3 -m json.tool

# Everything since a specific time
curl -s 'http://api:8000/diagnostics/logs?since=2026-03-02T10:00:00Z&limit=200' | python3 -m json.tool
```

### Response

```json
[
  {
    "timestamp": "2026-03-02T10:15:32.123456",
    "level": "ERROR",
    "logger": "ai.workload",
    "message": "Workload abc123: push failed, escalating: remote rejected"
  }
]
```

---

## GET /diagnostics/rooms

Available on the **API service** only. Lists all rooms across projects.

### Parameters

| Param | Type | Default | Description |
|---|---|---|---|
| `project_id` | UUID | none | Filter to a specific project |

### Examples

```bash
# All rooms
curl -s 'http://api:8000/diagnostics/rooms' | python3 -m json.tool

# Rooms for a specific project
curl -s 'http://api:8000/diagnostics/rooms?project_id=32e22d76-...' | python3 -m json.tool
```

### Response

```json
[
  {
    "id": "a1b2c3d4-...",
    "name": "General",
    "type": "standard",
    "project_id": "32e22d76-...",
    "project_name": "popmart",
    "created_at": "2026-03-02T09:00:00"
  },
  {
    "id": "e5f6g7h8-...",
    "name": "Admin",
    "type": "admin",
    "project_id": "32e22d76-...",
    "project_name": "popmart",
    "created_at": "2026-03-02T09:00:00"
  }
]
```

---

## GET /diagnostics/chats

Available on the **API service** only. Lists chats with filtering. Returns chat records enriched with room name, owner name, and workload title.

### Parameters

| Param | Type | Default | Description |
|---|---|---|---|
| `status` | string | none | Filter by status: `running`, `investigating`, `completed`, `cancelled`, `needs_attention` |
| `room_id` | UUID | none | Filter to a specific room |
| `project_id` | UUID | none | Filter to a specific project |
| `type` | string | none | Filter by chat type: `primary`, `workload`, `admin` |
| `limit` | int (1–200) | 50 | Max entries to return |

### Examples

```bash
# All recent chats
curl -s 'http://api:8000/diagnostics/chats?limit=20' | python3 -m json.tool

# Only workload chats
curl -s 'http://api:8000/diagnostics/chats?type=workload' | python3 -m json.tool

# Chats stuck in a bad state
curl -s 'http://api:8000/diagnostics/chats?status=running' | python3 -m json.tool
curl -s 'http://api:8000/diagnostics/chats?status=investigating' | python3 -m json.tool

# All chats in a specific room
curl -s 'http://api:8000/diagnostics/chats?room_id=a1b2c3d4-...' | python3 -m json.tool
```

### Response

```json
[
  {
    "id": "8e07e12e-...",
    "room_id": "a1b2c3d4-...",
    "room_name": "General",
    "room_type": "standard",
    "type": "workload",
    "title": "Add dark mode support",
    "status": "completed",
    "owner_name": "Zimomo",
    "workload_title": "Add dark mode support",
    "permission_mode": "acceptEdits",
    "created_at": "2026-03-02T10:30:00",
    "updated_at": "2026-03-02T10:45:00"
  }
]
```

### Common investigation patterns

**Find chats related to a bug report:** Start broad, then narrow down.
```bash
# 1. What rooms exist?
curl -s 'http://api:8000/diagnostics/rooms' | python3 -m json.tool

# 2. What chats are in the room the user mentioned?
curl -s 'http://api:8000/diagnostics/chats?room_id=<id>&limit=10' | python3 -m json.tool

# 3. Get full details for the relevant chat
curl -s 'http://api:8000/diagnostics/chats/<chat_id>' | python3 -m json.tool
```

**Find stuck or broken chats:**
```bash
# Chats that should have completed but didn't
curl -s 'http://api:8000/diagnostics/chats?status=running' | python3 -m json.tool
curl -s 'http://api:8000/diagnostics/chats?status=investigating' | python3 -m json.tool
```

---

## GET /diagnostics/chats/{chat_id}

Available on the **API service** only. Returns a rich debugging view of a single chat with all related entities.

### Parameters

| Param | Type | Default | Description |
|---|---|---|---|
| `message_limit` | int (1–200) | 20 | Number of recent messages to include |

### Example

```bash
curl -s 'http://api:8000/diagnostics/chats/8e07e12e-e641-4b97-a1fc-179383fe4151' | python3 -m json.tool
```

### Response structure

```json
{
  "chat": {
    "id": "8e07e12e-...",
    "room_id": "a1b2c3d4-...",
    "type": "workload",
    "title": "Add dark mode support",
    "owner_id": "member-uuid",
    "workload_id": "workload-uuid",
    "session_id": "session-abc",
    "status": "completed",
    "permission_mode": "acceptEdits",
    "created_at": "2026-03-02T10:30:00",
    "updated_at": "2026-03-02T10:45:00"
  },
  "room": {
    "id": "a1b2c3d4-...",
    "name": "General",
    "type": "standard",
    "created_at": "2026-03-02T09:00:00"
  },
  "project": {
    "id": "32e22d76-...",
    "name": "popmart",
    "git_repo_url": "https://github.com/bryan-zxc/popmart.git",
    "clone_path": "/data/projects/32e22d76-.../repo",
    "default_branch": "main",
    "is_locked": false
  },
  "owner": {
    "id": "member-uuid",
    "display_name": "Zimomo",
    "type": "coordinator"
  },
  "workload": {
    "id": "workload-uuid",
    "main_chat_id": "main-chat-uuid",
    "member_id": "member-uuid",
    "title": "Add dark mode support",
    "description": "...",
    "worktree_branch": "ta/add-dark-mode",
    "dispatch_id": "dispatch-uuid",
    "permission_mode": "acceptEdits",
    "created_at": "2026-03-02T10:30:00"
  },
  "messages": [
    {
      "id": "msg-uuid",
      "member_id": "member-uuid",
      "display_name": "Alice",
      "member_type": "human",
      "content": "{\"blocks\": [...]}",
      "created_at": "2026-03-02T10:31:00"
    }
  ],
  "message_count": 15
}
```

The `project.clone_path` field tells you where to look on disk for git state.
