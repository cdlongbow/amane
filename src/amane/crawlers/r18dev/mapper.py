"""r18 详情 → MediaMetadata 映射.

语言偏好: Language 枚举驱动, 未指定时日文优先带回退, 指定 JP/EN 时仅取对应语言.

图片 URL 处理: r18.dev dump 中所有图片 URL 均为无域名, 无扩展名的相对路径
(如 `digital/video/1hbad00051/1hbad00051pl`). 映射时补全为 DMM 绝对 URL:

- poster / thumb: digital/video 和 digital/amateur 路径 → 双候选 (aws 高清 → pics 标准回落), 其余 → 单候选
- gallery (extrafanart): 统一 pics.dmm.co.jp 单 URL, 不生成 aws 候选 (flat list 无法区分同图候选对)
- 统一追加 `.jpg` 扩展名
"""

import re
from typing import TYPE_CHECKING

from ...enums import Language
from ..models import MediaMetadata

if TYPE_CHECKING:
    from .models import R18VideoDetail


# --- 图片 URL 补全 ---

_CDN_HIGH_RES = "https://awsimgsrc.dmm.co.jp/pics_dig"
_CDN_STANDARD = "https://pics.dmm.co.jp"


def _image_urls(path: str | None) -> list[str]:
    """产出候选 URL 列表.

    digital/video 和 digital/amateur 路径产出双 URL (aws CDN → pics 回落),
    其他路径仅产出标准 URL. None / 空串返回空列表.
    """
    if not path:
        return []
    if path.startswith(("digital/video/", "digital/amateur/")):
        return [
            f"{_CDN_HIGH_RES}/{path}.jpg",
            f"{_CDN_STANDARD}/{path}.jpg",
        ]
    return [f"{_CDN_STANDARD}/{path}.jpg"]


_GALLERY_NUM_RE = re.compile(r"-(\d+)$")


def _parse_gallery_num(path: str) -> int | None:
    """提取 gallery 路径末尾的数字编号, 失败返回 None."""
    m = _GALLERY_NUM_RE.search(path)
    return int(m.group(1)) if m else None


def _generate_gallery(first: str | None, last: str | None) -> list[str]:
    """从首尾 gallery 路径生成完整的 gallery URL 列表.

    r18.dev 仅存储 gallery 首尾路径, 图片按顺序编号 (如 -1 至 -40).
    解析首尾编号后生成所有中间项, 统一使用标准 CDN (pics.dmm.co.jp) 补全域名与 .jpg 扩展名,
    不生成 AWS 高清候选 (gallery 图片量大, 双候选浪费).
    编号异常 (last < first, 包括 -0 结尾) 时仅保留 first.
    """
    if not first:
        return []

    first_num = _parse_gallery_num(first)
    last_num = _parse_gallery_num(last) if last else None

    if first_num is None:
        return [f"{_CDN_STANDARD}/{first}.jpg"]

    if last_num is None or last_num < first_num:
        return [f"{_CDN_STANDARD}/{first}.jpg"]

    base = _GALLERY_NUM_RE.sub("", first)
    return [f"{_CDN_STANDARD}/{base}-{n}.jpg" for n in range(first_num, last_num + 1)]


# --- 主映射 ---


def to_metadata(detail: R18VideoDetail, number: str, language: Language | None = None) -> MediaMetadata:
    """把 r18 聚合详情映射为通用 MediaMetadata.

     number 用调用方传入的规范化番号 (而非 content_id), 保持与其它爬虫一致.

     语言偏好:
    - None: 日文优先, 缺则回退英文.
    - JP: 仅日文, 缺则 None.
    - EN: 仅英文, 缺则 None.
    """
    v = detail.video

    # 标题与简介
    if language is Language.JP:
        title = v.title_ja
        plot = v.comment_ja
    elif language is Language.EN:
        title = v.title_en
        plot = v.comment_en
    else:
        title = v.title_ja or v.title_en
        plot = v.comment_ja or v.comment_en

    actors = [n for p in (*detail.actresses, *detail.actors) if (n := p.best(language))]
    directors = [n for p in detail.directors if (n := p.best(language))]
    tags = [n for c in detail.categories if (n := c.best(language))]

    studio = detail.maker.best(language) if detail.maker else None
    publisher = detail.label.best(language) if detail.label else None
    series = detail.series.best(language) if detail.series else None

    # 图片 URL 补全: jacket_full 作 thumb (大图), jacket_thumb 作 poster
    # digital/video 路径产出双候选 (高清 CDN → 标准回落)
    poster_urls = _image_urls(v.jacket_thumb_url)
    thumb_urls = _image_urls(v.jacket_full_url) or _image_urls(v.jacket_thumb_url)

    # Gallery: 从首尾生成全量, gallery_full 优先, 回退 gallery_thumb
    extrafanart = _generate_gallery(v.gallery_full_first, v.gallery_full_last)
    if not extrafanart:
        extrafanart = _generate_gallery(v.gallery_thumb_first, v.gallery_thumb_last)

    release = v.release_date.isoformat() if v.release_date else None
    score = None  # r18 derived schema 无统一评分字段, 留空

    return MediaMetadata(
        number=number,
        title=title or None,
        actors=actors,
        studio=studio,
        publisher=publisher,
        release=release,
        runtime=v.runtime_mins,
        tags=tags,
        series=series,
        plot=plot or None,
        poster_urls=poster_urls,
        thumb_urls=thumb_urls,
        trailer_urls=[detail.trailer_url] if detail.trailer_url else [],
        score=score,
        external_id=v.content_id,
        source_url=None,
        directors=directors,
        extrafanart=extrafanart,
    )
