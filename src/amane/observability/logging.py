"""
日志配置 -- 基于 structlog 的统一日志管线.

设计:
- structlog 作为处理器后端, 兼容 stdlib logging (所有现有 getLogger 调用无需更改)
- 通过 contextvars 自动注入 task_id, request_id 等上下文
- 两种渲染目标: stderr (人类可读 + 颜色) / 文件 (结构化 JSON)
- WSEventLogHandler 将日志转发为 WebSocket 事件

在进程启动时调用 setup_logging() 进行初始化 (见 app/bootstrap.py).
"""

import asyncio
import logging
import sys
from logging.handlers import RotatingFileHandler
from typing import TYPE_CHECKING

import structlog

from ..events import EventType

if TYPE_CHECKING:
    from pathlib import Path

    from ..events import EventBus


MB = 1024 * 1024


# ─── WebSocket 日志转发 ─────────────────────────────────────────────────────────


class WSEventLogHandler(logging.Handler):
    """
    将 Python 日志记录转发为 WebSocket LOG 事件.

    从结构化日志中提取:
        level   - 日志级别
        source  - logger 名称短形式
        message - 事件消息
        + 所有 contextvars 绑定的字段 (task_id, request_id 等)
        + 所有 structlog extra 字段 (duration_s, fields, 等)
    """

    # 跳过的 LogRecord 标准属性 (不转发到前端)
    _SKIP_ATTRS = frozenset(
        {
            "name",
            "msg",
            "args",
            "levelname",
            "levelno",
            "pathname",
            "filename",
            "module",
            "exc_info",
            "exc_text",
            "stack_info",
            "lineno",
            "funcName",
            "created",
            "msecs",
            "relativeCreated",
            "thread",
            "threadName",
            "processName",
            "process",
            "message",
            "taskName",
            # structlog 内部
            "color_message",
        }
    )

    def __init__(self, event_bus: EventBus) -> None:
        super().__init__()
        self._event_bus = event_bus

    def emit(self, record: logging.LogRecord) -> None:
        try:
            source = record.name.rsplit(".", 1)[-1] if "." in record.name else record.name

            # structlog 通过 wrap_for_formatter 将 event_dict 存入 record.msg
            # stdlib 日志的 record.msg 则是普通字符串
            if isinstance(record.msg, dict):
                # structlog-originated: 从 event_dict 提取字段
                event_dict: dict = record.msg
                message = str(event_dict.get("event", ""))
                data: dict = {
                    "level": record.levelname,
                    "source": source,
                    "message": message,
                }
                # 转发所有其他字段 (排除 structlog 内部 key)
                # 注意: "timestamp" 不在此集合中 - 需要转发原始日志时间戳
                _INTERNAL_KEYS = {"event", "level", "logger", "_record", "_from_decorator"}
                for key, value in event_dict.items():
                    if key in _INTERNAL_KEYS:
                        continue
                    if isinstance(value, (str, int, float, bool, list, dict, type(None))):
                        data[key] = value
            else:
                # stdlib-originated: 普通 LogRecord
                message = record.getMessage()
                data = {
                    "level": record.levelname,
                    "source": source,
                    "message": message,
                }
                # 提取 extra 字段
                for key, value in record.__dict__.items():
                    if key.startswith("_") or key in self._SKIP_ATTRS:
                        continue
                    if isinstance(value, (str, int, float, bool, list, dict, type(None))):
                        data[key] = value

            try:
                loop = asyncio.get_running_loop()
                loop.call_soon_threadsafe(asyncio.ensure_future, self._event_bus.emit(EventType.LOG, data))
            except RuntimeError:
                pass  # 没有运行中的事件循环, 跳过
        except Exception:
            # handler 自身不能抛出异常
            pass


# ─── 核心配置 ──────────────────────────────────────────────────────────────────


