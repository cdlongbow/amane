"""HttpClient: HTML 拦截启发式与浏览器失败路径 (透传方法不单测)."""

from unittest.mock import AsyncMock

import pytest

from amane.crawlers.http import HttpClient
from amane.net.errors import FailureReason, RequestError, SourceError


@pytest.fixture
def mock_web():
    return AsyncMock()


@pytest.fixture
def mock_browser():
    return AsyncMock()


@pytest.fixture
def client(mock_web, mock_browser):
    return HttpClient(web=mock_web, browser=mock_browser)


@pytest.mark.asyncio
async def test_get_html_passes_through_normal_page(client, mock_web):
    mock_web.get_text.return_value = "<html><body>Normal Page</body></html>"
    assert await client.get_html("https://example.com/") == "<html><body>Normal Page</body></html>"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("html", "reason"),
    [
        ("", FailureReason.EMPTY_RESPONSE),
        ("just a moment... cloudflare challenge", FailureReason.CLOUDFLARE_CHALLENGE),
        ("This content is not available in your region", FailureReason.GEO_RESTRICTED),
    ],
)
async def test_get_html_raises_source_error_on_block(client, mock_web, html: str, reason: FailureReason):
    mock_web.get_text.return_value = html
    with pytest.raises(SourceError) as exc:
        await client.get_html("https://example.com/")
    assert exc.value.reason == reason


@pytest.mark.asyncio
async def test_get_rendered_failure_raises(client, mock_browser):
    mock_browser.get_page.return_value = (None, "timeout")
    with pytest.raises(RequestError, match="timeout"):
        await client.get_rendered("https://example.com/spa")


@pytest.mark.asyncio
async def test_get_rendered_no_browser_raises(mock_web):
    client = HttpClient(web=mock_web, browser=None)
    with pytest.raises(RequestError, match="BrowserClient not configured"):
        await client.get_rendered("https://example.com/spa")
