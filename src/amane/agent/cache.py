"""交付结果内存缓存 - 按 saved_query_id, LRU + TTL."""

from __future__ import annotations

import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class CachedResult:
    """物化的查询结果 - 缓存对列内容无感, 只存行列数组."""

    saved_query_id: int
    columns: list[str]
    rows: list[list[Any]]
    created_at: float = field(default_factory=time.monotonic)

    @property
    def row_count(self) -> int:
        return len(self.rows)


class ResultCache:
    """进程内结果缓存; 调整容量不丢弃现有未过期条目."""

    def __init__(self, *, ttl_s: int = 3600, max_entries: int = 64) -> None:
        self._ttl_s = ttl_s
        self._max_entries = max_entries
        self._entries: OrderedDict[int, CachedResult] = OrderedDict()

    def configure(self, *, ttl_s: int, max_entries: int) -> None:
        """热更新容量参数 (不丢现有未过期条目, 但立刻按新上限裁剪)."""
        self._ttl_s = ttl_s
        self._max_entries = max_entries
        self._evict()

    def get(self, saved_query_id: int) -> CachedResult | None:
        """按 saved_query_id 返回缓存; 未命中或已过期返回 None."""
        entry = self._entries.get(saved_query_id)
        if entry is None:
            return None
        if time.monotonic() - entry.created_at > self._ttl_s:
            del self._entries[saved_query_id]
            return None
        self._entries.move_to_end(saved_query_id)
        return entry

    def put(self, entry: CachedResult) -> None:
        self._entries[entry.saved_query_id] = entry
        self._entries.move_to_end(entry.saved_query_id)
        self._evict()

    def invalidate(self, saved_query_id: int) -> None:
        self._entries.pop(saved_query_id, None)

    def clear(self) -> None:
        self._entries.clear()

    def _evict(self) -> None:
        now = time.monotonic()
        expired = [k for k, v in self._entries.items() if now - v.created_at > self._ttl_s]
        for k in expired:
            del self._entries[k]
        while len(self._entries) > self._max_entries:
            self._entries.popitem(last=False)
