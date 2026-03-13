# Project

## Python and Dependencies

This project uses `uv` for Python dependency management.

- **Run scripts:** `uv run python <script>` — never bare `python`
- **Add a package:** `uv add <package>` — never `pip install` or manual edits to `pyproject.toml`
- **Remove a package:** `uv remove <package>`
- **Sync environment:** `uv sync` — installs all dependencies from the lock file

# Data

## File Paths

Source data lives in `data/raw/` which is gitignored — it only exists in the main repo checkout, never in worktrees. **Always use absolute paths** derived from the manifest:

```python
import json
from pathlib import Path

manifest = json.loads(Path(".team-agent/manifest.json").read_text())
project_id = manifest["project_id"]
repo_root = f"/data/projects/{project_id}/repo"
data_dir = f"{repo_root}/data/raw"
db_path = f"/data/projects/{project_id}/databases/data.duckdb"
```
