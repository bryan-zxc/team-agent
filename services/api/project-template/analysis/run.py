"""Pipeline runner — executes analysis steps defined in pipeline.yml."""

import json
import subprocess
import sys
from pathlib import Path

import duckdb
import yaml


def get_db_connection() -> duckdb.DuckDBPyConnection:
    """Connect to the project's DuckDB database via the manifest."""
    project_root = Path(__file__).parent.parent
    manifest_path = project_root / ".team-agent" / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    db_path = f"/data/projects/{manifest['project_id']}/databases/data.duckdb"
    return duckdb.connect(db_path)


def run_pipeline(pipeline_path: Path) -> None:
    """Execute each step in the pipeline sequentially."""
    config = yaml.safe_load(pipeline_path.read_text())
    steps = config.get("steps", [])
    base_dir = pipeline_path.parent

    for i, step in enumerate(steps, 1):
        name = step.get("name", f"Step {i}")
        script = step.get("script")
        if not script:
            print(f"[{i}/{len(steps)}] {name} — skipped (no script)")
            continue

        script_path = base_dir / script
        if not script_path.exists():
            print(f"[{i}/{len(steps)}] {name} — ERROR: {script} not found")
            sys.exit(1)

        print(f"[{i}/{len(steps)}] {name} — running {script}")

        if script.endswith(".py"):
            result = subprocess.run(
                [sys.executable, str(script_path)],
                cwd=str(base_dir.parent),
            )
            if result.returncode != 0:
                print(f"  FAILED (exit code {result.returncode})")
                sys.exit(1)

        elif script.endswith(".sql"):
            sql = script_path.read_text()
            try:
                conn = get_db_connection()
                conn.execute(sql)
                conn.close()
            except Exception as e:
                print(f"  FAILED: {e}")
                sys.exit(1)

        else:
            print(f"  Unknown file type: {script}")
            continue

        # Run checks if defined
        for check in step.get("checks", []):
            check_path = base_dir / check
            if check_path.exists():
                print(f"  Check: {check}")
                check_result = subprocess.run(
                    [sys.executable, str(check_path)],
                    cwd=str(base_dir),
                )
                if check_result.returncode != 0:
                    print(f"  Check FAILED: {check}")
                    sys.exit(1)

    print(f"\nPipeline complete — {len(steps)} steps executed.")


if __name__ == "__main__":
    pipeline_file = Path(__file__).parent / "pipeline.yml"
    if not pipeline_file.exists():
        print("No pipeline.yml found. Create one to define your analysis steps.")
        print("\nExample pipeline.yml:")
        print("  steps:")
        print("    - name: Ingest sales data")
        print("      script: l10wrk_sales.py")
        print("    - name: Sales by region")
        print("      script: l20drv_sales_by_region.sql")
        sys.exit(0)

    run_pipeline(pipeline_file)
