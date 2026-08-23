from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .base import Crawler


class CrawlerRegistry:
    """站点名 -> 爬虫类 的注册表; 注册键为 profile().name 的字符串形式."""

    def __init__(self):
        self._crawlers: dict[str, type[Crawler]] = {}

    def register(self, crawler_class: type[Crawler]) -> type[Crawler]:
        self._crawlers[str(crawler_class.profile().name)] = crawler_class
        return crawler_class

    def get(self, site: str) -> type[Crawler] | None:
        """按站点名返回注册的爬虫类; 未注册返回 None."""
        return self._crawlers.get(str(site))

    def sites(self):
        """返回所有已注册站点名的生成器."""
        return (str(cls.profile().name) for cls in self._crawlers.values())


registry = CrawlerRegistry()
