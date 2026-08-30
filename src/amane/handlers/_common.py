"""
handler 间共享的可复用单元.

- iter_media_files / aiter_media_files: 目录遍历 + 媒体文件过滤 (REFRESH / ORGANIZE)
- register_media_file: 注册 MediaFile (WATCHER 发现 / REFRESH 扫描); 不计算 oshash
- ensure_oshash: 按需计算并落库指纹 (仅 Stash 系刮削前调用)
- finalize_media_file: 标记 MediaFile 为已刮削并关联 Metadata (SCRAPE)

库目录落盘 (apply_file_operations) 在 file.py, 仅 ORGANIZE 调用.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING

from ..db import MediaFileStatus
from ..utils.extensions import MEDIA_EXTENSIONS, compile_skip_patterns, is_in_trash, is_undersized_video
from ..utils.oshash import compute_oshash

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Iterator, Sequence

    from ..db.models import MediaFile
    from ..db.repository import Repository

# 每批在工作线程里推进的 glob 条目数: 让出事件循环, 又避免每文件一次 to_thread.
_WALK_BATCH = 256


def _maybe_file(f: Path) -> bool:
    """判断路径是否为(可能断链的)文件入口: 常规文件或符号链接."""
    return f.is_file() or f.is_symlink()


def iter_media_files(
    scan_dir: Path,
    *,
    recursive: bool,
    patterns: list[str] | None,
    skip_patterns: Sequence[str | None] | None = None,
    min_file_size: int = 0,
    media_extensions: frozenset[str] | None = None,
) -> Iterator[Path]:
    """遍历目录, 产出符合条件的媒体文件路径.

     过滤规则:
    - 仅产出常规文件 (跳过目录/目录符号链接等, 但允许文件符号链接和无效链接)
    - 提供 patterns 时按 glob 模式匹配 (任一命中即可)
    - 未提供 patterns 时按 media_extensions (默认 MEDIA_EXTENSIONS) 扩展名过滤
    - skip_patterns 任一命中文件名 (含扩展名) 则跳过 (预告片/黑名单正则)
    - 路径任一组件为 `.amane_trash` (回收站) 则跳过
    - min_file_size > 0 时跳过低于阈值的**视频** (同一套扩展名; 图片/nfo/字幕/strm 不参与)

     Args:
         scan_dir: 待遍历目录
         recursive: 是否递归子目录
         patterns: 文件名 glob 模式列表, None 时回退到扩展名过滤
         skip_patterns: 跳过正则列表 (预告片 + 黑名单), 空/非法则跳过
         min_file_size: 视频体积下限 (字节); 0 关闭
         media_extensions: 视频扩展名白名单; None 则 MEDIA_EXTENSIONS
    """
    glob_pattern = "**/*" if recursive else "*"
    skip_res = compile_skip_patterns(skip_patterns)
    extensions = MEDIA_EXTENSIONS if media_extensions is None else media_extensions
    for file_path in scan_dir.glob(glob_pattern):
        if not _maybe_file(file_path):
            continue
        if is_in_trash(file_path):
            continue
        if skip_res is not None and any(r.search(file_path.name) for r in skip_res):
            continue
        if patterns:
            if not any(file_path.match(p) for p in patterns):
                continue
        elif file_path.suffix.lower() not in extensions:
            continue
        if is_undersized_video(file_path, min_file_size, media_extensions=extensions):
            continue
        yield file_path


async def aiter_media_files(
    scan_dir: Path,
    *,
    recursive: bool,
    patterns: list[str] | None,
    skip_patterns: Sequence[str | None] | None = None,
    min_file_size: int = 0,
    media_extensions: frozenset[str] | None = None,
) -> AsyncIterator[Path]:
    """``iter_media_files`` 的异步封装: glob/stat 在线程池分批推进, 不堵事件循环."""
    iterator = iter_media_files(
        scan_dir,
        recursive=recursive,
        patterns=patterns,
        skip_patterns=skip_patterns,
        min_file_size=min_file_size,
        media_extensions=media_extensions,
    )

    def _next_batch() -> list[Path]:
        batch: list[Path] = []
        for _ in range(_WALK_BATCH):
            try:
                batch.append(next(iterator))
            except StopIteration:
                break
        return batch

    while True:
        batch = await asyncio.to_thread(_next_batch)
        if not batch:
            return
        for path in batch:
            yield path


async def register_media_file(repo: Repository, library_id: int, path: Path) -> MediaFile:
    """创建 MediaFile 记录. oshash 留给刮削按需计算, 注册不读文件内容."""
    return await repo.create_media_file(library_id=library_id, path=str(path))


async def ensure_oshash(repo: Repository, media: MediaFile) -> str | None:
    """已有指纹直接返回; 否则计算并落库. 失败留 None, 不阻断刮削."""
    if media.oshash is not None:
        return media.oshash
    media_hash = await compute_oshash(Path(media.path))
    if media_hash is None or media.id is None:
        return None
    updated = await repo.update_media_file(media.id, oshash=media_hash)
    return updated.oshash if updated is not None else media_hash


async def finalize_media_file(repo: Repository, media_file_id: int | None, metadata_id: int | None) -> None:
    """将 MediaFile 标记为已刮削并关联 Metadata. media_file_id 为 None 时静默跳过."""
    if media_file_id is None:
        return
    await repo.update_media_file(media_file_id, status=MediaFileStatus.SCRAPED, metadata_id=metadata_id)
