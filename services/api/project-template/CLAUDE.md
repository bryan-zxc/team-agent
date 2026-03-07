# Project Data

This project has a DuckDB analytical database for storing and querying structured data.

## Accessing the Database

```python
import duckdb, json
from pathlib import Path

manifest = json.loads(Path(".team-agent/manifest.json").read_text())
project_id = manifest["project_id"]
conn = duckdb.connect(f"/data/projects/{project_id}/databases/data.duckdb")
```

## Usage

- Create tables, insert data, and run analytical queries using standard SQL
- Import CSV: `CREATE TABLE t AS SELECT * FROM read_csv_auto('path/to/file.csv')`
- Import Parquet: `CREATE TABLE t AS SELECT * FROM read_parquet('path/to/file.parquet')`
- For complex datasets, load as a pandas DataFrame first, then push into DuckDB:
  ```python
  import pandas as pd
  df = pd.read_excel("data/raw/report.xlsx", sheet_name="Sheet1")
  conn.execute("CREATE TABLE report AS SELECT * FROM df")
  ```
- The database file is outside the git repository — it is not version-controlled
