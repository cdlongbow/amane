"""资源 serve 端点 - 本地文件 + 外链反代.

按 url 的 hash 查 Resource 记录, 直接返回本地文件. 零业务逻辑 (无选源/裁剪/超分).
内部派生资源 (裁剪) 在 metadata 中以相对 URL `/api/resources/{url_hash}` 引用, 由本端点提供.

``GET /proxy`` 代理外链图片: 命中 ResourceStore 则直接返回, 否则 acquire 入库后再返回.

缓存策略: ``content_hash`` 作 ETag + ``Cache-Control: public, no-cache`` -
因 SR 可能就地覆盖 (URL 不变, 字节变), 浏览器每次使用前须再验证, 未变 304 / 已变 200.
"""

from typing import Annotated
from urllib.parse import urlparse

import structlog
from fastapi import APIRouter, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse

from ..deps import RuntimeDep
from ..support.http_cache import RESOURCE_CACHE_HEADERS, format_etag, maybe_not_modified

logger = structlog.get_logger()

router = APIRouter(prefix="/resources", tags=["resources"])

_EXT_TO_MIME = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".gif": "image/gif",
    ".avif": "image/avif",
    ".mp4": "video/mp4",
}


@router.get("/proxy")
async def proxy_image(
    runtime: RuntimeDep, request: Request, url: Annotated[str, Query(description="External image URL to proxy")]
) -> Response:
    """代理外链图片以绕过浏览器防盗链 / 严格 CORS.

    优先级:
    1. ResourceStore 命中 → 直接返回本地文件 (零网络开销)
    2. 未命中 → 通过 ResourceStore.acquire 下载并写入 store, 然后返回
       (后续请求自动走第 1 步)

    上游获取失败时记入进程内负缓存 (固定 15 分钟), 窗口内同 URL 直接 502,
    避免前端反复请求失效图时每次打满重试/超时. 同 URL 进行中请求合并为一次 acquire.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise HTTPException(status_code=400, detail="仅支持 http/https URL")

    failures = runtime.proxy_failure_cache
    if failures.is_blocked(url):
        raise HTTPException(status_code=502, detail="上游图片获取失败")

    store = runtime.resource_store
    local_path = await failures.coalesce(url, lambda: store.acquire(url, runtime.web_client))
    if local_path is None:
        failures.remember(url)
        logger.warning("proxy image acquire failed", url=url)
        raise HTTPException(status_code=502, detail="上游图片获取失败")

    failures.forget(url)

    record = await store.get_by_url(url)
    content_hash = record.content_hash if record is not None else None
    not_modified = maybe_not_modified(request, content_hash)
    if not_modified is not None:
        return not_modified

    headers = dict(RESOURCE_CACHE_HEADERS)
    if content_hash:
        headers["ETag"] = format_etag(content_hash)
    return FileResponse(
        path=local_path, media_type=_EXT_TO_MIME.get(local_path.suffix.lower(), "image/jpeg"), headers=headers
    )


@router.get("/{url_hash}")
async def serve_resource(url_hash: str, request: Request, runtime: RuntimeDep) -> Response:
    """按 url hash 返回本地资源文件 (哑文件服务)."""
    found = await runtime.resource_store.get_by_url_hash(url_hash)
    if found is None:
        raise HTTPException(status_code=404, detail="资源不存在")
    record, path = found

    not_modified = maybe_not_modified(request, record.content_hash)
    if not_modified is not None:
        return not_modified

    headers = dict(RESOURCE_CACHE_HEADERS)
    if record.content_hash:
        headers["ETag"] = format_etag(record.content_hash)
    media_type = record.mime_type or _EXT_TO_MIME.get(path.suffix.lower(), "application/octet-stream")
    return FileResponse(path=path, media_type=media_type, headers=headers)
