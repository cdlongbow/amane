"""API token 解析: 生成 / 持久化 / 配置语义.

- ``AMANE_TOKEN`` 未设置 (auto): 生成随机 token 并持久化到 ``data_dir/token``
  (0600), 后续启动复用. 所有 ``/api/*`` 请求 (health 除外) 需携带
  ``Authorization: Bearer <token>`` (或认证成功后下发的 HttpOnly cookie,
  见 ``api/middleware.py``).
- ``AMANE_TOKEN=off``: 显式关闭校验 — 容器/反代场景, 反代负责安全.
- ``AMANE_TOKEN=<value>``: 使用显式 token.

函数幂等: 文件已存在时直接读取, 不会覆盖. 桌面菜单栏在 bootstrap 写入后再读同一文件.
"""

from __future__ import annotations

import secrets
from pathlib import Path

_TOKEN_FILE = "token"


def resolve_api_token(token_env: str | None, data_dir: Path) -> str | None:
    """按配置语义解析 API token; 关闭时返回 ``None``."""
    if token_env == "off":
        return None
    if token_env:
        return token_env

    token_path = data_dir / _TOKEN_FILE
    if token_path.is_file():
        value = token_path.read_text(encoding="utf-8").strip()
        return value or None

    token = secrets.token_urlsafe(32)
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(token, encoding="utf-8")
    token_path.chmod(0o600)
    return token
