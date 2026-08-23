"""actor-ops Capability - 演员人物字段与刮削入队."""

from __future__ import annotations

from typing import Any, cast

from pydantic_ai import RunContext
from pydantic_ai.capabilities import Capability

from amane.db.models import TaskType
from amane.db.repo_types import ActorPersonFields
from amane.handlers.models import ActorScrapePayload, CacheKind
from amane.utils.dates import normalize_calendar_date

from .tools import AgentDeps, trace_tool

_AGENT_ACTOR_PATCH_KEYS = frozenset(
    {
        "aliases",
        "gender",
        "birthday",
        "birthplace",
        "height",
        "bust",
        "waist",
        "hip",
        "cup",
        "overview",
        "tagline",
        "image_urls",
        "provider_ids",
        "source_urls",
    }
)


def build_actor_ops_capability() -> Capability[AgentDeps]:
    """按需加载的演员管理能力 (人物 PATCH / 刮削; 身份合并走 facet-identity)."""
    cap: Capability[AgentDeps] = Capability(
        id="actor-ops",
        description=(
            "Use for patching actor person fields and enqueueing actor scrape tasks. "
            "For rename/merge/delete of identity facets, load facet-identity instead."
        ),
        instructions=(
            "Mutate actors only via these tools — never raw SQL. "
            "Prefer actor ids from sql_deliver / explore views. "
            "Do not rename actors here; use facet-identity.rename_facet for name changes."
        ),
        defer_loading=True,
    )

    @cap.tool
    async def update_actor(ctx: RunContext[AgentDeps], actor_id: int, patch: dict[str, Any]) -> dict[str, Any]:
        """Patch actor person fields (aliases, gender, birthday, ...). Omits name/raw/field_sources."""
        trace_tool(ctx, "tool_call", {"tool": "update_actor", "actor_id": actor_id, "patch": patch})
        if not patch:
            return {"error": "patch 为空"}
        unknown = sorted(set(patch) - _AGENT_ACTOR_PATCH_KEYS)
        if unknown:
            return {"error": f"不允许的字段: {', '.join(unknown)}"}
        updates = dict(patch)
        if "birthday" in updates:
            raw_bday = updates["birthday"]
            if raw_bday is None or (isinstance(raw_bday, str) and not raw_bday.strip()):
                updates["birthday"] = None
            elif isinstance(raw_bday, str):
                normalized = normalize_calendar_date(raw_bday)
                if normalized is None:
                    return {"error": "birthday 须为 YYYY-MM-DD"}
                updates["birthday"] = normalized
            else:
                return {"error": "birthday 须为 YYYY-MM-DD"}
        actor = await ctx.deps.repo.update_actor(actor_id, **cast(ActorPersonFields, updates))
        if actor is None:
            return {"error": f"actor {actor_id} 不存在"}
        out = {"id": actor.id, "name": actor.name, "updated": True}
        trace_tool(ctx, "tool_result", {"tool": "update_actor", "result": out})
        return out

    @cap.tool
    async def enqueue_actor_scrape(
        ctx: RunContext[AgentDeps], actor_ids: list[int], use_cache: set[CacheKind] | None = None
    ) -> dict[str, Any]:
        """Enqueue ACTOR_SCRAPE tasks for actor ids."""
        cache_kinds = use_cache if use_cache is not None else {CacheKind.metadata, CacheKind.trans}
        trace_tool(
            ctx,
            "tool_call",
            {
                "tool": "enqueue_actor_scrape",
                "actor_ids": actor_ids,
                "use_cache": sorted(k.value for k in cache_kinds),
            },
        )
        if not actor_ids:
            return {"error": "actor_ids 为空"}
        task_ids: list[int] = []
        missing = 0
        for actor_id in actor_ids:
            actor = await ctx.deps.repo.get_actor(actor_id)
            if actor is None:
                missing += 1
                continue
            task = await ctx.deps.repo.create_task(
                task_type=TaskType.ACTOR_SCRAPE, payload=ActorScrapePayload(actor_id=actor_id, use_cache=cache_kinds)
            )
            assert task.id is not None
            task_ids.append(task.id)
        out = {"submitted": len(task_ids), "missing": missing, "task_ids": task_ids}
        trace_tool(ctx, "tool_result", {"tool": "enqueue_actor_scrape", "result": out})
        return out

    return cap
