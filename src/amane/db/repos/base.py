from __future__ import annotations

from typing import TYPE_CHECKING

from sqlmodel.ext.asyncio.session import AsyncSession

if TYPE_CHECKING:
    import asyncio


class RepositoryMixinBase:
    """RepoMixin 组合基类.

    子类须提供 ``_session()`` 返回 ``AsyncSession``; 任务类 mixin 还依赖
    ``_task_insert_lock`` 在并发下串行化任务入队 (insert-or-reuse 互斥). 本类方法经由组合对象调用.
    """

    _task_insert_lock: asyncio.Lock

    def _session(self) -> AsyncSession:
        raise NotImplementedError
