"""
定时任务引擎 -- 基于 croniter 的后台调度循环.

每 60 秒检查所有已启用的 Schedule, 如果 next_run <= now 则创建对应 Task,
并更新 last_run / next_run.
"""

import asyncio
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import structlog
from croniter import croniter
from structlog.contextvars import bound_contextvars

from ..db import RoutineType, TaskType
from ..handlers import CleanupPayload, R18ImportPayload, RescrapePayload, UpscalePayload

if TYPE_CHECKING:
    from ..db.repository import Repository

logger = structlog.get_logger()

_CHECK_INTERVAL = 60.0  # 检查间隔 (秒)


class CronScheduler:
    """后台 cron 调度器, 作为 asyncio 任务运行."""

    def __init__(self, repo: Repository):
        self._repo = repo
        self._running = False

    @property
    def is_running(self) -> bool:
        return self._running

    async def start(self) -> None:
        """启动调度循环. 阻塞直到 stop() 被调用."""
        self._running = True
        logger.info("cron scheduler started", interval=_CHECK_INTERVAL)

        while self._running:
            try:
                await self._tick()
            except Exception:
                logger.exception("cron scheduler tick error")
            await asyncio.sleep(_CHECK_INTERVAL)

    async def stop(self) -> None:
        """通知调度器停止"""
        self._running = False
        logger.info("cron scheduler stopping")

    async def _tick(self) -> None:
        """单次检查: 遍历所有已启用 schedule, 触发到期任务."""
        now = datetime.now(UTC)
        schedules = await self._repo.list_schedules()

        for schedule in schedules:
            if not schedule.enabled:
                continue
            if schedule.id is None:
                continue

            if schedule.next_run is None:
                # 计算初始 next_run
                next_run = croniter(schedule.cron, now).get_next(datetime)
                await self._repo.update_schedule(schedule.id, next_run=next_run)
            else:
                # 处理时区
                next_run = schedule.next_run if schedule.next_run.tzinfo else schedule.next_run.replace(tzinfo=UTC)

            if next_run > now:
                continue

            with bound_contextvars(schedule_id=schedule.id, schedule_name=schedule.name, task_type=schedule.task_type):
                logger.info("schedule triggered", payload=schedule.payload)
                await self._execute_task(schedule.id, schedule.task_type, schedule.payload)

            # 更新 last_run 和 next_run
            new_next_run = croniter(schedule.cron, now).get_next(datetime)
            await self._repo.update_schedule(schedule.id, last_run=now, next_run=new_next_run)

    async def _execute_task(self, schedule_id: int, task_type: RoutineType, payload: dict) -> None:
        match task_type:
            case RoutineType.CLEANUP:
                await self._repo.create_task(
                    TaskType.CLEANUP,
                    CleanupPayload(
                        remove_missing_files=payload.get("remove_missing_files", True),
                        remove_unreferenced_resources=payload.get("remove_unreferenced_resources", True),
                    ),
                )
            case RoutineType.UPSCALE:
                await self._repo.create_task(
                    TaskType.UPSCALE,
                    UpscalePayload(
                        max_dim_threshold=payload.get("max_dim_threshold"),
                        max_bytes_threshold=payload.get("max_bytes_threshold"),
                        limit=payload.get("limit", 200),
                    ),
                )
            case RoutineType.R18_IMPORT:
                await self._repo.create_task(TaskType.R18_IMPORT, R18ImportPayload(force=payload.get("force", False)))
            case RoutineType.RESCRAPE:
                await self._repo.create_task(
                    TaskType.RESCRAPE,
                    RescrapePayload(limit=payload.get("limit", 100), min_age_days=payload.get("min_age_days")),
                )
            case _:
                logger.warning("unknown task type", task_type=task_type)
