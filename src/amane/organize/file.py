from dataclasses import dataclass
from pathlib import Path

import structlog

from ..enums import MoveMode
from ..utils.threads import in_thread

logger = structlog.get_logger()


@dataclass
class OrganizeResult:
    success: bool
    dest: Path | None = None
    error: str | None = None


@in_thread
def execute_organize(
    source: Path,
    target_dir: Path,
    target_stem: str,
    mode: MoveMode = MoveMode.MOVE,
    *,
    suffix: str | None = None,
) -> OrganizeResult:
    # 校验源文件存在.
    if not source.exists():
        logger.warning("organize source not found", source=str(source))
        return OrganizeResult(success=False, error=f"Source not found: {source}")

    try:
        target_dir.mkdir(parents=True, exist_ok=True)
        dest_suffix = source.suffix if suffix is None else suffix
        dest = target_dir / f"{target_stem}{dest_suffix}"
        # 已就位则跳过碰撞改名.
        if _already_at_dest(source, dest):
            return OrganizeResult(success=True, dest=dest)

        # 目标占用时追加 (1), (2).
        dest = _resolve_collision(dest)

        match mode:
            case MoveMode.MOVE:
                source.move(dest)
            case MoveMode.COPY:
                source.copy(dest)
            case MoveMode.HARDLINK:
                dest.hardlink_to(source)
            case MoveMode.SYMLINK:
                dest.symlink_to(source)

        logger.debug("file organized", source=source.name, dest=str(dest), mode=mode)
        return OrganizeResult(success=True, dest=dest)

    except Exception as e:
        logger.error("organize failed", source=str(source), target_dir=str(target_dir), error=str(e))
        return OrganizeResult(success=False, error=str(e))


def _already_at_dest(source: Path, dest: Path) -> bool:
    """源与模板 dest 已是同一文件 (含硬链) 则视为已整理, 不触发碰撞改名."""
    if not dest.exists():
        return False
    try:
        return source.samefile(dest)
    except OSError:
        return False


def _resolve_collision(dest: Path) -> Path:
    if not dest.exists():
        return dest
    stem = dest.stem
    suffix = dest.suffix
    parent = dest.parent
    i = 1
    while True:
        candidate = parent / f"{stem}({i}){suffix}"
        if not candidate.exists():
            return candidate
        i += 1
