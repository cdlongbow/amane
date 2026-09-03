"""按 updated_at 选取 Metadata 并扇出 SCRAPE. content_type 不存表, 运行时按路径或番号推断.
Metadata 是判定依据, 不依赖挂载文件是否存在.
"""

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from ..db import TaskType
from ..db.models import MetadataSortField, SortOrder
from ..parsing import infer_content_type
from .models import CacheKind, RescrapePayload, RescrapeResult, ScrapePayload
from .protocol import FollowupTask, TaskHandler, TaskResult

if TYPE_CHECKING:
    from ..db.repository import Repository


class RescrapeHandler(TaskHandler[RescrapePayload, RescrapeResult]):
    def __init__(self, repo: Repository) -> None:
        super().__init__(payload_t=RescrapePayload, result_t=RescrapeResult)
        self._repo = repo

    async def handle(self, payload: RescrapePayload) -> TaskResult[RescrapeResult]:
        # 按 updated_at 取最久未更新的 Metadata.
        updated_before = (
            datetime.now(UTC) - timedelta(days=payload.min_age_days) if payload.min_age_days is not None else None
        )
        items, _ = await self._repo.list_metadata(
            sort_by=MetadataSortField.UPDATED_AT,
            order=SortOrder.ASC,
            limit=payload.limit,
            updated_before=updated_before,
        )
        if not items:
            return TaskResult(success=True, result=RescrapeResult(submitted=0))

        identified = [(m, m.id) for m in items if m.id is not None]
        # 挂载文件仅用于 content_type 推断: 每个 metadata 取第一个文件即可 (同号文件类型一致).
        files = await self._repo.list_media_files(metadata_ids=[mid for _, mid in identified], limit=None)
        first_path_by_metadata: dict[int, str] = {}
        for f in files:
            if f.metadata_id is not None and f.metadata_id not in first_path_by_metadata:
                first_path_by_metadata[f.metadata_id] = f.path

        # 扇出低优先 SCRAPE.
        followups = []
        for meta, meta_id in identified:
            followups.append(
                FollowupTask(
                    key=f"scrape:{meta_id}",
                    task_type=TaskType.SCRAPE,
                    payload=ScrapePayload(
                        number=meta.number,
                        content_type=infer_content_type(meta.number, first_path_by_metadata.get(meta_id)),
                        use_cache={CacheKind.metadata, CacheKind.trans},
                    ).model_dump(mode="json"),
                    priority=-1,
                )
            )

        return TaskResult(success=True, result=RescrapeResult(submitted=len(identified)), followups=followups)
