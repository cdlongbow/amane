"""把同步函数调度到默认线程池, 供事件循环 ``await``.

已在工作线程里的代码用 ``.sync`` 调原函数, 不要再进一次线程池.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from functools import update_wrapper
from pathlib import Path
from typing import Any


class in_thread[**P, R]:
    """装饰同步函数: ``await fn(...)`` 进线程池, ``fn.sync(...)`` 原地执行."""

    __slots__ = ("__dict__", "__wrapped__", "sync")

    def __init__(self, fn: Callable[P, R]) -> None:
        self.sync = fn
        update_wrapper(self, fn)

    def __call__(self, *args: P.args, **kwargs: P.kwargs) -> Coroutine[Any, Any, R]:
        return asyncio.to_thread(self.sync, *args, **kwargs)


@in_thread
def path_exists(path: Path, *, follow_symlinks: bool = True) -> bool:
    return path.exists(follow_symlinks=follow_symlinks)


@in_thread
def path_is_dir(path: Path) -> bool:
    return path.is_dir()
