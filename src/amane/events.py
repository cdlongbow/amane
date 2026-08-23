"""EventBus 供 scheduler 与 api 共用 (避免 api↔scheduler 环依赖)."""

import json
from contextlib import suppress
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from fastapi import WebSocket

logger = structlog.get_logger()


class EventType(StrEnum):
    """通过 WebSocket 广播的事件类型."""

    TASK_STARTED = "task.started"
    TASK_PROGRESS = "task.progress"
    TASK_COMPLETED = "task.completed"
    TASK_FAILED = "task.failed"
    FILE_DISCOVERED = "file.discovered"
    FILE_REMOVED = "file.removed"
    LOG = "log"


@dataclass
class Event:
    """广播给已连接客户端的单个事件."""

    type: EventType
    data: dict = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


class EventBus:
    """
    向所有已连接的 WebSocket 客户端广播事件.

    线程安全的单例, 管理 WebSocket 连接并分发事件.
    失效的连接会被自动清理.
    """

    def __init__(self) -> None:
        self._connections: list[WebSocket] = []

    @property
    def connection_count(self) -> int:
        """当前活跃的 WebSocket 连接数."""
        return len(self._connections)

    async def connect(self, ws: WebSocket) -> None:
        """接受并注册新的 WebSocket 连接."""
        await ws.accept()
        self._connections.append(ws)

    def disconnect(self, ws: WebSocket) -> None:
        """移除 WebSocket 连接."""
        if ws in self._connections:
            self._connections.remove(ws)

    async def close_all(self) -> None:
        """主动断开全部客户端, 避免 graceful shutdown 被常驻 WS 拖死."""
        connections = list(self._connections)
        self._connections.clear()
        for ws in connections:
            with suppress(Exception):
                await ws.close()

    async def broadcast(self, event: Event) -> None:
        """
        向所有已连接的客户端发送事件.

        发送失败时自动移除失效的连接. 但序列化失败 (event 数据含非 JSON 类型)
        是 event 自身的问题, 不能据此判定连接已死 - - 否则一条坏 event 会静默踢掉
        所有客户端, 且客户端 TCP 未断 (无 onclose), 表现为"绿灯长亮但收不到任何事件".
        """
        try:
            payload = asdict(event)
            # 提前序列化校验: 失败则丢弃该 event, 保留所有连接.
            json.dumps(payload)
        except TypeError, ValueError:
            logger.warning("dropping non-serializable event", event_type=str(event.type))
            return

        dead: list[WebSocket] = []
        for ws in self._connections:
            try:
                await ws.send_json(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._connections.remove(ws)

    async def emit(self, event_type: EventType, data: dict | None = None) -> None:
        """便捷方法, 创建并广播事件."""
        event = Event(type=event_type, data=data or {})
        await self.broadcast(event)
