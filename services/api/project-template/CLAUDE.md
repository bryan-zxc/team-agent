# Project Data

## File Paths

Source data lives in `data/raw/` inside the main repository. If the relative path doesn't work, you are in a git worktree — use absolute paths derived from the manifest instead:

```python
import json
from pathlib import Path

manifest = json.loads(Path(".team-agent/manifest.json").read_text())
project_id = manifest["project_id"]
repo_root = f"/data/projects/{project_id}/repo"
data_dir = f"{repo_root}/data/raw"
db_path = f"/data/projects/{project_id}/databases/data.duckdb"
```
