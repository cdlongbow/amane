"""从 parsel Selector 提取文本. 字符串视为 XPath, ``CSSSelector`` 视为 CSS, ``Pattern`` 视为正则."""

import re
from re import Pattern
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from parsel import Selector


class CSSSelector(str):
    __slots__ = ()


type SelectorType = CSSSelector | Pattern | str


def clean_string(text: str | None) -> str:
    if not text:
        return ""
    return text.strip().replace("\n", "").replace("\r", "").replace("&nbsp;", " ")


def extract_text(html: Selector, *selectors: SelectorType) -> str:
    for s in selectors:
        try:
            if isinstance(s, re.Pattern):
                result = html.re(s)
                result = result[0] if result else ""
            elif isinstance(s, CSSSelector):
                result = html.css(s).get()
            else:
                result = html.xpath(s).get()
            if result:
                return clean_string(result)
        except AttributeError, TypeError, IndexError:
            continue
    return ""


def extract_all_texts(html: Selector, *selectors: SelectorType) -> list[str]:
    for s in selectors:
        try:
            if isinstance(s, re.Pattern):
                results = html.re(s)
            elif isinstance(s, CSSSelector):
                results = html.css(s).getall()
            else:
                results = html.xpath(s).getall()
            if results:
                return [clean_string(r) for r in results if clean_string(r)]
        except AttributeError, TypeError, IndexError:
            continue
    return []
