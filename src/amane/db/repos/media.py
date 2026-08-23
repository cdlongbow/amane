from collections.abc import Iterable, Sequence
from typing import Unpack

from sqlalchemy import func, or_
from sqlalchemy.sql.functions import count
from sqlmodel import col, select

from ..models import MediaFile, MediaFileStatus, MediaSortField, SortOrder
from ..repo_types import _MEDIA_SORT_COLUMNS, MediaFileUpdates, _order_clause, _utcnow
from .base import RepositoryMixinBase


class MediaRepoMixin(RepositoryMixinBase):
    async def create_media_file(self, library_id: int, **updates: Unpack[MediaFileUpdates]) -> MediaFile:
        async with self._session() as session:
            media = MediaFile(library_id=library_id, **updates)
            session.add(media)
            await session.commit()
            await session.refresh(media)
            return media

    async def get_media_file(self, media_id: int) -> MediaFile | None:
        async with self._session() as session:
            return await session.get(MediaFile, media_id)

    async def get_media_file_by_path(self, path: str) -> MediaFile | None:
        async with self._session() as session:
            stmt = select(MediaFile).where(MediaFile.path == path)
            result = await session.exec(stmt)
            return result.first()

    async def get_valid(self, disk_paths: Iterable[str]) -> Sequence[MediaFile]:
        """获取 disk_paths 与数据库现有条目的交集."""
        if not disk_paths:
            return []
        async with self._session() as session:
            stmt = select(MediaFile).where(col(MediaFile.path).in_(disk_paths))
            result = await session.exec(stmt)
            return result.all()

    async def get_invalid(self, disk_paths: Iterable[str], library_id: int | None = None) -> Sequence[MediaFile]:
        """获取数据库中路径不在 disk_paths 的条目. library_id 收窄到单库, 避免扫 A 误删 B."""
        async with self._session() as session:
            stmt = select(MediaFile)
            if library_id is not None:
                stmt = stmt.where(col(MediaFile.library_id) == library_id)
            if disk_paths:
                stmt = stmt.where(col(MediaFile.path).not_in(disk_paths))
            elif library_id is None:
                return []
            result = await session.exec(stmt)
            return result.all()

    async def list_media_files(
        self,
        status: Iterable[MediaFileStatus] | None = None,
        limit: int | None = 50,
        offset: int = 0,
        search: str | None = None,
        library_id: int | None = None,
        sort_by: MediaSortField = MediaSortField.UPDATED_AT,
        order: SortOrder = SortOrder.DESC,
        metadata_ids: Sequence[int] | None = None,
    ) -> list[MediaFile]:
        """分页列出媒体文件. metadata_ids: 仅返回挂载到这些 Metadata 的文件; limit None 不分页."""
        async with self._session() as session:
            stmt = select(MediaFile)
            if status is not None:
                stmt = stmt.where(col(MediaFile.status).in_(status))
            if library_id is not None:
                stmt = stmt.where(col(MediaFile.library_id) == library_id)
            if metadata_ids is not None:
                stmt = stmt.where(col(MediaFile.metadata_id).in_(metadata_ids))
            if search:
                pattern = f"%{search}%"
                stmt = stmt.where(or_(col(MediaFile.path).ilike(pattern), col(MediaFile.number).ilike(pattern)))
            # 次级排序键 id 保证分页稳定 (主排序键有并列值时顺序确定).
            stmt = (
                stmt.order_by(_order_clause(_MEDIA_SORT_COLUMNS[sort_by], order), col(MediaFile.id).asc())
                .offset(offset)
                .limit(limit)
            )
            result = await session.exec(stmt)
            return list(result.all())

    async def count_media_files(
        self, status: Iterable[MediaFileStatus] | None = None, search: str | None = None, library_id: int | None = None
    ) -> int:
        async with self._session() as session:
            base = select(MediaFile)
            if status is not None:
                base = base.where(col(MediaFile.status).in_(status))
            if library_id is not None:
                base = base.where(col(MediaFile.library_id) == library_id)
            if search:
                pattern = f"%{search}%"
                base = base.where(or_(col(MediaFile.path).ilike(pattern), col(MediaFile.number).ilike(pattern)))
            stmt = select(count()).select_from(base.subquery())
            result = await session.exec(stmt)
            return result.one() or 0

    async def update_media_file(self, media_id: int, **updates: Unpack[MediaFileUpdates]) -> MediaFile | None:
        async with self._session() as session:
            media = await session.get(MediaFile, media_id)
            if media is None:
                return None
            # 显式赋值: 字段名与类型由 MediaFileUpdates(TypedDict) 与 MediaFile 静态保证一致.
            if "path" in updates:
                media.path = updates["path"]
            if "number" in updates:
                media.number = updates["number"]
            if "oshash" in updates:
                media.oshash = updates["oshash"]
            if "size" in updates:
                media.size = updates["size"]
            if "duration" in updates:
                media.duration = updates["duration"]
            if "codec" in updates:
                media.codec = updates["codec"]
            if "status" in updates:
                media.status = updates["status"]
            if "metadata_id" in updates:
                media.metadata_id = updates["metadata_id"]
            media.updated_at = _utcnow()
            session.add(media)
            await session.commit()
            await session.refresh(media)
            return media

    async def delete_media_file(self, media_id: int) -> bool:
        async with self._session() as session:
            media = await session.get(MediaFile, media_id)
            if media is None:
                return False
            await session.delete(media)
            await session.commit()
            return True

    async def count_media_by_metadata_ids(self, metadata_ids: Sequence[int]) -> dict[int, int]:
        """批量统计各 Metadata 关联的 MediaFile 数量; 无关联的 id 不出现在结果中."""
        ids = [i for i in metadata_ids if i]
        if not ids:
            return {}
        async with self._session() as session:
            stmt = (
                select(col(MediaFile.metadata_id), func.count())
                .where(col(MediaFile.metadata_id).in_(ids))
                .group_by(col(MediaFile.metadata_id))
            )
            result = await session.exec(stmt)
            return {mid: n for mid, n in result.all() if mid is not None}

    async def get_media_by_metadata_id(self, metadata_id: int) -> list[MediaFile]:
        async with self._session() as session:
            stmt = select(MediaFile).where(MediaFile.metadata_id == metadata_id)
            result = await session.exec(stmt)
            return list(result.all())
