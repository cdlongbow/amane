import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from ...utils.path import is_any_descendant
from ..deps import RuntimeDep

router = APIRouter(prefix="/files", tags=["files"])

_MAX_ITEMS = 1000


class FileItem(BaseModel):
    """文件或目录条目"""

    name: str = Field(..., description="File or directory name.")
    path: str = Field(..., description="Absolute POSIX path.")
    type: Literal["file", "directory"] = Field(..., description="Entry type.")
    size: int | None = Field(default=None, description="File size in bytes (omitted for directories).")
    last_modified: datetime | None = Field(default=None, description="Last modification time.")


class FileListResponse(BaseModel):
    """目录列表响应"""

    items: list[FileItem] = Field(
        ..., description="Entries sorted directories-first, then by name (case-insensitive). Truncated to 1000."
    )
    total: int = Field(..., description="Total entry count before truncation.")


@router.get("", summary="List files and directories at a server path")
async def list_files(
    path: Annotated[str, Query(description="Server path to list. Relative paths resolve against first safe dir.")],
    runtime: RuntimeDep,
    show_hidden: Annotated[bool, Query(description="Whether to include hidden files (dotfiles).")] = False,
) -> FileListResponse:
    """列出目录内容. 仅允许访问启动时确定的安全目录内的路径"""
    safe_dirs = runtime.safe_dirs
    if not safe_dirs:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="No safe directories configured.")

    p = Path(path)
    try:
        target_path = p.resolve(strict=True) if p.is_absolute() else (safe_dirs[0] / p).resolve(strict=True)
    except OSError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Path resolution failed — may not exist or lacks access permission.",
        )

    # 安全检查
    if not is_any_descendant(target_path, *safe_dirs):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access to this path is not permitted.")

    # 如果路径是文件, 则列出其父目录
    if not target_path.is_dir():
        target_path = target_path.parent

    if not target_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Path does not exist: {path}")

    items: list[FileItem] = []
    try:
        for entry in os.scandir(target_path):
            if not show_hidden and entry.name.startswith("."):
                continue
            entry_path = Path(entry.path)
            item_type: Literal["file", "directory"] = "directory" if entry_path.is_dir() else "file"
            item = FileItem(name=entry.name, path=str(entry_path.as_posix()), type=item_type)
            try:
                stat_result = entry.stat()
                item.last_modified = datetime.fromtimestamp(stat_result.st_mtime, tz=UTC)
                if item_type == "file":
                    item.size = stat_result.st_size
            except OSError, FileNotFoundError:
                pass
            items.append(item)
    except PermissionError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied reading directory.")

    # 排序: 目录优先, 然后按名称字母序 (不区分大小写)
    items.sort(key=lambda x: (x.type != "directory", x.name.lower()))
    total = len(items)
    return FileListResponse(items=items[:_MAX_ITEMS], total=total)
