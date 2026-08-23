"""媒体文件扩展名与预告片跳过 (目录监控与扫描共用).

叶子模块: 无任何 amane 内部导入, 供 scheduler 与 handlers 两侧引用,
避免 handlers._common ↔ scheduler.watcher 的循环导入.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING, Annotated

from pydantic import AfterValidator

if TYPE_CHECKING:
    from re import Pattern

MEDIA_EXTENSIONS = frozenset(
    {
        ".mp4",
        ".mkv",
        ".avi",
        ".wmv",
        ".flv",
        ".mov",
        ".ts",
        ".iso",
        ".strm",
    }
)

# 与默认 trailer 模板文件名 `{video_dir}/trailer.mp4` 对齐; 空串表示不跳过.
DEFAULT_TRAILER_PATTERN = "(?i)trailer"


def compile_skip_pattern(pattern: str | None) -> Pattern[str] | None:
    """编译预告片跳过正则. 空串/非法模式返回 None (不跳过)."""
    if not pattern or not pattern.strip():
        return None
    try:
        return re.compile(pattern)
    except re.error:
        return None


def validate_trailer_pattern(pattern: str) -> str:
    """校验用户输入的预告片正则; 空串合法 (关闭跳过)."""
    if pattern.strip():
        try:
            re.compile(pattern)
        except re.error as exc:
            raise ValueError(f"invalid trailer_pattern: {exc}") from exc
    return pattern


TrailerPattern = Annotated[str, AfterValidator(validate_trailer_pattern)]


def is_skipped_media(path: Path, pattern: str | None) -> bool:
    """文件名 (含扩展名) 命中库级 trailer_pattern 则为预告片, 扫描/监控应跳过."""
    compiled = compile_skip_pattern(pattern)
    if compiled is None:
        return False
    return compiled.search(path.name) is not None
