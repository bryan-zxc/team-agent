# Frontend Design

## Project Space

The top-level view. Shows a panel of all main chats in the project. Each chat has a name (e.g. "Reporting", "Standups", "Sprint Planning"). Every user in the project has access to every chat — there is no per-chat membership.

## Main Chat

A group conversation where all humans and all agents can participate. Opened by clicking a chat from the project space panel.

The main chat window has two areas:
1. **Chat area** — the conversation itself
2. **Workload panel** — a side/bottom panel showing all active and completed agent workloads attached to this chat

## Workload Chats

When an agent task is triggered from a main chat, a new **workload chat** is created. This appears as:
- A new tab alongside the main chat tab
- An entry in the workload panel within the main chat window

Each workload chat:
- Has exactly **one agent** working on a task
- Is visible to **all humans** — any human can click into the tab, watch the agent work, and send messages
- Is **attached to a specific main chat** (the one that triggered it)
- Lives as a tab in the same window as its parent main chat

## Tab Structure

```
┌─────────────────────────────────────────────────────────┐
│ [Main Chat]  [Agent: review PR #42]  [Agent: fix tests] │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Chat messages here                                     │
│                                                         │
│                                          ┌────────────┐ │
│                                          │ Workloads  │ │
│                                          │            │ │
│                                          │ • PR #42   │ │
│                                          │ • fix tests│ │
│                                          └────────────┘ │
│                                                         │
│ [message input]                                         │
└─────────────────────────────────────────────────────────┘
```

## Summary

- **Project space** → panel of all main chats
- **Main chat** → all humans + all agents, has a workload panel
- **Workload chat** → one agent + any humans, attached to a main chat, shown as a tab
