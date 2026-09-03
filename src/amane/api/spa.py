import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import structlog
from starlette.responses import FileResponse, HTMLResponse, Response
from starlette.staticfiles import StaticFiles

if TYPE_CHECKING:
    from fastapi import FastAPI
    from starlette.types import ASGIApp, Receive, Scope, Send

logger = structlog.get_logger()


def _project_root() -> Path:
    """定位仓库根 (含 pyproject.toml 与 web/), 兼容 src 布局与冻结包."""
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            return Path(meipass)
        return Path(sys.executable).resolve().parent
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "pyproject.toml").is_file() and (parent / "web").is_dir():
            return parent
    return here.parents[3]


def _default_dist() -> Path:
    override = os.environ.get("AMANE_WEB_DIST")
    if override:
        return Path(override).expanduser().resolve()
    return _project_root() / "web" / "dist"


# 不应被 SPA 拦截的路径前缀
_RESERVED_PREFIXES = ("/api/", "/docs", "/redoc", "/openapi.json", "/assets")


class _SPAFallbackMiddleware:
    """未匹配 API 的 GET 回退到 index.html. 含 ``..`` 的路径返回 400."""

    def __init__(self, app: ASGIApp, dist_dir: Path) -> None:
        self._app = app
        self._dist = dist_dir
        self._index = dist_dir / "index.html"

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        path: str = scope.get("path", "/")

        # 保留路径直接透传
        if any(path.startswith(p) for p in _RESERVED_PREFIXES):
            await self._app(scope, receive, send)
            return

        # 禁止路径遍历
        if ".." in path:
            response: Response = HTMLResponse(status_code=400, content="Bad request")
            await response(scope, receive, send)
            return

        # 先尝试 dist 内的静态文件
        clean_path = path.lstrip("/")
        if clean_path:
            file_path = self._dist / clean_path
            if file_path.is_file():
                response = FileResponse(str(file_path))
                await response(scope, receive, send)
                return

        # 非 GET 则透传给上游
        method = scope.get("method", "GET")
        if method != "GET":
            await self._app(scope, receive, send)
            return

        # SPA 回退: 返回 index.html
        response = FileResponse(str(self._index))
        await response(scope, receive, send)


def mount_spa(app: FastAPI, dist_dir: Path | None = None) -> None:
    """dist 不存在则跳过 (开发时由 Vite 提供)."""
    dist = dist_dir or _default_dist()

    if not dist.exists():
        logger.info("spa dist not found, skipping mount", path=str(dist))
        return

    index_html = dist / "index.html"
    if not index_html.exists():
        logger.warning("index.html not found, spa not mounted", path=str(dist))
        return

    # 挂载 /assets (Vite 产物文件名带 hash, 可长期缓存)
    assets_dir = dist / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="spa-assets")

    # 在路由匹配之前拦截非 API 请求, 回退到 index.html
    app.add_middleware(_SPAFallbackMiddleware, dist_dir=dist)  # type: ignore[arg-type]

    logger.info("spa mounted", path=str(dist))
