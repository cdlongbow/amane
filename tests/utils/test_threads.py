"""@in_thread: await 进线程池且不堵事件循环; 已在工作线程里用 .sync."""

from __future__ import annotations

import asyncio
import threading
import time
from pathlib import Path

import pytest

from amane.utils.threads import in_thread, path_exists, path_is_dir


@in_thread
def _greet(*, name: str) -> str:
    return f"hi {name}"


@in_thread
def _boom() -> None:
    raise ValueError("nope")


@in_thread
def _ident() -> int:
    return threading.get_ident()


class TestInThread:
    def test_sync_kwargs_and_caller_thread(self):
        assert _greet.sync(name="a") == "hi a"
        assert threading.get_ident() == _ident.sync()

    def test_sync_raises(self):
        with pytest.raises(ValueError, match="nope"):
            _boom.sync()

    @pytest.mark.asyncio
    async def test_await_kwargs_off_loop_thread(self):
        assert await _greet(name="a") == "hi a"
        assert await _ident() != threading.get_ident()

    @pytest.mark.asyncio
    async def test_await_raises(self):
        with pytest.raises(ValueError, match="nope"):
            await _boom()

    @pytest.mark.asyncio
    async def test_nested_sync_stays_on_worker(self):
        inner_ident: list[int] = []

        @in_thread
        def inner() -> None:
            inner_ident.append(threading.get_ident())

        @in_thread
        def outer() -> int:
            inner.sync()
            return threading.get_ident()

        outer_id = await outer()
        assert inner_ident == [outer_id]

    @pytest.mark.asyncio
    async def test_does_not_block_event_loop(self):
        order: list[str] = []

        @in_thread
        def slow() -> None:
            order.append("work_start")
            time.sleep(0.15)
            order.append("work_end")

        async def marker() -> None:
            await asyncio.sleep(0.04)
            order.append("marker")

        await asyncio.gather(slow(), marker())
        assert order.index("marker") < order.index("work_end")

    @pytest.mark.asyncio
    async def test_path_exists_and_is_dir(self, tmp_path: Path):
        missing = tmp_path / "nope"
        d = tmp_path / "d"
        d.mkdir()
        f = tmp_path / "f.txt"
        f.write_text("x")
        assert await path_exists(d) is True
        assert await path_exists(missing) is False
        assert await path_is_dir(d) is True
        assert await path_is_dir(f) is False
        assert await path_is_dir(missing) is False
