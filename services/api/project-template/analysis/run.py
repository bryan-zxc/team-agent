"""Pipeline runner — executes analysis steps defined in pipeline.yml."""

import subprocess
import sys
from pathlib import Path

import yaml


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
                cwd=str(base_dir),
            )
        elif script.endswith(".sql"):
            print(f"  SQL file: {script} (execute manually or via database connector)")
            continue
        else:
            print(f"  Unknown file type: {script}")
            continue

        if result.returncode != 0:
            print(f"  FAILED (exit code {result.returncode})")
            sys.exit(1)

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
        print("    - name: Clean raw data")
        print("      script: clean_data.py")
        print("      inputs: [../data/raw/transactions.csv]")
        print("      outputs: [../data/processed/transactions_clean.csv]")
        print("      checks: [check_clean.py]")
        sys.exit(0)

    run_pipeline(pipeline_file)
