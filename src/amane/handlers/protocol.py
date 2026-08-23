from abc import ABC, abstractmethod
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel

from ..db.models import TaskType

# 进度回调类型: (current, total, message) -> None
type ProgressCallback = Callable[[int, int, str], Coroutine[Any, Any, None]]


class FollowupTask(BaseModel):
    """处理器声明的动态后继任务描述.

    处理器只描述结果, 不直接写队列. 由 worker 完成阶段统一创建子任务并写 TaskLink.
    """

    key: str
    """父节点内后继语义键 (fan-out 须含实体 id, 如 scrape:{media_file_id}); 同父同名只留一条."""
    task_type: TaskType
    payload: dict
    """已完成绑定的类型化 payload (处理器自己组装, 不再透传父任务字段)."""
    priority: int = 0


@dataclass
class TaskResult[R: BaseModel | dict]:
    """handler 执行结果: 成功标志 + 类型化结果/错误 + 声明的后继任务."""

    success: bool
    result: R | None = None
    error: str | None = None
    followups: list[FollowupTask] = field(default_factory=list)

    def as_dict(self) -> dict | None:
        """序列化为可写入 Task.result JSON 列的 dict."""
        if isinstance(self.result, dict):
            return self.result
        if isinstance(self.result, BaseModel):
            return self.result.model_dump()
        return None


class TaskHandler[P: BaseModel | dict = dict, R: BaseModel | dict = dict](ABC):
    """P = payload, R = result; 由 Worker 按 TaskType 调度."""

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)

    def __init__(self, payload_t: type[P], result_t: type[R]) -> None:
        self.payload_type = payload_t
        self.result_type = result_t

    @abstractmethod
    async def handle(self, payload: P) -> TaskResult[R]:
        """使用给定的 payload 执行任务, 返回结果"""
        ...

    def parse_payload(self, raw: dict) -> P:
        """从 dict 反序列化为类型化 payload; 已是目标类型时原样返回."""
        if isinstance(raw, self.payload_type):
            return raw
        if issubclass(self.payload_type, BaseModel):
            return self.payload_type.model_validate(raw)  # type: ignore
        raise TypeError(f"Unsupported payload type: {self.payload_type}")

    # --- Progress reporting ---

    _progress_callback: ProgressCallback | None = None

    def set_progress_callback(self, callback: ProgressCallback | None) -> None:
        """由 worker 在 handle() 前调用, 注入进度上报回调."""
        self._progress_callback = callback

    async def report_progress(self, current: int, total: int, message: str = "") -> None:
        """handler 内部调用, 上报进度. 无回调时静默忽略."""
        if self._progress_callback:
            await self._progress_callback(current, total, message)
