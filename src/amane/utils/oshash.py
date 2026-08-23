"""影片文件指纹 (oshash) 计算.

oshash 是 Stash 系站点 (ThePornDB 等) 的 open-subtitles 风格指纹:
文件大小 + 首尾各 64 KiB 按小端 int64 累加, 输出 16 位小写 hex.
本模块包一层, 收敛大小/IO 边界, 调用方无需关心异常.
"""

from __future__ import annotations

import asyncio
import io
import struct
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from pathlib import Path

logger = structlog.get_logger()

#: 首尾各 64 KiB (oshash 规范)
CHUNK_SIZE = 65536
#: 每次解包 8 字节 (小端 int64)
_UNPACK = struct.Struct("<q")
#: 文件至少需首尾各 64 KiB 才可计算
_MIN_FILE_SIZE = CHUNK_SIZE * 2


def compute_oshash(path: Path) -> str | None:
    """计算文件 oshash, 与 ``oshash`` 包实现一致.

    不可用文件 (< 128 KiB / 无法读取) 返回 ``None`` 而非抛异常 —
    .strm 占位文件等对象本就没有指纹. 同步阻塞 (最多读 128 KiB), 只应在
    工作线程中调用.
    """
    try:
        file_size = path.stat().st_size
    except OSError as e:
        logger.debug("oshash stat failed", path=str(path), error=str(e))
        return None
    if file_size < _MIN_FILE_SIZE:
        logger.debug("oshash skipped: file too small", path=str(path), size=file_size)
        return None
    try:
        with open(path, "rb") as f:
            file_hash = file_size
            # 文件头: 完整读满 64 KiB (getsize ≥ 128 KiB, 头块必然读满)
            head = f.read(CHUNK_SIZE)
            if len(head) < CHUNK_SIZE:
                return None
            file_hash = _sum_chunk(head, file_hash)
            # 文件尾: 从末尾倒数 64 KiB
            f.seek(-CHUNK_SIZE, io.SEEK_END)
            tail = f.read(CHUNK_SIZE)
            if len(tail) < CHUNK_SIZE:
                return None
            file_hash = _sum_chunk(tail, file_hash)
            return f"{file_hash:016x}"
    except OSError as e:
        logger.debug("oshash read failed", path=str(path), error=str(e))
        return None


def _sum_chunk(data: bytes, file_hash: int) -> int:
    """将 64 KiB 块按小端 int64 逐项累加进 hash (模 2^64 环绕)."""
    for i in range(0, CHUNK_SIZE, _UNPACK.size):
        (unpacked,) = _UNPACK.unpack_from(data, i)
        file_hash = (file_hash + unpacked) & 0xFFFFFFFFFFFFFFFF
    return file_hash


async def compute_oshash_async(path: Path) -> str | None:
    """``compute_oshash`` 的异步包装: 投递到默认线程池, 避免阻塞事件循环."""
    return await asyncio.to_thread(compute_oshash, path)
