"""数据访问层 - 组合各聚合 mixin.

类型与排序映射见 ``repo_types``; facet 辅助见 ``repos.facet_helpers``.
"""

import asyncio
from typing import TYPE_CHECKING

from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from . import repos

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine


class Repository(
    repos.AgentRepoMixin,
    repos.FacetsRepoMixin,
    repos.FeedsRepoMixin,
    repos.LibrariesRepoMixin,
    repos.MediaRepoMixin,
    repos.MetadataRepoMixin,
    repos.SchedulesRepoMixin,
    repos.TasksRepoMixin,
):
    """基于 SQLModel 表的异步数据访问层"""

    def __init__(self, engine: AsyncEngine):
        self._engine = engine
        # SQLite DEFERRED: 两个 session 的 SELECT 都在写锁前看到空表. 入队互斥检查与 INSERT 同锁.
        self._task_insert_lock = asyncio.Lock()

    async def initialize(self) -> None:
        """创建所有表 (应用启动时调用一次)"""
        async with self._engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)

    def _session(self) -> AsyncSession:
        return AsyncSession(self._engine, expire_on_commit=False)
