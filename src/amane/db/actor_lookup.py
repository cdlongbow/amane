"""演员刮削查找名构造 - 规范名 + FacetRule 入边 + aliases."""

from __future__ import annotations

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from amane.db.models import Actor, FacetKind, FacetRule, FacetRuleAction


def _dedupe_preserve(names: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for name in names:
        if not name or name in seen:
            continue
        seen.add(name)
        out.append(name)
    return out


async def build_actor_lookup_names(session: AsyncSession, actor: Actor) -> list[str]:
    """有序候选名: name → 入边 FacetRule alias 源名 → Actor.aliases."""
    names: list[str] = [actor.name]
    stmt = select(FacetRule.source_name).where(
        FacetRule.kind == FacetKind.ACTOR,
        FacetRule.action == FacetRuleAction.ALIAS,
        FacetRule.target_name == actor.name,
    )
    inbound = list((await session.exec(stmt)).all())
    names.extend(inbound)
    names.extend(actor.aliases or [])
    return _dedupe_preserve(names)


async def list_inbound_alias_names(session: AsyncSession, canonical_name: str) -> list[str]:
    """详情展示用: 指向规范名的 alias 源名列表."""
    stmt = (
        select(FacetRule.source_name)
        .where(
            FacetRule.kind == FacetKind.ACTOR,
            FacetRule.action == FacetRuleAction.ALIAS,
            FacetRule.target_name == canonical_name,
        )
        .order_by(col(FacetRule.source_name))
    )
    return list((await session.exec(stmt)).all())
