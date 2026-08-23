"""HTTP 服务入口. 按 app.state.exit_code 退出.

Desktop 壳、Docker CMD、``just start`` 共用.
"""

from __future__ import annotations

import os
import sys

import uvicorn

from amane.api.app import create_app

EXIT_OK = 0
EXIT_RESTART = 3


def run_server(*, host: str, port: int, log_level: str = "info") -> int:
    """阻塞运行直到停机, 返回退出码 (0 正常停 / 3 请求重启)."""
    app = create_app()
    app.state.exit_code = EXIT_OK
    server = uvicorn.Server(
        uvicorn.Config(
            app,
            host=host,
            port=port,
            log_level=log_level,
            timeout_graceful_shutdown=5,
        )
    )
    app.state.server = server
    server.run()
    code: int = app.state.exit_code
    return code


def main() -> None:
    if getattr(sys, "frozen", False):
        os.environ.setdefault("PYDANTIC_DISABLE_PLUGINS", "1")
    host = os.environ.get("AMANE_HOST", "0.0.0.0")
    port = int(os.environ.get("AMANE_PORT", "8000"))
    sys.exit(run_server(host=host, port=port))


if __name__ == "__main__":
    main()
