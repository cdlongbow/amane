"""把模型打出的命名空间工具名改写成当前可执行名.

只在 ``after_model_request`` 改 ``ModelResponse`` (即执行与落入 history 的名字).
流式 SSE 仍可能带模型原始名.
"""

from __future__ import annotations

from collections.abc import Set as AbstractSet
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from pydantic_ai.capabilities import AbstractCapability
from pydantic_ai.messages import ModelResponse, ModelResponsePart, ToolCallPart
from pydantic_ai.tools import RunContext

from .tools import AgentDeps

if TYPE_CHECKING:
    from pydantic_ai.models import ModelRequestContext


def canonical_tool_name(name: str, available: AbstractSet[str]) -> str:
    """未知名若 ``__`` 后缀恰好是当前可调用工具, 则用该后缀; 否则原样返回."""
    if name in available:
        return name
    if "__" not in name:
        return name
    suffix = name.rsplit("__", 1)[-1]
    if suffix and suffix in available:
        return suffix
    return name


def alias_response_tool_names(response: ModelResponse, available: AbstractSet[str]) -> ModelResponse:
    """改写响应里不可调用、但后缀可调用的 ``ToolCallPart.tool_name``."""
    changed = False
    parts: list[ModelResponsePart] = []
    for part in response.parts:
        if isinstance(part, ToolCallPart):
            canonical = canonical_tool_name(part.tool_name, available)
            if canonical != part.tool_name:
                parts.append(replace(part, tool_name=canonical))
                changed = True
                continue
        parts.append(part)
    if not changed:
        return response
    return replace(response, parts=parts)


@dataclass
class ToolNameAlias(AbstractCapability[AgentDeps]):
    """始终在场: 执行前把 ``name__name`` 裁成当前可调用工具名."""

    async def after_model_request(
        self,
        ctx: RunContext[AgentDeps],
        *,
        request_context: ModelRequestContext,
        response: ModelResponse,
    ) -> ModelResponse:
        del request_context
        return alias_response_tool_names(response, ctx.available_tool_names)
