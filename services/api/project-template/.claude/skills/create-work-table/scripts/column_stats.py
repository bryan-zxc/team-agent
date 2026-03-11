"""Generate per-column statistics from a DuckDB table.

Each column is classified as categorical, numeric, or date, and receives
stats appropriate to its classification.

Usage:
    python .claude/skills/create-work-table/scripts/column_stats.py \
        --db-path /data/projects/<id>/databases/data.duckdb \
        --table-name l10wrk_customers \
        --column-types '{"customer_id": "categorical", "revenue": "numeric", "order_date": "date"}'
"""

import argparse
import json
import sys

import duckdb


def stats_categorical(conn: duckdb.DuckDBPyConnection, table: str, col: str) -> dict:
    """Distinct count, value distribution, null/empty counts."""
    total = conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
    distinct = conn.execute(
        f'SELECT COUNT(DISTINCT "{col}") FROM "{table}" WHERE "{col}" IS NOT NULL'
    ).fetchone()[0]
    null_count = conn.execute(
        f'SELECT COUNT(*) FROM "{table}" WHERE "{col}" IS NULL'
    ).fetchone()[0]

    result: dict = {
        "classification": "categorical",
        "distinct_count": distinct,
        "null_count": null_count,
    }

    # Check for empty strings (VARCHAR columns)
    col_type = conn.execute(
        f"SELECT typeof(\"{col}\") FROM \"{table}\" WHERE \"{col}\" IS NOT NULL LIMIT 1"
    ).fetchone()
    if col_type and col_type[0] == "VARCHAR":
        empty_count = conn.execute(
            f'SELECT COUNT(*) FROM "{table}" WHERE TRIM("{col}") = \'\''
        ).fetchone()[0]
        if empty_count > 0:
            result["empty_count"] = empty_count

    non_null = total - null_count
    if non_null > 0 and distinct == non_null:
        result["unique"] = True
    elif distinct <= 10:
        # List all values with counts
        rows = conn.execute(
            f'SELECT "{col}", COUNT(*) as cnt FROM "{table}" '
            f'WHERE "{col}" IS NOT NULL GROUP BY "{col}" ORDER BY cnt DESC'
        ).fetchall()
        result["values"] = [{"value": str(r[0]), "count": r[1]} for r in rows]
    else:
        # Top 3 values
        rows = conn.execute(
            f'SELECT "{col}", COUNT(*) as cnt FROM "{table}" '
            f'WHERE "{col}" IS NOT NULL GROUP BY "{col}" ORDER BY cnt DESC LIMIT 3'
        ).fetchall()
        result["top_values"] = [{"value": str(r[0]), "count": r[1]} for r in rows]

    return result


def stats_numeric(conn: duckdb.DuckDBPyConnection, table: str, col: str) -> dict:
    """Min, max, average, null count."""
    row = conn.execute(
        f'SELECT MIN("{col}"), MAX("{col}"), AVG("{col}"), '
        f'COUNT(CASE WHEN "{col}" IS NULL THEN 1 END) '
        f'FROM "{table}"'
    ).fetchone()

    return {
        "classification": "numeric",
        "min": float(row[0]) if row[0] is not None else None,
        "max": float(row[1]) if row[1] is not None else None,
        "avg": round(float(row[2]), 2) if row[2] is not None else None,
        "null_count": row[3],
    }


