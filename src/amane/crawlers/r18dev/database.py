"""r18.dev 只读 PostgreSQL 引擎管理.

与主 SQLite 库完全隔离: 独立 asyncpg 引擎, 不进 Alembic, 不进 HotSettings 热重载链.
引擎在 bootstrap 惰性建立 (dsn 未配置则不连), 注入 CrawlerFactory 供 R18DevCrawler 使用.

无全局单例: 实例由调用方持有并注入 (遵循项目"禁止全局变量"约定).
内置连接池天然并发安全, 实例可长期缓存复用 (爬虫无状态语义).
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine


class R18Database:
    """r18 只读镜像的连接管理器.

    持有一个 asyncpg 引擎 + sessionmaker. 每次查询从 sessionmaker 开短生命周期 session,
    用完即关 - 并发请求各拿各的连接, 互不干扰.
    """

    def __init__(self, read_url: str, *, echo: bool = False, pool_size: int = 5, max_overflow: int = 10):
        self._read_url = read_url
        self._engine: AsyncEngine = create_async_engine(
            read_url,
            echo=echo,
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_pre_ping=True,
        )
        self._session_factory = async_sessionmaker(self._engine, class_=AsyncSession, expire_on_commit=False)

    @property
    def engine(self) -> AsyncEngine:
        return self._engine

    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession]:
        """只读 session 上下文. 不提交 (纯查询); 异常时回滚."""
        async with self._session_factory() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise

    async def close(self) -> None:
        await self._engine.dispose()
