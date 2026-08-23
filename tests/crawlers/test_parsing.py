"""测试独立的 HTML 解析工具函数"""

from parsel import Selector

from amane.crawlers.parsing import CSSSelector, clean_string, extract_all_texts, extract_text

SAMPLE_HTML = """
<html>
<body>
  <h1 class="title">  Hello World  </h1>
  <div class="info">
    <span class="label">Studio:</span>
    <span class="value"><a href="/s/1">Studio A</a></span>
  </div>
  <div class="tags">
    <a href="/t/1">Tag 1</a>
    <a href="/t/2">Tag 2</a>
    <a href="/t/3">Tag 3</a>
  </div>
  <div class="empty"></div>
</body>
</html>
"""


class TestCleanString:
    def test_strips_whitespace(self):
        assert clean_string("  hello  ") == "hello"

    def test_removes_newlines(self):
        assert clean_string("hello\nworld\r") == "helloworld"

    def test_replaces_nbsp(self):
        assert clean_string("hello&nbsp;world") == "hello world"

    def test_none_returns_empty(self):
        assert clean_string(None) == ""

    def test_empty_returns_empty(self):
        assert clean_string("") == ""


class TestExtractText:
    def test_xpath(self):
        sel = Selector(text=SAMPLE_HTML)
        result = extract_text(sel, "//h1[@class='title']/text()")
        assert result == "Hello World"

    def test_css(self):
        sel = Selector(text=SAMPLE_HTML)
        result = extract_text(sel, CSSSelector("h1.title::text"))
        assert result == "Hello World"

    def test_fallback_to_second_selector(self):
        sel = Selector(text=SAMPLE_HTML)
        result = extract_text(sel, "//h1[@class='nonexistent']/text()", "//h1[@class='title']/text()")
        assert result == "Hello World"

    def test_no_match_returns_empty(self):
        sel = Selector(text=SAMPLE_HTML)
        result = extract_text(sel, "//h1[@class='nonexistent']/text()")
        assert result == ""


class TestExtractAllTexts:
    def test_extracts_list(self):
        sel = Selector(text=SAMPLE_HTML)
        result = extract_all_texts(sel, "//div[@class='tags']/a/text()")
        assert result == ["Tag 1", "Tag 2", "Tag 3"]

    def test_no_match_returns_empty_list(self):
        sel = Selector(text=SAMPLE_HTML)
        result = extract_all_texts(sel, "//div[@class='nothing']/a/text()")
        assert result == []
