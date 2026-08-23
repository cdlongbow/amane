"""测试 amane.crawlers.http - HttpClient 薄封装"""

from pathlib import Path
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
@pytest.mark.parametrize(
    "url,headers,encoding",
    [
        ("https://example.com/page", None, "utf-8"),
        ("https://example.com/api", {"Cookie": "session=abc"}, "utf-8"),
        ("https://example.com/jp", None, "shift_jis"),
    ],
)
async def test_get_text_passes_params(client, mock_web, url, headers, encoding):
    mock_web.get_text.return_value = "response"
    result = await client.get_text(url, headers=headers, encoding=encoding)
    assert result == "response"
    mock_web.get_text.assert_called_once_with(url, headers=headers, cookies=None, encoding=encoding)


@pytest.mark.asyncio
async def test_get_text_failure_raises(client, mock_web):
    mock_web.get_text.side_effect = RequestError("https://example.com/missing", "HTTP 404")
    with pytest.raises(RequestError, match="HTTP 404"):
        await client.get_text("https://example.com/missing")


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
async def test_get_json_success(client, mock_web):
    mock_web.get_json.return_value = {"results": [1, 2, 3]}
    result = await client.get_json("https://api.example.com/data")
    assert result == {"results": [1, 2, 3]}
    mock_web.get_json.assert_called_once_with("https://api.example.com/data", headers=None, cookies=None)


@pytest.mark.asyncio
async def test_get_json_with_headers(client, mock_web):
    mock_web.get_json.return_value = {"token": "abc"}
    headers = {"Authorization": "Bearer xyz"}
    result = await client.get_json("https://api.example.com/auth", headers=headers)
    assert result == {"token": "abc"}
    mock_web.get_json.assert_called_once_with("https://api.example.com/auth", headers=headers, cookies=None)


@pytest.mark.asyncio
async def test_get_json_failure_raises(client, mock_web):
    mock_web.get_json.side_effect = RequestError("https://api.example.com/data", "HTTP 403")
    with pytest.raises(RequestError, match="HTTP 403"):
        await client.get_json("https://api.example.com/data")


@pytest.mark.asyncio
async def test_get_bytes_success(client, mock_web):
    mock_web.get_bytes.return_value = b"\x89PNG"
    assert await client.get_bytes("https://example.com/img.png") == b"\x89PNG"


@pytest.mark.asyncio
async def test_get_bytes_failure_raises(client, mock_web):
    mock_web.get_bytes.side_effect = RequestError("https://example.com/img.png", "timeout")
    with pytest.raises(RequestError):
        await client.get_bytes("https://example.com/img.png")


@pytest.mark.asyncio
async def test_get_rendered_success(client, mock_browser):
    mock_browser.get_page.return_value = ("<html>JS</html>", "")
    assert await client.get_rendered("https://example.com/spa") == "<html>JS</html>"


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


@pytest.mark.asyncio
@pytest.mark.parametrize("return_val", [True, False])
async def test_download(client, mock_web, return_val):
    mock_web.download.return_value = return_val
    assert await client.download("https://example.com/f.zip", Path("/tmp/f.zip")) == return_val


@pytest.mark.asyncio
async def test_post_json_success(client, mock_web):
    mock_web.post_json.return_value = {"data": {"id": 1}}
    result = await client.post_json("https://api.example.com/graphql", json={"query": "..."})
    assert result == {"data": {"id": 1}}
    mock_web.post_json.assert_called_once_with("https://api.example.com/graphql", json={"query": "..."}, headers=None)


@pytest.mark.asyncio
async def test_post_json_failure_raises(client, mock_web):
    mock_web.post_json.side_effect = RequestError("https://api.example.com/graphql", "HTTP 500")
    with pytest.raises(RequestError, match="HTTP 500"):
        await client.post_json("https://api.example.com/graphql", json={"query": "..."})
