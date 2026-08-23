"""取消回合: 历史拼接与无 fixture 依赖的纯函数表测试."""

from __future__ import annotations

import pytest
from pydantic_ai.messages import TextPart

from amane.agent.service import _messages_for_cancelled


@pytest.mark.parametrize(
    ("reply", "expected"),
    [
        ("部分回复", "部分回复"),
        ("", "（已终止）"),
    ],
)
def test_messages_for_cancelled(reply: str, expected: str) -> None:
    msgs = _messages_for_cancelled([], "你好", reply)
    assert len(msgs) == 2
    part = msgs[1].parts[0]
    assert isinstance(part, TextPart)
    assert part.content == expected
