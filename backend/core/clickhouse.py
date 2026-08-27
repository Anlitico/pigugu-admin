"""Read-only ClickHouse query helpers.

asynch connects over the native protocol (port 9000); `connect()` returns a
Connection synchronously and `async with conn:` opens/closes it. SELECT
parameters must be passed as a dict (a list/tuple makes asynch treat the
query as an INSERT) with pyformat `%(name)s` placeholders.
"""
from __future__ import annotations

from typing import Any

from asynch import connect as ch_connect

from core.config import settings


def _connect():
    return ch_connect(
        user=settings.clickhouse_user,
        password=settings.clickhouse_password,
        host=settings.clickhouse_host,
        port=settings.clickhouse_port,
        database=settings.clickhouse_database,
    )


async def query(sql: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Run a SELECT and return rows as dicts keyed by column name."""
    conn = _connect()
    async with conn:
        async with conn.cursor() as cur:
            await cur.execute(sql, params)
            rows = await cur.fetchall()
            columns = [c.name for c in cur.description]
            return [dict(zip(columns, row)) for row in rows]
