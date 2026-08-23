"""r18.dev 只读查询 - 固定显式列 SQL.

这组 SQL 是项目与 r18 schema 的**唯一契约**. r18 dump 改结构时只需审计本文件:
- 只 SELECT 点名的列 → r18 新增/改动我们没引用的列零影响 (不映射全表, 刻意收窄依赖面).
- 与运行时同款 SELECT 也用于导入期 schema 校验 (importer.validate_schema), 列被删/改名 →
  导入被拒, 线上停留在上一个 good 版本.

番号 → content_id 匹配目前是基础实现 (dvd_id 精确 + content_id 零填充变体), 刻意留出
增强余量: 可后续加模糊匹配 / service_code 优选 / 多结果排序. 检索类扩展 (按演员列出全部
作品等) 也挂在这里.
"""

import re
from collections.abc import Sequence

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from .models import R18Named, R18Person, R18Video, R18VideoDetail

# --- 番号规范化 (留余量: 仅覆盖主流场景, 可渐进增强) ---


def _normalize(number: str) -> tuple[str, str] | None:
    """番号 → (前缀小写, 数字串). 无法解析返回 None."""
    m = re.search(r"([a-zA-Z]+)-?(\d+)", number)
    if not m:
        return None
    return m.group(1).lower(), m.group(2)


def content_id_candidates(number: str) -> list[str]:
    """由番号生成可能的 DMM content_id 变体 (零填充 5 位 / 原零填充 / 去零).

    例: MIDV-123 → ['midv00123', 'midv123']
    例: MLDE-013 → ['mlde00013', 'mlde013', 'mlde13']
    顺序即优先级: 5 位标准零填充 > 保留原始零填充 > 去前导零.
    """
    parsed = _normalize(number)
    if not parsed:
        return []
    prefix, digits = parsed
    # 去前导零再统一
    digits_int = digits.lstrip("0") or "0"
    padded = f"{prefix}{digits_int:0>5}"
    preserved = f"{prefix}{digits}"
    plain = f"{prefix}{digits_int}"
    out: list[str] = []
    for c in (padded, preserved, plain):
        if c not in out:
            out.append(c)
    return out


# --- 查询契约 ---

# 主行: 显式列, 不取我们用不到的字段
_VIDEO_COLS = (
    "content_id, service_code, dvd_id, title_en, title_ja, comment_en, comment_ja, "
    "runtime_mins, release_date, sample_url, maker_id, label_id, series_id, "
    "jacket_full_url, jacket_thumb_url, gallery_full_first, gallery_full_last, "
    "gallery_thumb_first, gallery_thumb_last"
)


