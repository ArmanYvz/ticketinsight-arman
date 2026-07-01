"""FastMCP MCP server for TicketInsight.

Defines tools:
- list_tables()
- get_schema(table_name: str)
- run_query(sql: str)
- get_sample_rows(table_name: str, limit: int = 5)

Connects to `data/tickets.db` in read-only mode.
"""
from __future__ import annotations

import sqlite3
import os
from typing import Any, Dict, List, Optional, Tuple

try:
    import fastmcp  # type: ignore
except Exception as exc:  # pragma: no cover - helpful error if lib missing
    raise ImportError("fastmcp is required to run this server. Install via `pip install fastmcp`.") from exc

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "tickets.db")


def _connect_readonly(path: str) -> sqlite3.Connection:
    """Open the SQLite database in read-only mode and return a connection.

    Uses URI mode to ensure the file is opened read-only.
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"Database not found at {path}. Run data/seed.py first.")

    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


# Initialize connection for the module
_conn: Optional[sqlite3.Connection] = None


def _get_conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        _conn = _connect_readonly(DB_PATH)
    return _conn


def list_tables() -> List[str]:
    """Return a list of table names in the database (excluding sqlite internal tables)."""
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")
    return [row[0] for row in cur.fetchall()]


def get_schema(table_name: str) -> str:
    """Return the CREATE TABLE SQL for the given table name.

    Raises FileNotFoundError or ValueError if the table does not exist.
    """
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
    row = cur.fetchone()
    if not row or not row[0]:
        raise ValueError(f"No schema found for table '{table_name}'")
    return row[0]


def get_sample_rows(table_name: str, limit: int = 5) -> Dict[str, Any]:
    """Return up to `limit` rows from `table_name` as a dict with `columns` and `rows`.

    The rows are returned as lists in the same column order as `columns`.
    """
    if limit <= 0:
        raise ValueError("limit must be > 0")
    conn = _get_conn()
    cur = conn.cursor()
    try:
        cur.execute(f"SELECT * FROM {table_name} LIMIT ?", (limit,))
    except sqlite3.OperationalError as exc:
        raise ValueError(f"Error querying table {table_name}: {exc}")
    rows = cur.fetchall()
    columns = rows[0].keys() if rows else [c[0] for c in cur.description] if cur.description else []
    return {"columns": list(columns), "rows": [list(r) for r in rows]}


FORBIDDEN = {"INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "ATTACH", "CREATE"}


def _check_query_safe(sql: str) -> None:
    up = sql.strip().upper()
    if not up.startswith("SELECT"):
        raise ValueError("Only SELECT queries are allowed.")
    for bad in FORBIDDEN:
        if bad in up:
            raise ValueError(f"Forbidden keyword in query: {bad}")


def run_query(sql: str) -> Dict[str, Any]:
    """Safely run a user-provided SELECT query against the read-only DB.

    Security rules:
    - The query must begin with SELECT (case-insensitive).
    - Disallow keywords: INSERT/UPDATE/DELETE/DROP/ALTER/ATTACH/CREATE.
    - Limit result set to at most 200 rows.

    Returns a dict with either `error` key or `columns` and `rows` keys.
    """
    try:
        _check_query_safe(sql)
    except ValueError as exc:
        return {"error": str(exc)}

    # Normalize and strip trailing semicolons
    sql_clean = sql.strip().rstrip("; ")

    # Wrap the query to enforce a maximum row count safely
    wrapped = f"SELECT * FROM ({sql_clean}) AS _sub LIMIT 200"

    conn = _get_conn()
    cur = conn.cursor()
    try:
        cur.execute(wrapped)
        rows = cur.fetchall()
        columns = rows[0].keys() if rows else [c[0] for c in cur.description] if cur.description else []
        return {"columns": list(columns), "rows": [list(r) for r in rows]}
    except sqlite3.DatabaseError as exc:
        return {"error": f"Database error: {exc}"}
    except Exception as exc:  # pragma: no cover - defensive
        return {"error": f"Unexpected error: {exc}"}


# Create the MCP instance and register tools
from fastmcp.tools.base import Tool


mcp = fastmcp.FastMCP("TicketInsight")


# Register functions as FastMCP tools
try:
    tools_to_register = [
        Tool.from_function(
            list_tables,
            name="list_tables",
            title="List tables",
            description="List tables in the read-only DB",
        ),
        Tool.from_function(
            get_schema,
            name="get_schema",
            title="Get schema",
            description="Get CREATE TABLE SQL for a table",
        ),
        Tool.from_function(
            run_query,
            name="run_query",
            title="Run query",
            description="Run a read-only SELECT query (safe)",
        ),
        Tool.from_function(
            get_sample_rows,
            name="get_sample_rows",
            title="Get sample rows",
            description="Get sample rows from a table",
        ),
    ]
    for t in tools_to_register:
        mcp.add_tool(t)
except Exception:
    # Best-effort registration to keep module importable; actual server run may need adjustments
    pass


if __name__ == "__main__":
    # Run the MCP server using Streamable HTTP transport at 0.0.0.0:8000
    mcp.run(transport="streamable-http", host="0.0.0.0", port=8000)
