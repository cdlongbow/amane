"""Agent SSE 事件契约 - 前后端共用形状."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field
from pydantic_ai.usage import RunUsage

from ..db.models import AgentSessionStatus, SavedQueryEntity


class TurnTokenUsage(BaseModel):
    """一轮对话的计费向用量.

    `input` 是**非缓存**输入 (总 input 减去 cache_read/cache_write), 便于估费率.
    pydantic-ai 的 `input_tokens` 是包含缓存的总量, 这里刻意拆开.
    """

    input: int = 0
    cache_read: int = 0
    cache_write: int = 0
    output: int = 0
    requests: int = 0


class StreamTextDelta(BaseModel):
    type: Literal["text_delta"] = "text_delta"
    text: str


class StreamToolCall(BaseModel):
    type: Literal["tool_call"] = "tool_call"
    tool_call_id: str
    name: str
    args: Any = None


class StreamToolResult(BaseModel):
    type: Literal["tool_result"] = "tool_result"
    tool_call_id: str
    name: str
    result: Any = None


class StreamNeedsApproval(BaseModel):
    type: Literal["needs_approval"] = "needs_approval"
    approval_id: str
    sql: str
    tool: str
    entity: SavedQueryEntity | None = None
    name: str | None = None
    reason: str = "allow_slow"


class StreamDone(BaseModel):
    type: Literal["done"] = "done"
    saved_query_ids: list[int] = Field(default_factory=list)
    status: AgentSessionStatus = AgentSessionStatus.ACTIVE
    usage: TurnTokenUsage = Field(default_factory=TurnTokenUsage)


class StreamError(BaseModel):
    type: Literal["error"] = "error"
    message: str


class StreamCancelled(BaseModel):
    """用户显式终止回合; 与断连无关."""

    type: Literal["cancelled"] = "cancelled"


AgentStreamEvent = (
    StreamTextDelta
    | StreamToolCall
    | StreamToolResult
    | StreamNeedsApproval
    | StreamDone
    | StreamError
    | StreamCancelled
)


def turn_usage_from_run(usage: RunUsage) -> TurnTokenUsage:
    """从 pydantic-ai RunUsage 抽出计费向用量."""
    cache_read = usage.cache_read_tokens
    cache_write = usage.cache_write_tokens
    return TurnTokenUsage(
        input=max(0, usage.input_tokens - cache_read - cache_write),
        cache_read=cache_read,
        cache_write=cache_write,
        output=usage.output_tokens,
        requests=usage.requests,
    )


def truncate_json(value: Any, *, max_chars: int = 4000) -> Any:
    """把工具结果压到可展示大小; 超长变摘要字符串."""
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        if len(value) <= max_chars:
            return value
        return value[:max_chars] + f"…(+{len(value) - max_chars} chars)"
    try:
        import json

        text = json.dumps(value, ensure_ascii=False, default=str)
    except TypeError:
        text = str(value)
    if len(text) <= max_chars:
        return value
    return text[:max_chars] + f"…(+{len(text) - max_chars} chars)"