class R18Repository:
    """r18 只读查询封装. 每个方法接收一个 AsyncSession (由调用方按需开闭)."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def find_video_row(self, number: str) -> dict | None:
        """番号 → derived_video 主行 (dict). 找不到返回 None.

        匹配策略 (按优先级):
        1. dvd_id 精确 (大小写不敏感) - r18 的 dvd_id 通常即标准番号.
        2. content_id 落在零填充/原样变体集合内.
        多行命中时优先 release_date 最新的一条 (留余量, 可改为按 service_code 优选).
        """
        candidates = content_id_candidates(number)
        stmt = text(
            f"SELECT {_VIDEO_COLS} FROM derived_video "
            "WHERE upper(dvd_id) = upper(:number) OR content_id = ANY(:cids) "
            "ORDER BY release_date DESC NULLS LAST LIMIT 1"
        )
        result = await self.session.execute(stmt, {"number": number, "cids": candidates})
        row = result.mappings().first()
        return dict(row) if row else None

    async def get_detail(self, number: str) -> R18VideoDetail | None:
        """番号 → 完整聚合详情 (主行 + 关联实体). 找不到返回 None."""
        row = await self.find_video_row(number)
        if row is None:
            return None

        video = R18Video.model_validate(row)
        cid = video.content_id

        maker = await self._get_named("derived_maker", row.get("maker_id"))
        label = await self._get_named("derived_label", row.get("label_id"))
        series = await self._get_named("derived_series", row.get("series_id"))
        actresses = await self._actresses(cid)
        actors = await self._actors(cid)
        directors = await self._directors(cid)
        categories = await self._categories(cid)
        trailer = await self._trailer(cid)

        return R18VideoDetail(
            video=video,
            maker=maker,
            label=label,
            series=series,
            actresses=actresses,
            actors=actors,
            directors=directors,
            categories=categories,
            trailer_url=trailer or video.sample_url,
        )

    # --- 关联实体 ---

    async def _get_named(self, table: str, entity_id: int | None) -> R18Named | None:
        if entity_id is None:
            return None
        # table 来自硬编码常量, 非用户输入 - 无注入风险
        stmt = text(f"SELECT id, name_en, name_ja FROM {table} WHERE id = :id")
        row = (await self.session.execute(stmt, {"id": entity_id})).mappings().first()
        return R18Named.model_validate(dict(row)) if row else None

    async def _actresses(self, content_id: str) -> list[R18Person]:
        stmt = text(
            "SELECT a.id, a.name_romaji, a.name_kanji, a.name_kana "
            "FROM derived_video_actress va JOIN derived_actress a ON a.id = va.actress_id "
            "WHERE va.content_id = :cid ORDER BY va.ordinality NULLS LAST"
        )
        rows = (await self.session.execute(stmt, {"cid": content_id})).mappings().all()
        return [R18Person.model_validate(dict(r)) for r in rows]

    async def _actors(self, content_id: str) -> list[R18Person]:
        stmt = text(
            "SELECT a.id, NULL AS name_romaji, a.name_kanji, a.name_kana "
            "FROM derived_video_actor va JOIN derived_actor a ON a.id = va.actor_id "
            "WHERE va.content_id = :cid ORDER BY va.ordinality NULLS LAST"
        )
        rows = (await self.session.execute(stmt, {"cid": content_id})).mappings().all()
        return [R18Person.model_validate(dict(r)) for r in rows]

    async def _directors(self, content_id: str) -> list[R18Person]:
        stmt = text(
            "SELECT d.id, d.name_romaji, d.name_kanji, d.name_kana "
            "FROM derived_video_director vd JOIN derived_director d ON d.id = vd.director_id "
            "WHERE vd.content_id = :cid"
        )
        rows = (await self.session.execute(stmt, {"cid": content_id})).mappings().all()
        return [R18Person.model_validate(dict(r)) for r in rows]

    async def _categories(self, content_id: str) -> list[R18Named]:
        stmt = text(
            "SELECT c.id, c.name_en, c.name_ja "
            "FROM derived_video_category vc JOIN derived_category c ON c.id = vc.category_id "
            "WHERE vc.content_id = :cid"
        )
        rows = (await self.session.execute(stmt, {"cid": content_id})).mappings().all()
        return [R18Named.model_validate(dict(r)) for r in rows]

    async def _trailer(self, content_id: str) -> str | None:
        stmt = text("SELECT url FROM source_dmm_trailer WHERE content_id = :cid LIMIT 1")
        row = (await self.session.execute(stmt, {"cid": content_id})).first()
        return row[0] if row else None

    # --- 导入期 schema 校验用的探针查询 ---

    @staticmethod
    def schema_probes() -> Sequence[str]:
        """返回一组 LIMIT 0/1 探针 SQL, 覆盖运行时实际依赖的所有表与列.

        importer 用它打刚导入的临时库; 任一条失败 (列被删/改名/类型不兼容) → 拒绝换名.
        与上面的查询保持同源, 改查询时同步改这里.
        """
        return (
            f"SELECT {_VIDEO_COLS} FROM derived_video LIMIT 1",
            "SELECT id, name_en, name_ja FROM derived_maker LIMIT 1",
            "SELECT id, name_en, name_ja FROM derived_label LIMIT 1",
            "SELECT id, name_en, name_ja FROM derived_series LIMIT 1",
            "SELECT id, name_en, name_ja FROM derived_category LIMIT 1",
            "SELECT id, name_romaji, name_kanji, name_kana FROM derived_actress LIMIT 1",
            "SELECT id, name_kanji, name_kana FROM derived_actor LIMIT 1",
            "SELECT id, name_romaji, name_kanji, name_kana FROM derived_director LIMIT 1",
            "SELECT content_id, actress_id, ordinality FROM derived_video_actress LIMIT 1",
            "SELECT content_id, actor_id, ordinality FROM derived_video_actor LIMIT 1",
            "SELECT content_id, category_id FROM derived_video_category LIMIT 1",
            "SELECT content_id, director_id FROM derived_video_director LIMIT 1",
            "SELECT content_id, url FROM source_dmm_trailer LIMIT 1",
        )
