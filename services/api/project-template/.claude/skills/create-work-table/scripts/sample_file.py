"""Sample a data file using DuckDB and output column info as JSON.

Reads up to --limit rows from the file, runs DESCRIBE to get inferred types,
and extracts sample values for each column. Supports CSV, Excel, and Parquet.

Usage:
    python .claude/skills/create-work-table/scripts/sample_file.py \
        --file-path data/raw/sales.csv --limit 10000
"""

import argparse
import json
import sys
from pathlib import Path

import duckdb


def detect_read_function(file_path: str) -> str:
    """Return the DuckDB read function for the given file extension."""
    ext = Path(file_path).suffix.lower()
    readers = {
        ".csv": "read_csv_auto",
        ".tsv": "read_csv_auto",
        ".parquet": "read_parquet",
        ".xlsx": "st_read",
        ".xls": "st_read",
    }
    reader = readers.get(ext)
    if not reader:
        print(f"Unsupported file type: {ext}", file=sys.stderr)
        sys.exit(1)
    return reader


def main() -> None:
    parser = argparse.ArgumentParser(description="Sample a data file and output column info.")
    parser.add_argument("--file-path", required=True, help="Path to the source file")
    parser.add_argument("--limit", type=int, default=10000, help="Max rows to sample")
    parser.add_argument("--output-rows", type=int, default=0, help="Include first N rows as arrays in output")
    args = parser.parse_args()

    file_path = args.file_path
    if not Path(file_path).exists():
        print(f"File not found: {file_path}", file=sys.stderr)
        sys.exit(1)

    reader = detect_read_function(file_path)
    conn = duckdb.connect()

    # Load sample into a temp table
    conn.execute(
        f"CREATE TABLE sample AS SELECT * FROM {reader}('{file_path}') LIMIT {args.limit}"
    )

    # Get row count
    row_count = conn.execute("SELECT COUNT(*) FROM sample").fetchone()[0]

    # Get column types via DESCRIBE
    describe = conn.execute("DESCRIBE sample").fetchall()

    # Get sample values (first 5 non-null distinct per column) and null counts
    columns = []
    for col_name, col_type, *_ in describe:
        samples = conn.execute(
            f'SELECT DISTINCT "{col_name}" FROM sample '
            f'WHERE "{col_name}" IS NOT NULL LIMIT 5'
        ).fetchall()
        sample_values = [str(row[0]) for row in samples]

        null_count = conn.execute(
            f'SELECT COUNT(*) FROM sample WHERE "{col_name}" IS NULL'
        ).fetchone()[0]

        columns.append({
            "name": col_name,
            "inferred_type": col_type,
            "sample_values": sample_values,
            "null_count": null_count,
        })

    # Total row count from the full file (not just sampled)
    total_rows = conn.execute(
        f"SELECT COUNT(*) FROM {reader}('{file_path}')"
    ).fetchone()[0]

    result = {
        "file_path": file_path,
        "rows_sampled": row_count,
        "total_rows": total_rows,
        "columns": columns,
    }

    # Optionally include first N rows as arrays of string values
    if args.output_rows > 0:
        col_names = [c["name"] for c in columns]
        quoted = ', '.join(f'"{n}"' for n in col_names)
        rows = conn.execute(
            f"SELECT {quoted} FROM sample LIMIT {args.output_rows}"
        ).fetchall()
        result["sample_rows"] = [[str(v) if v is not None else "" for v in row] for row in rows]

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
