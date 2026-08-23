"""资源图 HTTP 缓存头 - 就地超分后 URL 不变, 靠 content_hash ETag 协商失效.

``Cache-Control: public, no-cache``: 允许存本地, 但每次使用前必须带 ``If-None-Match`` 再验证;
未变 → 304, 超分改字节 → 200 新体. 不用固定 max-age (新鲜期内会跳过协商).
"""

from fastapi import Request, Response

# 可存本地, 但每次用前必须再验证 (带 If-None-Match).
RESOURCE_CACHE_HEADERS = {"Cache-Control": "public, no-cache"}


def format_etag(content_hash: str) -> str:
    """content_hash → 强 ETag 字面量 (带引号)."""
    return f'"{content_hash}"'


def etag_matches(if_none_match: str | None, content_hash: str) -> bool:
    """请求的 If-None-Match 是否命中当前 content_hash."""
    if not if_none_match or not content_hash:
        return False
    quoted = format_etag(content_hash)
    for part in if_none_match.split(","):
        candidate = part.strip()
        if candidate.startswith("W/"):
            candidate = candidate[2:].strip()
        if candidate == "*" or candidate == quoted:
            return True
    return False


def not_modified_response(content_hash: str) -> Response:
    """304 + 同一套 Cache-Control / ETag (无 body)."""
    return Response(status_code=304, headers={**RESOURCE_CACHE_HEADERS, "ETag": format_etag(content_hash)})


def maybe_not_modified(request: Request, content_hash: str | None) -> Response | None:
    """若 If-None-Match 命中则返回 304, 否则 None (调用方继续 200)."""
    if content_hash and etag_matches(request.headers.get("if-none-match"), content_hash):
        return not_modified_response(content_hash)
    return None
