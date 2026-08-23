import re
from urllib.parse import urljoin

from parsel import Selector

from ...enums import SiteName
from ..base import Crawler, CrawlerProfile
from ..models import FetchOptions, MediaMetadata, SearchQuery
from ..parsing import extract_all_texts, extract_text


class AvsoxCrawler(Crawler):
    @classmethod
    def profile(cls) -> CrawlerProfile:
        return CrawlerProfile(name=SiteName.AVSOX, base_url="https://avsox.click")

    async def _search(self, query: SearchQuery, options: FetchOptions | None = None) -> str | None:
        number = query.number
        url = f"{self.base_url}/cn/search/{number}"
        text = await self.client.get_html(url)
        html = Selector(text=text)
        links = html.xpath('//div[@class="item"]//a/@href').getall()
        urls = [urljoin(self.base_url, href) for href in links][:5]
        return urls[0] if urls else None

    async def _scrape(self, url: str, options: FetchOptions | None = None) -> MediaMetadata | None:
        text = await self.client.get_html(url)
        html = Selector(text=text)

        title = extract_text(html, "//h3/text()")
        number = extract_text(html, '//span[@class="header"][contains(text(),"识别码")]/../span[2]/text()')
        if not number:
            return None

        actors = extract_all_texts(html, '//a[@class="avatar-box"]/span/text()')
        cover = extract_text(html, '//a[@class="bigImage"]/@href')
        tags = extract_all_texts(html, '//span[@class="genre"]/a[contains(@href,"genre")]/text()')
        release = extract_text(html, '//span[@class="header"][contains(text(),"发行时间")]/../text()')
        runtime_str = extract_text(html, '//span[@class="header"][contains(text(),"长度")]/../text()')
        runtime = self._parse_runtime(runtime_str)
        studio = extract_text(html, '//a[contains(@href,"studio")]/text()')

        return MediaMetadata(
            number=number,
            title=title or None,
            actors=actors,
            studio=studio or None,
            release=release or None,
            runtime=runtime,
            tags=tags,
            thumb_urls=[cover] if cover else [],
            source_url=url,
        )

    @staticmethod
    def _parse_runtime(text: str) -> int | None:
        if not text:
            return None
        match = re.search(r"(\d+)", text)
        return int(match.group(1)) if match else None
