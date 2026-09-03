"""ReadonlySqlSandbox / ResultCache 表测试."""

from __future__ import annotations

from pathlib import Path

import pytest
import pytest_asyncio

from amane.agent.cache import CachedResult, ResultCache
from amane.agent.sql import ReadonlySqlSandbox, SqlNeedsApproval, SqlSandboxError, SqlTimeoutError, as_id_subquery_sql


@pytest.mark.parametrize(
    ("sql", "expect"),
    [
        ("SELECT id FROM metadata", "SELECT id FROM (SELECT id FROM metadata) AS _sq"),
        (
            "  select id, title from metadata where 1  ",
            "SELECT id FROM (select id, title from metadata where 1) AS _sq",
        ),
        ("SELECT 1; ", "SELECT id FROM (SELECT 1) AS _sq"),
    ],
)
def test_as_id_subquery_sql(sql: str, expect: str) -> None:
    assert as_id_subquery_sql(sql) == expect


@pytest_asyncio.fixture
async def sandbox(tmp_path: Path) -> ReadonlySqlSandbox:
    import aiosqlite

    db = tmp_path / "t.db"
    async with aiosqlite.connect(db) as conn:
        await conn.execute("CREATE TABLE items (id INTEGER PRIMARY KEY, name TEXT)")
        await conn.executemany("INSERT INTO items (name) VALUES (?)", [("a",), ("b",), ("c",)])
        await conn.commit()
    return ReadonlySqlSandbox(db)


@pytest.mark.asyncio
async def test_execute_select(sandbox: ReadonlySqlSandbox) -> None:
    result = await sandbox.execute("SELECT id, name FROM items ORDER BY id", timeout_ms=1000)
    assert result.columns == ["id", "name"]
    assert result.row_count == 3
    assert result.rows[0] == [1, "a"]


@pytest.mark.asyncio
async def test_execute_allows_literal_keywords(sandbox: ReadonlySqlSandbox) -> None:
    """字面量里的黑名单单词是合法查询 — 无词法校验, 只读连接直接放行."""
    result = await sandbox.execute(
        "SELECT id FROM items WHERE name LIKE '%update%' OR name LIKE '%delete%'", timeout_ms=1000
    )
    assert result.row_count == 0


@pytest.mark.asyncio
async def test_execute_rejects_write(sandbox: ReadonlySqlSandbox) -> None:
    with pytest.raises(SqlSandboxError, match="readonly"):
        await sandbox.execute("DELETE FROM items", timeout_ms=1000)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("sql", "match"),
    [
        ("ATTACH DATABASE 'x.db' AS other", "not authorized"),
        ("PRAGMA journal_mode=WAL", "not authorized"),
        ("VACUUM INTO 'x.db'", "authorization denied"),
    ],
)
async def test_execute_rejects_attach_pragma_vacuum(sandbox: ReadonlySqlSandbox, sql: str, match: str) -> None:
    """解析层授权拒绝 ATTACH/PRAGMA/VACUUM INTO — mode=ro 只约束 main 库, 无法拦截这三者."""
    with pytest.raises(SqlSandboxError, match=match):
        await sandbox.execute(sql, timeout_ms=1000)


@pytest.mark.asyncio
async def test_execute_attach_creates_no_file(sandbox: ReadonlySqlSandbox, tmp_path: Path) -> None:
    """ATTACH 在授权回调处被拒, 目标文件不会被创建."""
    target = tmp_path / "evil.db"
    with pytest.raises(SqlSandboxError, match="not authorized"):
        await sandbox.execute(f"ATTACH DATABASE '{target}' AS evil", timeout_ms=1000)
    assert not target.exists()


@pytest.mark.asyncio
async def test_execute_vacuum_into_creates_no_file(sandbox: ReadonlySqlSandbox, tmp_path: Path) -> None:
    """VACUUM INTO 在只读连接上本可写出新库文件, 解析层授权阻止其落盘."""
    target = tmp_path / "out.db"
    with pytest.raises(SqlSandboxError, match="authorization denied"):
        await sandbox.execute(f"VACUUM INTO '{target}'", timeout_ms=1000)
    assert not target.exists()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "sql",
    [
        "SELECT missing_col FROM items",
        "SELECT id FROM no_such_table",
        "SELECT metadata_id FROM items",
    ],
)
async def test_execute_sqlite_errors_become_sandbox_errors(sandbox: ReadonlySqlSandbox, sql: str) -> None:
    """执行期 SQLite 错误须包装为 SqlSandboxError, 供工具返回 error 而非打断整轮."""
    with pytest.raises(SqlSandboxError, match=r"no such (column|table)"):
        await sandbox.execute(sql, timeout_ms=1000)


@pytest.mark.asyncio
async def test_allow_slow_needs_approval(sandbox: ReadonlySqlSandbox) -> None:
    with pytest.raises(SqlNeedsApproval):
        await sandbox.execute("SELECT 1", timeout_ms=1000, allow_slow=True, approved=False)


@pytest.mark.asyncio
async def test_allow_slow_approved(sandbox: ReadonlySqlSandbox) -> None:
    result = await sandbox.execute("SELECT 1 AS n", timeout_ms=5000, allow_slow=True, approved=True)
    assert result.rows == [[1]]


@pytest.mark.asyncio
async def test_timeout(sandbox: ReadonlySqlSandbox) -> None:
    sql = """
    WITH RECURSIVE t(x) AS (
      SELECT 1
      UNION ALL
      SELECT x + 1 FROM t WHERE x < 5000000
    )
    SELECT COUNT(*) FROM t
    """
    with pytest.raises(SqlTimeoutError):
        await sandbox.execute(sql, timeout_ms=1)


@pytest.mark.asyncio
async def test_max_rows_truncation(sandbox: ReadonlySqlSandbox) -> None:
    result = await sandbox.execute("SELECT id FROM items ORDER BY id", timeout_ms=1000, max_rows=2)
    assert len(result.rows) == 2
    assert result.row_count == -1  # more rows exist


def test_result_cache_lru_and_get() -> None:
    cache = ResultCache(ttl_s=3600, max_entries=2)
    cache.put(CachedResult(1, ["id"], [[1]]))
    cache.put(CachedResult(2, ["id"], [[2]]))
    assert cache.get(1) is not None
    cache.put(CachedResult(3, ["id"], [[3]]))
    assert cache.get(2) is None  # LRU evicted
    assert cache.get(1) is not None
    assert cache.get(3) is not None


def test_result_cache_ttl(monkeypatch: pytest.MonkeyPatch) -> None:
    cache = ResultCache(ttl_s=10, max_entries=8)
    cache.put(CachedResult(1, ["id"], [[1]], created_at=0.0))
    monkeypatch.setattr("amane.agent.cache.time.monotonic", lambda: 11.0)
    assert cache.get(1) is None
