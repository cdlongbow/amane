"""任务记录的字段级契约.

config.hot.json 直接复用 HotSettings dump, 不在此平行建模.
"""

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field

from ..net.errors import FailureReason

RECORD_VERSION: Literal[2] = 2
SECRETS_HOT_FILENAME = ".secrets.hot.json"
REDACTION_PLACEHOLDER = "***"


class CaptureReason(StrEnum):
    """HTTP body 落盘原因."""

    FAILURE = "failure"
    DEBUG_FLAG = "debug_flag"
    NONE = "none"


class RecordManifest(BaseModel):
    """任务记录根清单."""

    record_version: Literal[2] = RECORD_VERSION
    amane_version: str
    created_at: datetime
    task_id: int
    redacted: bool
    http_captured: bool
    capture_reason: CaptureReason


class TaskSnapshot(BaseModel):
    """与 DB Task 对齐的可序列化子集."""

    id: int
    type: str
    status: str
    payload: dict[str, Any] = Field(default_factory=dict)
    result: dict[str, Any] | None = None
    error: str | None = None
    priority: int = 0
    created_at: datetime | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None


class SiteOutcomeKind(StrEnum):
    """单站点抓取结果的类别 (summary.json / task report 共用同一结构)."""

    OK = "ok"
    FAILED = "failed"
    CACHE_HIT = "cache_hit"


class SiteOutcomeRecord(BaseModel):
    """单站点抓取结果 - 一手结构化事实, 由 Recorder.record_site_outcome 唯一写入."""

    site: str
    """cache_key (site 或 site:lang)."""
    outcome: SiteOutcomeKind
    reason: FailureReason | None = None
    """结构化失败原因; 成功 / 缓存命中为 None."""
    http_status: int | None = None
    """失败时的 HTTP 状态码 (reason=http_error 时必有)."""
    detail: str | None = None
    """人类可读补充 (错误原文等, 展示用, 不解析)."""


class TaskSummary(BaseModel):
    """任务结束摘要 - 只保留 task.json / http/ 无法直接表达的聚合信息.

    number / error / content_type 见 task.json; HTTP 原文见 http/.
    """

    eligible_sites: list[str] = Field(default_factory=list)
    """content_routes 下有资格的站点 (未必实际请求)."""
    sites_queried: list[str] = Field(default_factory=list)
    """实际调度并上报结果的 cache_key (顺序)."""
    outcomes: dict[str, SiteOutcomeRecord] = Field(default_factory=dict)
    """站点结果表 (key = cache_key); 唯一一手导出 record_site_outcome 写入."""
    failed_sites: list[str] | None = None
    """仅 RECORD_VERSION 1 记录写入; 新记录留空, 读取时用于降级投影."""
    cache_hits: list[str] | None = None
    """同上; 仅 RECORD_VERSION 1 记录写入."""


class HttpExchangeMeta(BaseModel):
    """单次出站请求元数据 (index.jsonl 一行)."""

    seq: int
    site: str | None = None
    method: str
    url: str
    status: int | None = None
    error: str | None = None
    content_type: str | None = None
    body_file: str | None = None
    elapsed_ms: int | None = None
