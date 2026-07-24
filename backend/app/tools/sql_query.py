import re
from typing import Any

from sqlalchemy import text

from app.db.sql_demo import get_sql_demo_engine
from app.tools.base import BaseTool, ToolDefinition

# Row/character caps exist independently of the LIMIT injected into the query itself - a second,
# code-level backstop in case a statement already has its own (larger) LIMIT.
_MAX_ROWS = 200
_MAX_OUTPUT_CHARS = 4000
_STATEMENT_TIMEOUT_MS = 5000

_FORBIDDEN_KEYWORDS = (
    "insert", "update", "delete", "drop", "alter", "truncate", "grant", "revoke",
    "copy", "call", "execute", "merge", "into", "vacuum", "listen", "notify",
    "set", "reset", "begin", "commit", "rollback", "savepoint", "lock", "create",
    "do", "prepare", "deallocate", "explain", "analyze", "refresh", "cluster",
    "reindex", "discard", "checkpoint",
)
_FORBIDDEN_RE = re.compile(r"\b(" + "|".join(_FORBIDDEN_KEYWORDS) + r")\b", re.IGNORECASE)
_SELECT_RE = re.compile(r"^\s*select\b", re.IGNORECASE)
_LIMIT_RE = re.compile(r"\blimit\b", re.IGNORECASE)


def validate_readonly_sql(query: str) -> str:
    """Rejects anything that isn't a single, plain SELECT statement, before it ever reaches
    Postgres. This is a second layer on top of the sql_demo_reader role's own SELECT-only grant
    (app/db/sql_demo.py) - not a substitute for it, since a role-level permission denied is the
    guarantee that actually holds if this regex has a gap."""
    if not isinstance(query, str) or not query.strip():
        raise ValueError("'query' must be a non-empty string")

    if "--" in query or "/*" in query:
        raise ValueError("SQL comments are not allowed")

    statements = [s.strip() for s in query.split(";") if s.strip()]
    if len(statements) != 1:
        raise ValueError("Exactly one SQL statement is allowed (no semicolon-separated batches)")
    statement = statements[0]

    if not _SELECT_RE.match(statement):
        raise ValueError("Only SELECT statements are allowed")

    forbidden = _FORBIDDEN_RE.search(statement)
    if forbidden:
        raise ValueError(f"Disallowed SQL keyword: '{forbidden.group(0)}'")

    if not _LIMIT_RE.search(statement):
        statement = f"{statement} LIMIT {_MAX_ROWS}"

    return statement


def _format_rows(columns: list[str], rows: list[tuple[Any, ...]]) -> str:
    if not rows:
        return "(no rows)"

    lines = [" | ".join(columns)]
    for row in rows:
        lines.append(" | ".join(str(value) for value in row))
    output = "\n".join(lines)

    if len(output) > _MAX_OUTPUT_CHARS:
        output = output[:_MAX_OUTPUT_CHARS] + "\n... (truncated)"
    return output


class SqlQueryTool(BaseTool):
    definition = ToolDefinition(
        name="sql_query",
        description=(
            "Runs a read-only SQL SELECT query against a sample company database (schema "
            "'sql_demo') to answer questions about employees and departments. Tables: "
            "sql_demo.departments(id, name), "
            "sql_demo.employees(id, name, department_id, salary, hire_date). "
            "Only SELECT statements are permitted."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "A single SELECT statement, e.g. "
                        "\"SELECT name, salary FROM sql_demo.employees ORDER BY salary DESC LIMIT 1\""
                    ),
                }
            },
            "required": ["query"],
        },
        permission_level="public",
        timeout_seconds=10.0,
    )

    async def run(self, **kwargs: Any) -> str:
        statement = validate_readonly_sql(kwargs.get("query", ""))

        engine = get_sql_demo_engine()
        async with engine.begin() as conn:
            await conn.execute(text(f"SET LOCAL statement_timeout = '{_STATEMENT_TIMEOUT_MS}'"))
            result = await conn.execute(text(statement))
            columns = list(result.keys())
            rows = result.fetchmany(_MAX_ROWS)

        return _format_rows(columns, [tuple(row) for row in rows])
