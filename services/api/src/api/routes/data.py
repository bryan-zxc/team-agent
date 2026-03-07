import logging
import uuid
from pathlib import Path
from typing import Literal

import duckdb
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..guards import require_project_member

logger = logging.getLogger(__name__)

CLONE_BASE = Path("/data/projects")
DEFAULT_LIMIT = 100
MAX_LIMIT = 1000

router = APIRouter(dependencies=[Depends(require_project_member)])


def _get_db_path(project_id: uuid.UUID, database: str) -> Path:
    """Resolve database name to file path, preventing traversal."""
    if ".." in database or "/" in database or "\\" in database:
        raise HTTPException(status_code=400, detail="Invalid database name")
    db_path = CLONE_BASE / str(project_id) / "databases" / f"{database}.duckdb"
    if not db_path.exists():
        raise HTTPException(status_code=404, detail=f"Database '{database}' not found")
    return db_path


# --- Request / Response schemas ---


class QueryRequest(BaseModel):
    database: str = "data"
    sql: str
    offset: int = Field(default=0, ge=0)
    limit: int = Field(default=DEFAULT_LIMIT, ge=1, le=MAX_LIMIT)
    sort_column: str | None = None
    sort_direction: Literal["asc", "desc"] = "asc"


class ResultSet(BaseModel):
    columns: list[str]
    rows: list[list]
    total_rows: int
    offset: int
    limit: int
    statement_index: int


class QueryResponse(BaseModel):
    results: list[ResultSet]
    error: str | None = None


class TableInfo(BaseModel):
    name: str
    column_count: int


class DatabaseInfo(BaseModel):
    name: str
    tables: list[TableInfo]


# --- Endpoints ---


@router.post("/projects/{project_id}/data/query")
async def execute_query(
    project_id: uuid.UUID,
    body: QueryRequest,
) -> QueryResponse:
    """Execute one or more SQL statements and return paginated results."""
    db_path = _get_db_path(project_id, body.database)

    statements = [s.strip() for s in body.sql.split(";") if s.strip()]
    if not statements:
        raise HTTPException(status_code=400, detail="No SQL statements provided")

    results: list[ResultSet] = []
    conn = duckdb.connect(db_path)
    try:
        for idx, stmt in enumerate(statements):
            try:
                rel = conn.execute(stmt)

                # DML (INSERT/UPDATE/DELETE/CREATE) won't have columns
                if not rel.description:
                    results.append(
                        ResultSet(
                            columns=[],
                            rows=[],
                            total_rows=0,
                            offset=0,
                            limit=body.limit,
                            statement_index=idx,
                        )
                    )
                    continue

                columns = [desc[0] for desc in rel.description]

                # Only the last statement gets pagination and sorting
                if idx == len(statements) - 1:
                    conn.execute("CREATE OR REPLACE TEMP VIEW __last_result AS " + stmt)

                    count_result = conn.execute(
                        "SELECT COUNT(*) FROM __last_result"
                    ).fetchone()
                    total = count_result[0] if count_result else 0

                    if body.sort_column and body.sort_column in columns:
                        direction = body.sort_direction.upper()
                        paginated = conn.execute(
                            f"SELECT * FROM __last_result "
                            f'ORDER BY "{body.sort_column}" {direction} '
                            f"LIMIT {body.limit} OFFSET {body.offset}"
                        )
                    else:
                        paginated = conn.execute(
                            f"SELECT * FROM __last_result "
                            f"LIMIT {body.limit} OFFSET {body.offset}"
                        )

                    raw_rows = paginated.fetchall()
                    rows = [list(row) for row in raw_rows]
                    results.append(
                        ResultSet(
                            columns=columns,
                            rows=rows,
                            total_rows=total,
                            offset=body.offset,
                            limit=body.limit,
                            statement_index=idx,
                        )
                    )
                else:
                    # Non-final SELECT: execute but don't paginate
                    results.append(
                        ResultSet(
                            columns=columns,
                            rows=[],
                            total_rows=0,
                            offset=0,
                            limit=body.limit,
                            statement_index=idx,
                        )
                    )

            except duckdb.Error as e:
                return QueryResponse(
                    results=results,
                    error=f"Statement {idx + 1}: {e!s}",
                )
    finally:
        conn.close()

    return QueryResponse(results=results)


@router.get("/projects/{project_id}/data/tables")
async def list_tables(project_id: uuid.UUID) -> list[DatabaseInfo]:
    """List all databases and their tables for the data side panel."""
    db_dir = CLONE_BASE / str(project_id) / "databases"
    if not db_dir.exists():
        return []

    databases: list[DatabaseInfo] = []
    for db_file in sorted(db_dir.glob("*.duckdb")):
        db_name = db_file.stem
        conn = duckdb.connect(db_file, read_only=True)
        try:
            tables_result = conn.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'main' ORDER BY table_name"
            ).fetchall()

            tables: list[TableInfo] = []
            for (table_name,) in tables_result:
                col_count = conn.execute(
                    "SELECT COUNT(*) FROM information_schema.columns "
                    "WHERE table_name = ? AND table_schema = 'main'",
                    [table_name],
                ).fetchone()
                tables.append(
                    TableInfo(
                        name=table_name,
                        column_count=col_count[0] if col_count else 0,
                    )
                )
            databases.append(DatabaseInfo(name=db_name, tables=tables))
        finally:
            conn.close()

    return databases
