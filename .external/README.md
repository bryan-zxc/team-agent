# External Repositories

This directory contains external repositories cloned for reference. These repositories are **not** committed to version control — only this README is tracked.

## Repositories

| Repo | URL | Purpose |
|---|---|---|
| claude-agent-sdk-python | https://github.com/anthropics/claude-agent-sdk-python | Official Python SDK for building agentic applications with Claude |
| claude-code | https://github.com/anthropics/claude-code | Claude Code CLI source |
| monaco-editor | https://github.com/microsoft/monaco-editor | VS Code's standalone editor component |
| react-arborist | https://github.com/brimdata/react-arborist | Full-featured tree component with drag-and-drop |
| dockview | https://github.com/mathuo/dockview | VS Code-style layout manager — tabbed panels, split views |

## Cloning

```bash
cd .external/
git clone https://github.com/anthropics/claude-agent-sdk-python.git
```

## Guidelines

- Never commit cloned repositories — they're in `.gitignore`
- Don't modify external code — these are for reference only
