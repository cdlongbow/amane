"""助理 Agent 包 - 会话式查询 / Saved Query / 写面 Capability."""

from .cache import CachedResult, ResultCache
from .events import (
    AgentStreamEvent,
    StreamCancelled,
    StreamDone,
    StreamError,
    StreamNeedsApproval,
    StreamTextDelta,
    StreamToolCall,
    StreamToolResult,
    TurnTokenUsage,
    turn_usage_from_run,
)
from .executor import QueryExecutor, extract_entity_ids
from .runtime import build_agent
from .service import AgentService, AgentTurnResult
from .sql import ReadonlySqlSandbox, SqlNeedsApproval, SqlResult, SqlSandboxError, SqlTimeoutError, as_id_subquery_sql
from .tools import NeedsApprovalPayload

__all__ = [
    "AgentService",
    "AgentStreamEvent",
    "AgentTurnResult",
    "CachedResult",
    "NeedsApprovalPayload",
    "QueryExecutor",
    "ReadonlySqlSandbox",
    "ResultCache",
    "SqlNeedsApproval",
    "SqlResult",
    "SqlSandboxError",
    "SqlTimeoutError",
    "StreamCancelled",
    "StreamDone",
    "StreamError",
    "StreamNeedsApproval",
    "StreamTextDelta",
    "StreamToolCall",
    "StreamToolResult",
    "TurnTokenUsage",
    "as_id_subquery_sql",
    "build_agent",
    "extract_entity_ids",
    "turn_usage_from_run",
]
