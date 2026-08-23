"""r18.dev 查询结果的宽松读模型.

设计要点 (鲁棒性): 字段一律 Optional + 默认值. r18 是外部不可控的只读镜像, 某列变 NULL
或暂时缺失时降级为空, 而非抛错. 真正的 schema 漂移 (列被删/改名/类型不兼容) 由导入期
schema 校验拦截 (见 importer.py), 坏 dump 进不了线上.

这些模型只覆盖 repository.py 显式 SELECT 的列 - 那组 SQL 是我们与 r18 schema 的唯一契约.
"""

import datetime

from pydantic import BaseModel

from ...enums import Language


class R18Person(BaseModel):
    """演员 / 导演的多语言名."""

    id: int | None = None
    name_romaji: str | None = None
    name_kanji: str | None = None
    name_kana: str | None = None

    def best(self, language: Language | None = None) -> str | None:
        """按语言偏好返回最合适的名字.

        JP: kanji → kana. 缺则 None, 不回退其他语言.
        EN: romaji. 缺则 None, 不回退其他语言.
        None: kanji → kana → romaji (日文优先, 带回退).
        """
        if language is Language.JP:
            return self.name_kanji or self.name_kana
        if language is Language.EN:
            return self.name_romaji
        return self.name_kanji or self.name_kana or self.name_romaji


class R18Named(BaseModel):
    """maker / label / series / category 的 en/ja 名."""

    id: int | None = None
    name_en: str | None = None
    name_ja: str | None = None

    def best(self, language: Language | None = None) -> str | None:
        """按语言偏好返回最合适的名字.

        JP: name_ja. 缺则 None, 不回退其他语言.
        EN: name_en. 缺则 None, 不回退其他语言.
        None: name_ja → name_en (日文优先, 带回退).
        """
        if language is Language.JP:
            return self.name_ja
        if language is Language.EN:
            return self.name_en
        return self.name_ja or self.name_en


class R18Video(BaseModel):
    """derived_video 主行 (仅 repository 用到的列)."""

    content_id: str
    dvd_id: str | None = None
    title_en: str | None = None
    title_ja: str | None = None
    comment_en: str | None = None
    comment_ja: str | None = None
    runtime_mins: int | None = None
    release_date: datetime.date | None = None
    sample_url: str | None = None
    jacket_full_url: str | None = None
    jacket_thumb_url: str | None = None
    gallery_full_first: str | None = None
    gallery_full_last: str | None = None
    gallery_thumb_first: str | None = None
    gallery_thumb_last: str | None = None


class R18VideoDetail(BaseModel):
    """聚合后的完整结果 - 主行 + 关联实体. mapper 据此产出 MediaMetadata."""

    video: R18Video
    maker: R18Named | None = None
    label: R18Named | None = None
    series: R18Named | None = None
    actresses: list[R18Person] = []
    actors: list[R18Person] = []
    directors: list[R18Person] = []
    categories: list[R18Named] = []
    trailer_url: str | None = None
