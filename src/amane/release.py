"""GitHub Releases 版本检查. 进程内 ETag + 1h 缓存; 失败不抛, 由调用方展示."""

from __future__ import annotations

import time

import httpx2 as httpx
from packaging.version import InvalidVersion, Version

from .version import get_version

GITHUB_LATEST_URL = "https://api.github.com/repos/sqzw-x/amane/releases/latest"
GITHUB_RELEASES_PAGE = "https://github.com/sqzw-x/amane/releases"
_CACHE_TTL_S = 3600.0
_TIMEOUT_S = 10.0


def _user_agent() -> str:
    return f"Amane/{get_version()} (+https://github.com/sqzw-x/amane)"


def _strip_v(tag: str) -> str:
    return tag[1:] if tag[:1] in "vV" else tag


def is_newer(latest: str, current: str) -> bool:
    """比较 GitHub tag 与包版本; 无法解析时退回字符串不等."""
    left, right = _strip_v(latest), _strip_v(current)
    try:
        return Version(left) > Version(right)
    except InvalidVersion:
        return left != right


class ReleaseSnapshot:
    __slots__ = ("html_url", "latest")

    def __init__(self, latest: str | None, html_url: str | None) -> None:
        self.latest = latest
        self.html_url = html_url


class ReleaseChecker:
    """带 ETag 的 latest 查询. 由 AppRuntime 持有, 不参与 rebuild."""

    def __init__(self) -> None:
        self._etag: str | None = None
        self._snapshot = ReleaseSnapshot(None, None)
        self._cached_at: float = 0.0

    async def fetch(self, *, proxy: str | None = None, url: str | None = None) -> ReleaseSnapshot:
        now = time.monotonic()
        if self._snapshot.latest is not None and now - self._cached_at < _CACHE_TTL_S:
            return self._snapshot
        target = url.strip() if url else GITHUB_LATEST_URL
        headers = {"User-Agent": _user_agent(), "Accept": "application/vnd.github+json"}
        if self._etag is not None:
            headers["If-None-Match"] = self._etag
        try:
            async with httpx.AsyncClient(proxy=proxy, timeout=_TIMEOUT_S) as client:
                resp = await client.get(target, headers=headers)
        except httpx.HTTPError:
            return self._stale_or_empty()
        if resp.status_code == 304:
            self._cached_at = now
            return self._snapshot
        if resp.status_code != 200:
            return self._stale_or_empty()
        try:
            body = resp.json()
        except ValueError:
            return self._stale_or_empty()
        tag = body.get("tag_name")
        html_url = body.get("html_url")
        if not isinstance(tag, str) or not tag:
            return self._stale_or_empty()
        url = html_url if isinstance(html_url, str) and html_url else GITHUB_RELEASES_PAGE
        etag = resp.headers.get("etag")
        self._etag = etag if isinstance(etag, str) else None
        self._snapshot = ReleaseSnapshot(tag, url)
        self._cached_at = now
        return self._snapshot

    def _stale_or_empty(self) -> ReleaseSnapshot:
        if self._snapshot.latest is not None:
            return self._snapshot
        return ReleaseSnapshot(None, None)
