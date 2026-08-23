"""
独立的 HTML 解析工具函数.

纯函数 - 无类继承, 无状态.
供爬虫从 parsel Selector 中提取数据使用.
"""

import re
from re import Pattern
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from parsel import Selector


class CSSSelector(str):
    """CSS 选择器的标记类型 (区别于 XPath 字符串)."""

    __slots__ = ()


type SelectorType = CSSSelector | Pattern | str


def clean_string(text: str | None) -> str:
    """去除空白, 移除换行, 替换 &nbsp;."""
    if not text:
        return ""
    return text.strip().replace("\n", "").replace("\r", "").replace("&nbsp;", " ")


def extract_text(html: Selector, *selectors: SelectorType) -> str:
    """
    使用第一个匹配的选择器提取单个文本值.

    按顺序尝试每个选择器. 返回清理后的文本或空字符串.
    字符串视为 XPath, CSSSelector 实例视为 CSS, Pattern 视为正则表达式.
    """
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
    """
    使用第一个匹配的选择器提取所有文本值.

    按顺序尝试每个选择器直到某个产生结果.
    返回清理后的字符串列表 (过滤掉空项).
    """
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
