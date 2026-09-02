from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Protocol

import structlog

from .models import ActorMetadata

if TYPE_CHECKING:
    from ...config import SiteConfig
    from ...enums import SiteName
    from ..base import CrawlerProfile
    from ..http import HttpClient


class ActorFetcher(Protocol):
    """按名抓取演员元数据 - Handler / Factory 共用契约."""

    async def fetch(self, name: str) -> ActorMetadata | None: ...


class ActorCrawler(ABC):
    """
    演员爬虫基类.

    公开接口: fetch(name) -> ActorMetadata | None
    默认 Template Method: _search(name) -> URL | None, _scrape(url) -> ActorMetadata | None
    纯头像源可 override fetch() 直接查索引.
    """

    @classmethod
    @abstractmethod
    def profile(cls) -> CrawlerProfile: ...

    def __init__(self, client: HttpClient, config: SiteConfig | None = None):
        self._profile = self.profile()
        self.name: SiteName | str = self._profile.name
        self.client = client
        self.config = config
        self.base_url = self._profile.base_url
        self.cookies = dict(self._profile.cookies)
        self.headers = dict(self._profile.headers)
        self._resolve_config()

    def _resolve_config(self) -> None:
        """合并 CrawlerProfile 与 SiteConfig."""
        if self.config is None:
            return
        if self.config.base_url:
            self.base_url = self.config.base_url.rstrip("/")
        for k, v in self.config.cookie.items():
            self.cookies[k] = v

    @property
    def logger(self) -> structlog.stdlib.BoundLogger:
        try:
            return self._logger
        except AttributeError:
            self._logger = structlog.get_logger(f"amane.crawlers.actor.{self.name}")
            return self._logger

    async def fetch(self, name: str) -> ActorMetadata | None:
        """按演员名抓取; 未命中返回 None. HTTP / 拦截失败冒泡 SourceError."""
        url = await self._search(name)
        if not url:
            return None
        return await self._scrape(url)

    async def _search(self, name: str) -> str | None:
        """名 → 详情 URL. 子类实现; 纯索引源可不用."""
        raise NotImplementedError

    async def _scrape(self, url: str) -> ActorMetadata | None:
        """详情 URL → ActorMetadata. 子类实现."""
        raise NotImplementedError
