from datetime import datetime
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from ...db import RoutineType, Schedule
from ...utils.model import create_partial_model
from .tasks import RoutineSubmission


class ScheduleCreateRequest(BaseModel):
    name: str | None = None
    cron: str
    enabled: bool = True
    submission: RoutineSubmission


if TYPE_CHECKING:
    type ScheduleUpdateRequest = Schedule

# 外部可写面: 仅 name/cron/enabled; 修改 task_type/payload 须删除后重建, last_run/next_run 由调度器维护, id 只读.
ScheduleUpdateRequest = create_partial_model(
    Schedule, fields=("name", "cron", "enabled"), partial_cls_name="ScheduleUpdateRequest"
)


class ScheduleResponse(BaseModel):
    id: int
    name: str | None = None
    cron: str
    task_type: RoutineType
    payload: dict = Field(default_factory=dict)
    enabled: bool
    last_run: datetime | None = None
    next_run: datetime | None = None


class ScheduleListResponse(BaseModel):
    items: list[ScheduleResponse]
    total: int
