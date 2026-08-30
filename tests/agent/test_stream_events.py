"""SSE 事件与 truncate 表测试."""

from __future__ import annotations

import pytest
from pydantic_ai.messages import PartDeltaEvent, TextPartDelta
from pydantic_ai.usage import RunUsage

from amane.agent.events import StreamTextDelta, truncate_json, turn_usage_from_run
from amane.agent.service import _map_pai_event


@pytest.mark.parametrize(
    ("value", "max_chars", "ok"),
    [
        ("short", 100, True),
        ("x" * 50, 20, False),
        ({"a": 1}, 100, True),
        (None, 10, True),
        (123, 10, True),
    ],
)
def test_truncate_json(value: object, max_chars: int, ok: bool) -> None:
    out = truncate_json(value, max_chars=max_chars)
    if ok:
        assert out == value
    else:
        assert isinstance(out, str)
        assert out.startswith("x" * max_chars) or "…" in out


@pytest.mark.parametrize(
    ("run", "expected"),
    [
        (RunUsage(input_tokens=100, cache_read_tokens=40, cache_write_tokens=10, output_tokens=20), (50, 40, 10, 20)),
        (RunUsage(input_tokens=10, output_tokens=5), (10, 0, 0, 5)),
        (RunUsage(input_tokens=5, cache_read_tokens=10, output_tokens=1), (0, 10, 0, 1)),
    ],
)
def test_turn_usage_from_run(run: RunUsage, expected: tuple[int, int, int, int]) -> None:
    u = turn_usage_from_run(run)
    assert (u.input, u.cache_read, u.cache_write, u.output) == expected


def test_turn_usage_includes_requests() -> None:
    u = turn_usage_from_run(RunUsage(input_tokens=10, output_tokens=2, requests=3))
    assert u.requests == 3


def test_map_pai_event_skips_empty_and_unknown() -> None:
    assert _map_pai_event(PartDeltaEvent(index=0, delta=TextPartDelta(content_delta=""))) is None
    assert _map_pai_event(object()) is None
    assert isinstance(
        _map_pai_event(PartDeltaEvent(index=0, delta=TextPartDelta(content_delta="你好"))),
        StreamTextDelta,
    )
