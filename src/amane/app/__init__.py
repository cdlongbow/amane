"""进程组合根 - AppRuntime, 装配函数与进程会话.

HTTP 层 (amane.api) 与 CLI/回放共用此处, 避免依赖 FastAPI 包.
"""

from .bootstrap import AppSession, build_safe_dirs, start_app
from .runtime import AppRuntime, NetworkStack, build_handlers, build_network_stack, build_r18_db

__all__ = [
    "AppRuntime",
    "AppSession",
    "NetworkStack",
    "build_handlers",
    "build_network_stack",
    "build_r18_db",
    "build_safe_dirs",
    "start_app",
]
