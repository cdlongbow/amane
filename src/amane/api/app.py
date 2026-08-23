"""FastAPI 宿主入口 - create_app + lifespan 胶水.

进程编排在 ``amane.app.bootstrap``; 此处只把 ``AppSession.runtime`` 挂到 ``app.state``.
"""

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ..app.bootstrap import start_app
from ..version import get_version
from .middleware import LoggingMiddleware, TokenAuthMiddleware
from .routes import router
from .spa import mount_spa

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from fastapi.routing import APIRoute


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """挂接进程会话到 FastAPI ``app.state``, 退出时 ``aclose``."""
    session = await start_app()
    app.state.runtime = session.runtime
    try:
        yield
    finally:
        await session.aclose()


def generate_operation_id(route: APIRoute) -> str:
    """用路由函数名作为 operation ID, 避免 FastAPI 默认的冗长命名."""
    return route.name


def create_app() -> FastAPI:
    """创建带有生命周期管理的 FastAPI 应用"""
    app = FastAPI(
        title="Amane API",
        version=get_version(),
        docs_url="/docs",
        openapi_url="/openapi.json",
        lifespan=lifespan,
        generate_unique_id_function=generate_operation_id,
    )
    app.state.exit_code = 0
    app.state.server = None
    app.include_router(router)
    mount_spa(app)  # 必须在 API 路由之后, 以免 catch-all 覆盖 API
    app.add_middleware(LoggingMiddleware)
    app.add_middleware(TokenAuthMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    return app
