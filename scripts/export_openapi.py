#!/usr/bin/env python3
"""从 FastAPI 应用导出 OpenAPI schema, 供前端 SDK 生成 (无需启动服务器).

用法: uv run python scripts/export_openapi.py
输出: web/openapi.json
"""

from __future__ import annotations

import json
from pathlib import Path

from amane.api.app import create_app


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    out = root / "web" / "openapi.json"
    app = create_app()
    out.write_text(json.dumps(app.openapi(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