def setup_logging(level: str = "INFO", event_bus: EventBus | None = None, log_dir: Path | None = None) -> None:
    """
     配置 structlog + stdlib 的统一日志管线.

     调用后效果:
    - 所有 logging.getLogger("amane.*") 的输出经过 structlog 处理器链
    - contextvars (task_id, request_id 等) 自动附加到每条日志
    - stderr: 人类可读彩色输出 (ConsoleRenderer)
    - 文件: 结构化 JSON (JSONRenderer)
    - WebSocket: 结构化事件转发

     Args:
         level: 日志级别 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
         event_bus: 可选, 用于转发日志到 WebSocket 客户端
         log_dir: 可选, 日志文件输出目录
    """
    # 幂等: 检查是否已配置
    root = logging.getLogger("amane")
    if root.handlers:
        return

    # ── 1. 共享处理器链 (structlog pipeline) ──
    # 这些处理器在最终渲染之前运行, 负责提取上下文/添加元数据.
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.ExceptionRenderer(),
    ]

    # ── 2. 配置 structlog ──
    # wrapper_class=BoundLogger 使直接使用 structlog.get_logger() 时获得标准接口
    # logger_factory=LoggerFactory() 使 structlog 最终委托给 stdlib logging
    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # ── 3. stdlib Handler 配置 (用 ProcessorFormatter 桥接) ──
    # foreign_pre_chain: 处理来自 stdlib logging (非 structlog) 的记录
    # 这确保了 getLogger().info() 也能获得 contextvars 注入的字段
    foreign_pre_chain = shared_processors

    root.setLevel(level.upper())

    # 3a. Console handler (stderr) - 人类可读彩色输出
    console_formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.dev.ConsoleRenderer(colors=sys.stderr.isatty()),
        ],
        foreign_pre_chain=foreign_pre_chain,
    )
    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setFormatter(console_formatter)
    root.addHandler(stderr_handler)

    # 3b. 文件 handler - 结构化 JSON (用于分析/告警)
    if log_dir:
        log_dir.mkdir(parents=True, exist_ok=True)

        json_formatter = structlog.stdlib.ProcessorFormatter(
            processors=[
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                structlog.processors.JSONRenderer(),
            ],
            foreign_pre_chain=foreign_pre_chain,
        )
        file_handler = RotatingFileHandler(
            log_dir / "app.log",
            maxBytes=10 * MB,
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setFormatter(json_formatter)
        root.addHandler(file_handler)

        # Request log: 独立文件, 独立 formatter
        request_logger = logging.getLogger("amane.request")
        request_logger.propagate = False
        req_console_formatter = structlog.stdlib.ProcessorFormatter(
            processors=[
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                structlog.dev.ConsoleRenderer(colors=sys.stderr.isatty()),
            ],
            foreign_pre_chain=foreign_pre_chain,
        )
        req_json_formatter = structlog.stdlib.ProcessorFormatter(
            processors=[
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                structlog.processors.JSONRenderer(),
            ],
            foreign_pre_chain=foreign_pre_chain,
        )

        req_file_handler = RotatingFileHandler(
            log_dir / "request.log",
            maxBytes=10 * MB,
            backupCount=5,
            encoding="utf-8",
        )
        req_file_handler.setFormatter(req_json_formatter)
        request_logger.addHandler(req_file_handler)

        req_stderr_handler = logging.StreamHandler(sys.stderr)
        req_stderr_handler.setFormatter(req_console_formatter)
        request_logger.addHandler(req_stderr_handler)
    else:
        # 无 log_dir 时, request logger 仍输出到 stderr
        request_logger = logging.getLogger("amane.request")
        request_logger.propagate = False
        req_console_formatter = structlog.stdlib.ProcessorFormatter(
            processors=[
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                structlog.dev.ConsoleRenderer(colors=sys.stderr.isatty()),
            ],
            foreign_pre_chain=foreign_pre_chain,
        )
        req_stderr_handler = logging.StreamHandler(sys.stderr)
        req_stderr_handler.setFormatter(req_console_formatter)
        request_logger.addHandler(req_stderr_handler)

    # 3c. WebSocket 日志转发
    if event_bus:
        ws_handler = WSEventLogHandler(event_bus)
        ws_handler.setLevel(logging.DEBUG)
        root.addHandler(ws_handler)

    # ── 4. 第三方库降噪 ──
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("watchdog").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
