"""R18_IMPORT 任务 handler - 下载并导入 r18.dev dump.

定时任务 (RoutineType.R18_IMPORT) 或手动触发. 重活 (下载 GB 级 dump + psql 导入), 走 worker
而非 cron 循环内联. 已导入版本的 ETag 持久化到 data_dir/r18_import.json, 远程未变化时跳过.

dsn 未配置时直接返回失败 (success=False), 不抛错.
"""

import json
from pathlib import Path
from typing import TYPE_CHECKING

import structlog

from ..crawlers.r18dev import R18Importer, RemoteMeta
from .models import R18ImportPayload, R18ImportResult
from .protocol import TaskHandler, TaskResult

if TYPE_CHECKING:
    from ..config import R18Config
    from ..net.http import WebClient

logger = structlog.get_logger()


class R18ImportHandler(TaskHandler[R18ImportPayload, R18ImportResult]):
    """处理 R18_IMPORT 任务 - 编排 dump 下载与导入."""

    def __init__(self, config: R18Config, web_client: WebClient, state_dir: Path):
        super().__init__(payload_t=R18ImportPayload, result_t=R18ImportResult)
        self._config = config
        self._web = web_client
        self._state_path = state_dir / "r18_import.json"

    def _load_meta(self) -> RemoteMeta | None:
        """读取上次成功导入的 dump 元数据."""
        if not self._state_path.exists():
            return None
        try:
            data = json.loads(self._state_path.read_text(encoding="utf-8"))
            return RemoteMeta(**data)
        except ValueError, TypeError, OSError:
            return None

    def _save_meta(self, meta: RemoteMeta) -> None:
        """将已导入的 dump 元数据持久化到状态文件."""
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        self._state_path.write_text(json.dumps(meta._asdict()), encoding="utf-8")

    async def handle(self, payload: R18ImportPayload) -> TaskResult[R18ImportResult]:
        if not self._config.enabled:
            return TaskResult(success=False, error="r18.dsn 未配置, 无法导入")

        current = None if payload.force else self._load_meta()
        importer = R18Importer(self._config, self._web)
        success, error, meta = await importer.run(current_meta=current)

        if not success:
            return TaskResult(success=False, error=error)

        # meta is None 仅当无 download_url 且默认导入; 有 meta 才更新状态.
        imported = not (current is not None and meta is not None and meta.same_as(current))
        if meta is not None and imported:
            self._save_meta(meta)

        return TaskResult(success=True, result=R18ImportResult(imported=imported, etag=meta.etag if meta else None))