def stats_date(conn: duckdb.DuckDBPyConnection, table: str, col: str) -> dict:
    """Date range, special dates, null count, time distribution."""
    null_count = conn.execute(
        f'SELECT COUNT(*) FROM "{table}" WHERE "{col}" IS NULL'
    ).fetchone()[0]

    # Count special year dates (1900, 9999)
    special_count = conn.execute(
        f'SELECT COUNT(*) FROM "{table}" WHERE "{col}" IS NOT NULL '
        f'AND (YEAR("{col}") = 1900 OR YEAR("{col}") = 9999)'
    ).fetchone()[0]

    # Min/max excluding special years
    range_row = conn.execute(
        f'SELECT MIN("{col}"), MAX("{col}") FROM "{table}" '
        f'WHERE "{col}" IS NOT NULL '
        f'AND YEAR("{col}") != 1900 AND YEAR("{col}") != 9999'
    ).fetchone()

    result: dict = {
        "classification": "date",
        "null_count": null_count,
        "special_date_count": special_count,
    }

    if range_row[0] is not None:
        min_date = range_row[0]
        max_date = range_row[1]
        result["min"] = str(min_date)
        result["max"] = str(max_date)

        # Calculate range in months to decide granularity
        months_row = conn.execute(
            f"SELECT DATEDIFF('month', DATE '{min_date}', DATE '{max_date}')"
        ).fetchone()
        months_span = months_row[0] if months_row else 0

        if months_span < 15:
            # Count by month
            rows = conn.execute(
                f'SELECT STRFTIME("{col}", \'%Y-%m\') as m, COUNT(*) as cnt '
                f'FROM "{table}" WHERE "{col}" IS NOT NULL '
                f'AND YEAR("{col}") != 1900 AND YEAR("{col}") != 9999 '
                f'GROUP BY m ORDER BY m'
            ).fetchall()
            result["count_by_month"] = [{"month": r[0], "count": r[1]} for r in rows]

            # Find missing months in range
            all_months = {r[0] for r in rows}
            expected = set()
            cur = min_date.replace(day=1)
            end = max_date.replace(day=1)
            while cur <= end:
                expected.add(cur.strftime("%Y-%m"))
                if cur.month == 12:
                    cur = cur.replace(year=cur.year + 1, month=1)
                else:
                    cur = cur.replace(month=cur.month + 1)
            missing = sorted(expected - all_months)
            if missing:
                result["missing_months"] = missing
        else:
            # Count by year
            rows = conn.execute(
                f'SELECT YEAR("{col}") as y, COUNT(*) as cnt '
                f'FROM "{table}" WHERE "{col}" IS NOT NULL '
                f'AND YEAR("{col}") != 1900 AND YEAR("{col}") != 9999 '
                f'GROUP BY y ORDER BY y'
            ).fetchall()
            result["count_by_year"] = [{"year": r[0], "count": r[1]} for r in rows]

            # Find missing years in range
            all_years = {r[0] for r in rows}
            expected_years = set(range(rows[0][0], rows[-1][0] + 1))
            missing_years = sorted(expected_years - all_years)
            if missing_years:
                result["missing_years"] = missing_years

    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate column statistics from a DuckDB table.")
    parser.add_argument("--db-path", required=True, help="Path to the DuckDB database file")
    parser.add_argument("--table-name", required=True, help="Name of the table to profile")
    parser.add_argument("--column-types", required=True, help="JSON mapping column names to classification (categorical/numeric/date)")
    args = parser.parse_args()

    try:
        column_types = json.loads(args.column_types)
    except json.JSONDecodeError as e:
        print(f"Invalid JSON for --column-types: {e}", file=sys.stderr)
        sys.exit(1)

    conn = duckdb.connect(args.db_path, read_only=True)

    # Verify table exists
    tables = [r[0] for r in conn.execute("SHOW TABLES").fetchall()]
    if args.table_name not in tables:
        print(f"Table not found: {args.table_name}", file=sys.stderr)
        sys.exit(1)

    row_count = conn.execute(f'SELECT COUNT(*) FROM "{args.table_name}"').fetchone()[0]

    stats_funcs = {
        "categorical": stats_categorical,
        "numeric": stats_numeric,
        "date": stats_date,
    }

    columns = {}
    for col, classification in column_types.items():
        func = stats_funcs.get(classification)
        if not func:
            print(f"Unknown classification '{classification}' for column '{col}'", file=sys.stderr)
            sys.exit(1)
        columns[col] = func(conn, args.table_name, col)

    result = {
        "table_name": args.table_name,
        "row_count": row_count,
        "columns": columns,
    }

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
