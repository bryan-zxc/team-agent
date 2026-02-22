# External Repositories

This directory contains external repositories cloned for reference and development purposes. These repositories are **not** committed to version control.

## Purpose

- Provides easy discovery and reference for Claude Code and other tools
- Keeps external dependencies separate from project code
- Allows for quick exploration and learning from external codebases

## Managed Repositories

The following repositories should be cloned into this directory:

### Claude Agent SDK (Python)
- **URL**: https://github.com/anthropics/claude-agent-sdk-python
- **Purpose**: Official Python SDK for building agentic applications with Claude
- **Directory**: `external/claude-agent-sdk-python/`

### Monaco Editor
- **URL**: https://github.com/microsoft/monaco-editor
- **Purpose**: VS Code's standalone editor component — syntax highlighting, line numbers, editing
- **Directory**: `external/monaco-editor/`

### React Arborist
- **URL**: https://github.com/brimdata/react-arborist
- **Purpose**: Full-featured tree component with drag-and-drop, rename, create/delete
- **Directory**: `external/react-arborist/`

### Dockview
- **URL**: https://github.com/mathuo/dockview
- **Purpose**: VS Code-style layout manager — tabbed panels, split views, drag-and-drop
- **Directory**: `external/dockview/`

## Quick Start

### Automatic Setup (Recommended)
```bash
# Clone all configured repositories
./scripts/setup-external-repos.sh

# Update all repositories
./scripts/setup-external-repos.sh --update
```

### Manual Setup
```bash
cd external/

# Clone Claude Agent SDK (Python)
gh repo clone anthropics/claude-agent-sdk-python

# Or using git directly
git clone https://github.com/anthropics/claude-agent-sdk-python.git

# Add other repositories as needed
```

## Updating Repositories

```bash
cd external/claude-agent-sdk-python
git pull origin main

# Or use the helper script
./scripts/setup-external-repos.sh --update
```

## Guidelines

1. **Never commit cloned repositories** - They're in `.gitignore` for a reason
2. **Document new repositories** - Add them to the "Managed Repositories" section above
3. **Keep repositories updated** - Periodically pull latest changes
4. **Don't modify external code** - These are for reference only; fork if you need to make changes

## Troubleshooting

### Repository already exists
```bash
# Remove and re-clone
rm -rf external/repo-name
cd external && gh repo clone org/repo-name
```

### Disk space issues
```bash
# Use shallow clone (last commit only)
git clone --depth 1 <repository-url>
```

## Notes

- This directory is excluded from version control via `.gitignore`
- Only this README is tracked in git
- Each cloned repository maintains its own git history
