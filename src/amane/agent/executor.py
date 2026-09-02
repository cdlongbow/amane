"""Saved Query 结果解析: 缓存命中或 Live 重跑."""

from __future__ import annotations

from typing import Any

from ..db.models import SavedQuery
from .cache import CachedResult, ResultCache
from .sql import ReadonlySqlSandbox, SqlResult


def extract_entity_ids(columns: list[str], rows: list[list[Any]]) -> list[int]:
    """从结果中抽出 `id` 列; 缺失则抛 ValueError."""
    lowered = [c.lower() for c in columns]
    if "id" not in lowered:
        raise ValueError("结果必须包含名为 id 的主键列")
    idx = lowered.index("id")
    ids: list[int] = []
    seen: set[int] = set()
    for row in rows:
        raw = row[idx]
        if raw is None:
            continue
        value = int(raw)
        if value not in seen:
            seen.add(value)
            ids.append(value)
    return ids


class QueryExecutor:
    """执行 Saved Query / 填充 ResultCache."""

    def __init__(self, sandbox: ReadonlySqlSandbox, cache: ResultCache) -> None:
        self.sandbox = sandbox
        self.cache = cache

    async def run_sql(
        self,
        sql: str,
        *,
        timeout_ms: int,
        allow_slow: bool = False,
        approved: bool = False,
        max_rows: int | None = None,
    ) -> SqlResult:
        return await self.sandbox.execute(
            sql,
            timeout_ms=timeout_ms,
            allow_slow=allow_slow,
            approved=approved,
            max_rows=max_rows,
        )

    async def ensure_cached(
        self,
        query: SavedQuery,
        *,
        timeout_ms: int,
        approved: bool = False,
    ) -> CachedResult:
        """优先复用缓存; 未命中则执行 SQL 并写回缓存 (可能触发审批/重跑)."""
        assert query.id is not None
        hit = self.cache.get(query.id)
        if hit is not None:
            return hit
        result = await self.run_sql(query.sql, timeout_ms=timeout_ms, approved=approved)
        entry = CachedResult(saved_query_id=query.id, columns=result.columns, rows=result.rows)
        self.cache.put(entry)
        return entry
