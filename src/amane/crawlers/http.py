"""爬虫 HTTP 封装. ``get_html`` / ``get_rendered`` 命中拦截页抛 ``SourceError``."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

    from ..net.http import BrowserClient, WebClient

from ..net.errors import RequestError, SourceError, classify_block


class HttpClient:
    """构造函数注入 WebClient / BrowserClient. ``get_json`` 不做 HTML 拦截启发式."""

    def __init__(self, web: WebClient, browser: BrowserClient | None = None):
        self._web = web
        self._browser = browser

    @property
    def web_client(self) -> WebClient:
        """Shared low-level client exposed to trusted source plugins."""
        return self._web

    async def get_text(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        cookies: dict[str, str] | None = None,
        encoding: str = "utf-8",
    ) -> str:
        return await self._web.get_text(url, headers=headers, cookies=cookies, encoding=encoding)

    async def get_html(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        cookies: dict[str, str] | None = None,
        encoding: str = "utf-8",
    ) -> str:
        text = await self.get_text(url, headers=headers, cookies=cookies, encoding=encoding)
        reason = classify_block(text)
        if reason is not None:
            raise SourceError(reason, detail=url)
        return text

    async def get_json(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        cookies: dict[str, str] | None = None,
    ) -> Any:
        return await self._web.get_json(url, headers=headers, cookies=cookies)

    async def get_bytes(self, url: str, *, headers: dict[str, str] | None = None) -> bytes:
        return await self._web.get_bytes(url, headers=headers)

    async def post_json(
        self,
        url: str,
        *,
        json: Any,
        headers: dict[str, str] | None = None,
    ) -> Any:
        return await self._web.post_json(url, json=json, headers=headers)

    async def get_rendered(
        self,
        url: str,
        *,
        wait_for: str | None = None,
        timeout: float = 30000,
    ) -> str:
        # 未配置浏览器或抓取失败抛 RequestError; 拦截页抛 SourceError.
        if self._browser is None:
            raise RequestError(url, "BrowserClient not configured")
        html, err = await self._browser.get_page(url, wait_for=wait_for, timeout=timeout)
        if html is None:
            raise RequestError(url, err)
        reason = classify_block(html)
        if reason is not None:
            raise SourceError(reason, detail=url)
        return html

    async def download(self, url: str, dest: Path) -> bool:
        # 失败返回 False, 不抛异常.
        return await self._web.download(url, dest)
