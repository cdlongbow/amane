from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING

import structlog
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine

from .sqlite_migrate import upgrade_sqlite_database

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

logger = structlog.get_logger()


async def create_async_engine_from_path(db_path: Path | str) -> AsyncEngine:
    """
    为指定文件创建异步 SQLite 引擎.

    启动时先做 WAL 安全备份 (若落后 head), 再以事务性 DDL 跑 Alembic upgrade.
    业务连接仍用默认 SQLite 模式 + WAL; 事务性 DDL 仅用于迁移连接.
    """
    path = Path(db_path)
    try:
        upgrade_sqlite_database(path)
    except Exception as e:
        raise RuntimeError(f"Database migration failed: {e}") from e

    url = f"sqlite+aiosqlite:///{path}"
    engine = create_async_engine(url, echo=False)

    # 为每个新连接启用 WAL 并开启外键约束
    @event.listens_for(engine.sync_engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    logger.info("database ready", path=str(path))
    return engine


@asynccontextmanager
async def get_session(engine: AsyncEngine) -> AsyncGenerator[AsyncSession]:
    """提供作用域为上下文管理器的异步 session"""
    async with AsyncSession(engine, expire_on_commit=False) as session:
        yield session
