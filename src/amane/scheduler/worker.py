"""
异步任务 worker -- 消费任务队列的后台循环.

作为 asyncio 任务在 FastAPI 事件循环内运行.
轮询 DB 中的排队任务, 执行 handler, 并更新状态.

可观测性:
    每个任务执行在独立的 contextvars 上下文中.
    Recorder 统一安装 task.log FileHandler 与结构化产物.
"""

import asyncio
import time
from contextlib import suppress
from typing import TYPE_CHECKING, Any

import structlog
from pydantic import BaseModel

from ..config import HotSettings
from ..events import EventType
from ..observability import Recorder

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping
    from pathlib import Path

    from ..db.models import Task, TaskType
    from ..db.repository import Repository
    from ..events import EventBus
    from ..handlers.protocol import TaskHandler

logger = structlog.get_logger()

# stop() 时等待活跃任务优雅退出的最长时间 (默认值, 可通过配置覆盖)
_DEFAULT_SHUTDOWN_TIMEOUT = 0


class AsyncWorker:
    """
    后台任务消费者.

    持续轮询任务队列并分发给已注册的 handler.
    通过 asyncio.Semaphore 控制并发.

    用法:
        worker = AsyncWorker(repo, handlers, concurrency=3)
        asyncio.create_task(worker.start())
        ...
        await worker.stop()
    """

    def __init__(
        self,
        repo: Repository,
        handlers: Mapping[TaskType, TaskHandler[Any, Any]],
        *,
        concurrency: int = 3,
        poll_interval: float = 2.0,
        shutdown_timeout: float = _DEFAULT_SHUTDOWN_TIMEOUT,
        event_bus: EventBus | None = None,
        log_dir: Path | None = None,
        get_hot: Callable[[], HotSettings] | None = None,
    ):
        self._repo = repo
        self._handlers = handlers
        self._concurrency = concurrency
        self._poll_interval = poll_interval
        self._shutdown_timeout = shutdown_timeout
        self._semaphore = asyncio.Semaphore(concurrency)
        self._running = False
        # 主循环 task: stop() 须取消并等待它退出, 否则「在飞 claim」会在 stop() 返回后
        # 继续认领 stop 之后新入队的任务 (API 测试 stop_worker 竞态即源于此).
        self._main_task: asyncio.Task[None] | None = None
        self._active_tasks: set[asyncio.Task] = set()
        # task_id -> asyncio.Task 映射, 用于按 ID 取消正在执行的任务
        self._running_tasks: dict[int, asyncio.Task] = {}
        # 完成信号 channel: 每个任务完成时 put task_id, 供外部精确同步
        self._done_queue: asyncio.Queue[int] = asyncio.Queue()
        self._event_bus = event_bus
        self._log_dir = log_dir
        self._get_hot = get_hot
        # 未 finalize 的 Recorder (shutdown 兜底 close)
        self._active_recorders: dict[int, Recorder] = {}
        self._paused = False

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def is_paused(self) -> bool:
        """暂停时循环仍在, 只是不再 claim 新任务; 已认领的继续跑."""
        return self._paused

    def set_paused(self, paused: bool) -> None:
        if self._paused == paused:
            return
        self._paused = paused
        logger.info("worker paused" if paused else "worker resumed")

    def start(self) -> None:
        """启动 worker 后台循环. 内部创建 Task, 立即返回."""
        self._main_task = asyncio.create_task(self._run_loop())

    async def stop(self) -> None:
        """停止 worker, 等待所有任务完成后返回."""
        self._running = False
        # 先终止主循环: 在飞 claim 若不取消, 可能恰在 stop() 返回后完成并认领
        # 之后新入队的任务, 导致「stop 后任务仍被 worker 拾取」.
        if self._main_task is not None and not self._main_task.done():
            self._main_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._main_task
            self._main_task = None
        # 关闭时: 等待活跃任务完成, 超时则强制取消
        await self._shutdown_active_tasks()
        failed = await self._repo.fail_all_running_tasks()
        for rec in list(self._active_recorders.values()):
            rec.close()
        self._active_recorders.clear()
        logger.info("worker stopped", marked_failed=failed)

    async def _run_loop(self) -> None:
        """worker 主循环. 持续轮询任务队列直到 stop() 被调用."""
        self._running = True
        logger.info("worker started", concurrency=self._concurrency, poll_interval=self._poll_interval)

        while self._running:
            # 尝试认领任务 (仅在未暂停且有空闲容量时)
            if not self._paused and self._semaphore._value > 0:
                task = await self._repo.claim_next_task()
                if task is not None:
                    t = asyncio.create_task(self._execute(task))
                    self._active_tasks.add(t)
                    t.add_done_callback(self._active_tasks.discard)
                    continue  # 立即检查更多任务

            await asyncio.sleep(self._poll_interval)

    async def cancel_task(self, task_id: int) -> bool:
        """取消正在执行的任务. 返回 True 表示已发送取消信号."""
        asyncio_task = self._running_tasks.get(task_id)
        if asyncio_task is None:
            return False
        asyncio_task.cancel()
        logger.info("task cancellation requested", task_id=task_id)
        return True

    async def _shutdown_active_tasks(self) -> None:
        """等待活跃任务完成, 超时后 cancel."""
        if not self._active_tasks:
            return
        try:
            await asyncio.wait_for(
                asyncio.gather(*self._active_tasks, return_exceptions=True), timeout=self._shutdown_timeout
            )
        except TimeoutError:
            logger.warning(
                "shutdown timeout, cancelling active tasks",
                timeout=self._shutdown_timeout,
                active_count=len(self._active_tasks),
            )
            for t in self._active_tasks:
                t.cancel()
            await asyncio.gather(*self._active_tasks, return_exceptions=True)

    async def _execute(self, task: Task) -> None:
        """使用 Semaphore 控制并发来执行单个任务"""
        assert task.id is not None
        task_id = task.id
        task_type_str = str(task.type)

        # ─── 绑定上下文: structlog contextvars ───
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(task_id=task_id, task_type=task_type_str)

        async with self._semaphore:
            handler = self._handlers.get(task.type)

            if handler is None:
                await self._repo.fail_task(task_id, error=f"No handler for {task.type}")
                self._done_queue.put_nowait(task_id)
                return

            try:
                typed_payload = handler.parse_payload(task.payload)
            except (TypeError, KeyError, ValueError) as e:
                await self._repo.fail_task(task_id, error=f"Invalid payload: {e}")
                self._done_queue.put_nowait(task_id)
                return

            # 注册到 running_tasks 以便外部按 ID 取消
            current = asyncio.current_task()
            assert current is not None
            self._running_tasks[task_id] = current

            # Inject progress callback
            async def _report_progress(current_val: int, total: int, message: str = "") -> None:
                if self._event_bus:
                    await self._event_bus.emit(
                        EventType.TASK_PROGRESS,
                        {"task_id": task_id, "current": current_val, "total": total, "message": message},
                    )

            handler.set_progress_callback(_report_progress)

            rec: Recorder | None = None
            if self._log_dir is not None:
                try:
                    started = await self._repo.get_task(task_id) or task
                    hot = self._get_hot() if self._get_hot is not None else HotSettings()
                    rec = Recorder.begin(self._log_dir, started, hot)
                    self._active_recorders[task_id] = rec
                    await self._repo.update_task_log_file(task_id, f"tasks/task-{task_id}/task.log")
                except Exception:
                    logger.exception("task recorder begin failed", task_id=task_id)
                    rec = None

            # Emit task.started
            if self._event_bus:
                await self._event_bus.emit(EventType.TASK_STARTED, {"task_id": task_id, "type": task_type_str})

            start_time = time.monotonic()
            # mode="json": payload 经 WS 广播时会被 json 序列化, set/enum/Path 等需先转为原生类型,
            # 否则 EventBus.broadcast 序列化失败 (见 events.py 对该类异常的处理).
            payload_dump = (
                typed_payload.model_dump(mode="json") if isinstance(typed_payload, BaseModel) else typed_payload
            )
            logger.info("task started", payload=payload_dump)

            def _debug_capture() -> bool:
                if self._get_hot is None:
                    return False
                return self._get_hot().logging.debug_capture

            async def _finalize_recorder(*, success: bool, error: str | None) -> None:
                if rec is None:
                    return
                try:
                    final = await self._repo.get_task(task_id) or task
                    rec.finalize(final, success=success, error=error, debug_capture=_debug_capture())
                except Exception:
                    logger.exception("task recorder finalize failed", task_id=task_id)
                    rec.close()

            try:
                try:
                    result = await handler.handle(typed_payload)
                except asyncio.CancelledError:
                    duration_s = round(time.monotonic() - start_time, 2)
                    logger.info("task cancelled", duration_s=duration_s)
                    await self._repo.fail_task(task_id, error="Cancelled by user")
                    await _finalize_recorder(success=False, error="Cancelled by user")
                    if self._event_bus:
                        await self._event_bus.emit(
                            EventType.TASK_FAILED,
                            {"task_id": task_id, "type": task_type_str, "error": "Cancelled by user"},
                        )
                    self._done_queue.put_nowait(task_id)
                    return
                except Exception as e:
                    duration_s = round(time.monotonic() - start_time, 2)
                    logger.exception("task crashed", error=str(e), duration_s=duration_s)
                    await self._repo.fail_task(task_id, error=str(e))
                    await _finalize_recorder(success=False, error=str(e))
                    if self._event_bus:
                        await self._event_bus.emit(
                            EventType.TASK_FAILED, {"task_id": task_id, "type": task_type_str, "error": str(e)}
                        )
                    self._done_queue.put_nowait(task_id)
                    return

                if result.success:
                    duration_s = round(time.monotonic() - start_time, 2)
                    followups = [(f.key, f.task_type, f.payload, f.priority) for f in (result.followups or [])]
                    try:
                        await self._repo.complete_task_with_followups(task_id, result.as_dict(), followups)
                    except Exception as e:
                        logger.exception("task complete with followups failed", error=str(e), duration_s=duration_s)
                        await self._repo.fail_task(task_id, error=str(e))
                        await _finalize_recorder(success=False, error=str(e))
                        if self._event_bus:
                            await self._event_bus.emit(
                                EventType.TASK_FAILED, {"task_id": task_id, "type": task_type_str, "error": str(e)}
                            )
                        self._done_queue.put_nowait(task_id)
                        return
                    logger.info("task completed", duration_s=duration_s, followups=[key for key, _, _, _ in followups])
                    await _finalize_recorder(success=True, error=None)
                    if self._event_bus:
                        await self._event_bus.emit(
                            EventType.TASK_COMPLETED, {"task_id": task_id, "type": task_type_str}
                        )
                else:
                    duration_s = round(time.monotonic() - start_time, 2)
                    err = result.error or "Unknown error"
                    await self._repo.fail_task(task_id, error=err)
                    logger.warning("task failed", error=result.error, duration_s=duration_s)
                    await _finalize_recorder(success=False, error=err)
                    if self._event_bus:
                        await self._event_bus.emit(
                            EventType.TASK_FAILED, {"task_id": task_id, "type": task_type_str, "error": err}
                        )

                self._done_queue.put_nowait(task_id)
            finally:
                self._running_tasks.pop(task_id, None)
                if rec is not None:
                    self._active_recorders.pop(task_id, None)
                    rec.close()
