"""sql_explore create_view / materialize_saved_query 表测试."""

from __future__ import annotations

from pathlib import Path

import aiosqlite
import pytest
import pytest_asyncio

from amane.agent.cache import ResultCache
from amane.agent.executor import QueryExecutor
from amane.agent.sql import ReadonlySqlSandbox
from amane.agent.tools import AgentDeps, materialize_saved_query
from amane.agent.trace import TraceEvent
from amane.db.models import SavedQueryEntity
from amane.db.repository import Repository


class _MemTrace:
    def __init__(self) -> None:
        self.events: list[TraceEvent] = []

    def append(self, event: TraceEvent) -> None:
        self.events.append(event)


@pytest_asyncio.fixture
async def explore_env(tmp_path: Path, repo: Repository) -> tuple[AgentDeps, Path]:
    db = tmp_path / "explore.db"
    async with aiosqlite.connect(db) as conn:
        await conn.execute("CREATE TABLE metadata (id INTEGER PRIMARY KEY, title TEXT)")
        await conn.executemany("INSERT INTO metadata (title) VALUES (?)", [(f"t{i}",) for i in range(1, 31)])
        await conn.commit()

    session = await repo.create_agent_session(title="explore")
    assert session.id is not None
    sandbox = ReadonlySqlSandbox(db)
    cache = ResultCache(ttl_s=3600, max_entries=16)
    executor = QueryExecutor(sandbox, cache)
    deps = AgentDeps(
        repo=repo,
        executor=executor,
        session_id=session.id,
        trace=_MemTrace(),  # type: ignore[arg-type]
        sql_timeout_ms=5000,
        sample_limit=5,
    )
    return deps, db


@pytest.mark.asyncio
async def test_materialize_explore_view_not_surfaced(explore_env: tuple[AgentDeps, Path]) -> None:
    """探查视图是行数组: 无 entity、无 id 列要求, 不挂交付芯片."""
    deps, _db = explore_env
    result = await deps.executor.run_sql("SELECT title FROM metadata ORDER BY id", timeout_ms=deps.sql_timeout_ms)
    view_id, name, entity_ids = await materialize_saved_query(
        deps,
        sql="SELECT title FROM metadata ORDER BY id",
        entity=None,
        name="probe",
        result=result,
        surface_to_user=False,
    )
    assert view_id > 0
    assert name == "probe"
    assert entity_ids == []
    assert deps.last_saved_query_ids == []
    assert deps.executor.cache.get(view_id) is not None

    query = await deps.repo.get_saved_query(view_id)
    assert query is not None
    assert query.entity == SavedQueryEntity.DATA
    cached = await deps.executor.ensure_cached(query, timeout_ms=deps.sql_timeout_ms)
    assert len(cached.rows) == 30
    assert cached.rows[5:8] == [["t6"], ["t7"], ["t8"]]


@pytest.mark.asyncio
async def test_materialize_deliver_surfaces_to_user(explore_env: tuple[AgentDeps, Path]) -> None:
    """实体交付: 抽 id 列并挂芯片."""
    deps, _db = explore_env
    result = await deps.executor.run_sql("SELECT id FROM metadata WHERE id <= 3", timeout_ms=deps.sql_timeout_ms)
    view_id, _name, entity_ids = await materialize_saved_query(
        deps,
        sql="SELECT id FROM metadata WHERE id <= 3",
        entity=SavedQueryEntity.METADATA,
        name=None,
        result=result,
        surface_to_user=True,
    )
    assert entity_ids == [1, 2, 3]
    assert deps.last_saved_query_ids == [view_id]


@pytest.mark.asyncio
async def test_materialize_data_deliver_without_id(explore_env: tuple[AgentDeps, Path]) -> None:
    """data 交付不要求 id 列, 落库 entity=data 并挂芯片."""
    deps, _db = explore_env
    result = await deps.executor.run_sql(
        "SELECT title FROM metadata WHERE id <= 2 ORDER BY id", timeout_ms=deps.sql_timeout_ms
    )
    view_id, _name, entity_ids = await materialize_saved_query(
        deps,
        sql="SELECT title FROM metadata WHERE id <= 2 ORDER BY id",
        entity=None,
        name=None,
        result=result,
        surface_to_user=True,
    )
    assert entity_ids == []
    query = await deps.repo.get_saved_query(view_id)
    assert query is not None
    assert query.entity == SavedQueryEntity.DATA
    assert query.name == "数据查询"
    assert deps.last_saved_query_ids == [view_id]


@pytest.mark.asyncio
async def test_materialize_entity_deliver_requires_id(explore_env: tuple[AgentDeps, Path]) -> None:
    """实体交付契约: 缺 id 列必须报错, 保证列表子查询嵌入可用."""
    deps, _db = explore_env
    result = await deps.executor.run_sql("SELECT title FROM metadata", timeout_ms=deps.sql_timeout_ms)
    with pytest.raises(ValueError, match="id"):
        await materialize_saved_query(
            deps,
            sql="SELECT title FROM metadata",
            entity=SavedQueryEntity.METADATA,
            name=None,
            result=result,
            surface_to_user=True,
        )


@pytest.mark.asyncio
async def test_explore_without_view_truncates_sample(explore_env: tuple[AgentDeps, Path]) -> None:
    deps, _db = explore_env
    result = await deps.executor.run_sql(
        "SELECT id FROM metadata ORDER BY id", timeout_ms=deps.sql_timeout_ms, max_rows=deps.sample_limit
    )
    assert len(result.rows) == 5
    assert result.row_count == -1
