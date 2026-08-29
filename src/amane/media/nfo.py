"""
面向 Kodi/Emby/Jellyfin 的 NFO 生成 - 遵循 Kodi <movie> 规范的 XML 格式.

生成与以下媒体服务器兼容的 .nfo 辅助文件:
- Emby / Jellyfin 媒体服务器
- Kodi (原生 NFO 支持)
"""

import re
from io import StringIO
from typing import TYPE_CHECKING

import aiofiles
import structlog

if TYPE_CHECKING:
    from pathlib import Path

    from ..db.models import Metadata


logger = structlog.get_logger()


# --- XML 实体转义 ---

_XML_ESCAPE_MAP: dict[str, str] = {
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    "'": "&apos;",
    '"': "&quot;",
}


def _escape_xml(text: str) -> str:
    """转义文本内容中的 XML 特殊字符."""
    for char, entity in _XML_ESCAPE_MAP.items():
        text = text.replace(char, entity)
    return text


# --- NFO 写入器 ---


async def write_nfo(metadata: Metadata, nfo_path: Path) -> bool:
    """
    从 Metadata 对象生成兼容 Kodi 的 .nfo 文件.

    Args:
        metadata: 待序列化的元数据记录.
        nfo_path: .nfo 文件的目标路径.

    Returns:
        文件写入成功返回 True, 出错返回 False.
    """
    try:
        nfo_path.parent.mkdir(parents=True, exist_ok=True)

        code = StringIO()
        code.write('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n')
        code.write("<movie>\n")

        # 剧情 / 简介
        if metadata.plot:
            plot_escaped = _escape_xml(metadata.plot)
            code.write(f"  <plot><![CDATA[{metadata.plot}]]></plot>\n")
            code.write(f"  <outline>{plot_escaped}</outline>\n")

        # 发行日期
        if metadata.release:
            code.write(f"  <premiered>{metadata.release}</premiered>\n")
            code.write(f"  <releasedate>{metadata.release}</releasedate>\n")
            year_match = re.match(r"(\d{4})", metadata.release)
            if year_match:
                code.write(f"  <year>{year_match.group(1)}</year>\n")

        # 番号
        code.write(f"  <num>{_escape_xml(metadata.number)}</num>\n")

        # 标题
        if metadata.title:
            code.write(f"  <title>{_escape_xml(metadata.number)} {_escape_xml(metadata.title)}</title>\n")
            code.write(
                f"  <originaltitle>{_escape_xml(metadata.number)} {_escape_xml(metadata.title)}</originaltitle>\n"
            )
            code.write(f"  <sorttitle>{_escape_xml(metadata.number)} {_escape_xml(metadata.title)}</sorttitle>\n")

        # 分级 (MPAA)
        code.write("  <mpaa>JP-18+</mpaa>\n")

        # 演员
        if metadata.actors:
            for actor in metadata.actors:
                code.write("  <actor>\n")
                code.write(f"    <name>{_escape_xml(actor)}</name>\n")
                code.write("    <type>Actor</type>\n")
                code.write("  </actor>\n")

        # 评分
        if metadata.score is not None:
            code.write(f"  <rating>{metadata.score}</rating>\n")
            code.write(f"  <criticrating>{int(metadata.score * 10)}</criticrating>\n")

        # 时长
        if metadata.runtime is not None:
            code.write(f"  <runtime>{metadata.runtime}</runtime>\n")

        # 系列
        if metadata.series:
            code.write(f"  <series>{_escape_xml(metadata.series)}</series>\n")
            code.write("  <set>\n")
            code.write(f"    <name>{_escape_xml(metadata.series)}</name>\n")
            code.write("  </set>\n")

        # 制作商
        if metadata.studio:
            code.write(f"  <studio>{_escape_xml(metadata.studio)}</studio>\n")
            code.write(f"  <maker>{_escape_xml(metadata.studio)}</maker>\n")

        # 发行商 / 标签
        if metadata.publisher:
            code.write(f"  <publisher>{_escape_xml(metadata.publisher)}</publisher>\n")
            code.write(f"  <label>{_escape_xml(metadata.publisher)}</label>\n")

        # 标签 / 类型
        if metadata.tags:
            for tag in metadata.tags:
                if tag:
                    code.write(f"  <tag>{_escape_xml(tag)}</tag>\n")
                    code.write(f"  <genre>{_escape_xml(tag)}</genre>\n")

        # 海报
        if metadata.poster_url:
            code.write(f"  <poster>{_escape_xml(metadata.poster_url)}</poster>\n")

        # 缩略图 / 封面
        if metadata.thumb_url:
            code.write(f"  <cover>{_escape_xml(metadata.thumb_url)}</cover>\n")

        # 预告片
        if metadata.trailer_url:
            code.write(f"  <trailer>{_escape_xml(metadata.trailer_url)}</trailer>\n")

        # 导演
        if metadata.directors:
            for director in metadata.directors:
                code.write(f"  <director>{_escape_xml(director)}</director>\n")

        # 外部 ID
        if metadata.external_ids:
            for site, ext_id in metadata.external_ids.items():
                if ext_id:
                    code.write(f"  <{site}id>{_escape_xml(str(ext_id))}</{site}id>\n")

        code.write("</movie>\n")

        # 原子写入 (理想情况应写入临时文件再重命名,
        # 目前为简化直接覆盖)
        async with aiofiles.open(nfo_path, "w", encoding="UTF-8") as f:
            await f.write(code.getvalue())

        logger.debug("nfo written", path=str(nfo_path))
        return True

    except Exception:
        logger.exception("nfo write failed", path=str(nfo_path))
        return False
