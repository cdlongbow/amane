"""聚合引擎见 amane.aggregate."""

from collections.abc import Iterable, Mapping
from typing import TYPE_CHECKING, Protocol

from structlog.contextvars import bind_contextvars

from ..aggregate import SCALAR_FIELDS, AggregatedMetadata, CrawlerLike, FieldLanguage, aggregate, compile_priority
from ..crawlers.base import Crawler
from ..crawlers.models import SearchQuery
from ..crawlers.site_roles import MULTI_LANGUAGE_SOURCE_IDS
from ..db.models import TaskType
from ..enums import MetadataField
from ..media import materialize_images
from ..observability import current
from ._common import ensure_oshash, finalize_media_file
from .models import ActorScrapePayload, CacheKind, ScrapePayload, ScrapeResult
from .protocol import FollowupTask, TaskHandler, TaskResult

if TYPE_CHECKING:
    from ..config import HotSettings
    from ..db.repository import Repository
    from ..llm import Translator
    from ..media import ResourceStore
    from ..net.http import WebClient

# 进度: 聚合按已满足标量字段计数; 其后固定两步 (物化图片 / 持久化).
_PROGRESS_POST_STEPS = 2


def _crawlers_need_oshash(crawlers: Mapping[str, CrawlerLike]) -> bool:
    """本次实际实例化的爬虫是否声明需要文件指纹 (Stash 系)."""
    return any(isinstance(crawler, Crawler) and type(crawler).profile().uses_file_hash for crawler in crawlers.values())


class CrawlerFactoryLike(Protocol):
    """CrawlerFactory 的结构化类型 - 用于测试中的 duck typing."""

    async def get_crawlers(self, names: Iterable[str]) -> dict[str, CrawlerLike]: ...


class ScrapeHandler(TaskHandler[ScrapePayload, ScrapeResult]):
    """处理 SCRAPE 任务 - 编排多源爬取并写入元数据.

    流程:
        1. 按 content_type 取 content_routes 有序链 (资格真值)
        2. 实例化爬虫 (CrawlerFactory; 仅 route 内站点)
        3. 逐字段聚合结果 (aggregate; per-site 复用既有 raw 快照)
        4. 物化图片到 Resource 目录
        5. 持久化元数据到数据库 (Repository.upsert_metadata)
        6. 关联 MediaFile -> Metadata (若有 media_file_id)
    库目录落盘由 ORGANIZE 负责, 本任务不移动文件.
    """

    def __init__(
        self,
        repo: Repository,
        factory: CrawlerFactoryLike,
        resource_store: ResourceStore,
        pipeline_config: HotSettings,
        web_client: WebClient | None = None,
        translator: Translator | None = None,
        multi_language_sources: frozenset[str] | None = None,
    ):
        super().__init__(payload_t=ScrapePayload, result_t=ScrapeResult)
        self._repo = repo
        self._factory = factory
        self._config = pipeline_config
        self._web_client = web_client
        self._resource_store = resource_store
        self._translator = translator
        self._multi_language_sources = multi_language_sources or MULTI_LANGUAGE_SOURCE_IDS

    async def handle(self, payload: ScrapePayload) -> TaskResult[ScrapeResult]:
        bind_contextvars(number=payload.number)

        content_type = payload.content_type
        progress_total = len(SCALAR_FIELDS) + _PROGRESS_POST_STEPS
        rec = current()

        use_metadata_cache = CacheKind.metadata in payload.use_cache
        db_data = await self._repo.get_metadata_by_number(payload.number) if use_metadata_cache else None
        if db_data is not None and db_data.raw:
            rec.write_raw_cache(db_data.raw)

        route = self._config.scraping.content_routes.get(content_type)
        if not route:
            rec.warning("no eligible crawlers for content type", content_type=content_type)
            return TaskResult(success=False, error=f"No eligible crawlers for content type {content_type}")
        rec.info("scraping started", content_type=str(content_type), crawlers=route)
        rec.update_summary(eligible_sites=[str(s) for s in route])

        crawlers = await self._factory.get_crawlers(route)
        if not crawlers:
            current().warning("no crawlers available", requested=route)
            return TaskResult(success=False, error=f"No crawlers available for {payload.number}")

        file = None
        if payload.media_file_id:
            file = await self._repo.get_media_file(media_id=payload.media_file_id)

        file_hash = file.oshash if file else None
        if file is not None and file_hash is None and _crawlers_need_oshash(crawlers):
            file_hash = await ensure_oshash(self._repo, file)

        q = SearchQuery(
            payload.number,
            file.path if file else None,
            file_hash,
            payload.content_type,
        )

        field_priority = compile_priority(route, self._config.scraping.field_priority)
        field_language = self._config.scraping.field_language

        await self.report_progress(0, progress_total, "fetch")

        async def _on_fetch_progress(current: int, _total: int, message: str = "") -> None:
            # aggregate 上报的 current 是已满足标量字段数; 分母由 handler 统一为含后续步骤的 total.
            await self.report_progress(current, progress_total, message)

        result = await aggregate(
            q,
            crawlers,
            field_priority,
            field_language,
            db_data.raw if db_data else None,
            on_progress=_on_fetch_progress,
            multi_lang_sites=self._multi_language_sources,
        )

        # 站点结果已由引擎 _fetch_one 逐条上报到 summary.outcomes; 这里只记录调度顺序.
        rec.update_summary(sites_queried=list(result.sites_queried))

        if not result.field_sources:
            current().warning("no data found from any source", failed_sites=result.failed_sites)
            return TaskResult(success=False, error=f"No metadata found for {payload.number}")

        # 抓取阶段结束: 分子抬到标量总分, 留给后续 materialize/persist 两步.
        await self.report_progress(len(SCALAR_FIELDS), progress_total, "fetch")

        # 翻译文本字段 (聚合后, 持久化前): 机会主义, 失败不阻断刮削.
        if self._translator is not None:
            await self._translate_metadata(result.metadata, field_language, CacheKind.trans in payload.use_cache)

        # 物化资源 (下载到 Resource + 裁剪 + 急切超分), 得到应写入 metadata 的 URL.
        # 失败不阻断 (机会主义). 库目录落盘由 ORGANIZE 负责.
        poster_out = result.metadata.poster_urls
        thumb_out = result.metadata.thumb_urls
        trailer_out = result.metadata.trailer_urls
        if self._web_client is not None:
            try:
                materialized = await materialize_images(
                    result.metadata.poster_urls,
                    result.metadata.thumb_urls,
                    result.metadata.trailer_urls,
                    self._resource_store,
                    self._web_client,
                    self._config,
                    self._resource_store.data_dir,
                    extrafanart_urls=result.metadata.extrafanart_urls,
                )
                poster_out = materialized.poster_urls
                thumb_out = materialized.thumb_urls
                trailer_out = materialized.trailer_urls
            except Exception:
                current().warning("image materialization failed, keeping raw urls", number=payload.number)

        await self.report_progress(len(SCALAR_FIELDS) + 1, progress_total, "materialize")

        meta = await self._repo.upsert_metadata(
            number=payload.number,
            title=result.metadata.title,
            actors=result.metadata.actors,
            studio=result.metadata.studio,
            publisher=result.metadata.publisher,
            release=result.metadata.release,
            runtime=result.metadata.runtime,
            tags=result.metadata.tags,
            series=result.metadata.series,
            plot=result.metadata.plot,
            directors=result.metadata.directors,
            poster_urls=poster_out,
            thumb_urls=thumb_out,
            trailer_urls=trailer_out,
            extrafanart_urls=result.metadata.extrafanart_urls,
            scores={s.site: s.score for s in result.metadata.scores},
            external_ids=result.metadata.external_ids,
            source_urls=result.metadata.source_urls,
            field_sources=result.field_sources,
            raw=result.raw,
        )

        await finalize_media_file(self._repo, payload.media_file_id, meta.id)

        actor_followups = await self._actor_scrape_followups(meta.actors)

        await self.report_progress(progress_total, progress_total, "done")

        current().info(
            "scrape completed",
            metadata_id=meta.id,
            sites_used=len(set(result.field_sources.values())),
            fields_resolved=len(result.field_sources),
            failed_sites=result.failed_sites,
            actor_followups=len(actor_followups),
        )

        assert meta.id is not None
        return TaskResult(
            success=True,
            result=ScrapeResult(
                metadata_id=meta.id, field_sources=result.field_sources, failed_sites=result.failed_sites
            ),
            followups=actor_followups,
        )

    async def _actor_scrape_followups(self, actor_names: list[str]) -> list[FollowupTask]:
        """链式: 为影片演员未刮削者描述 ACTOR_SCRAPE 后继 (机会主义, 失败不阻断主流程).

        - ``meta.actors`` 已是 FacetRule 应用后的规范名, 与 sync_metadata_facets 创建的
          Actor 实体一一对应, 缺失名 (理论上不存在) 静默跳过.
        - 跳过 ``Actor.raw`` 非空者: 已刮过, 站点级 raw 快照可复用, 无需重刮.
        - ``priority=-1`` 低于默认 0: 批量 REFRESH 产生的演员任务不抢影片任务.
        """
        if not self._config.actor_scraping.auto_scrape or not actor_names:
            return []
        try:
            actors = await self._repo.get_actors_by_names(actor_names)
            return [
                FollowupTask(
                    key=f"actor-scrape:{actor.id}",
                    task_type=TaskType.ACTOR_SCRAPE,
                    payload=ActorScrapePayload(actor_id=actor.id).model_dump(mode="json"),
                    priority=-1,
                )
                for actor in actors
                if actor.id is not None and not actor.raw
            ]
        except Exception:
            current().warning("failed to build actor scrape followups", actors=actor_names)
            return []

    async def _translate_metadata(
        self, metadata: AggregatedMetadata, field_language: FieldLanguage, use_cache: bool
    ) -> None:
        """就地翻译 metadata 的文本字段至 field_language 指定语言.

        仅处理 llm.translate_fields 中受支持的文本标量字段 (当前 title/plot).
        每字段独立机会主义: 单字段失败不影响其余, 全程不抛.
        ``use_cache`` 为 False 时跳过译文缓存读取 (强制重译), 但仍刷新缓存.
        """
        assert self._translator is not None
        fields = self._config.llm.translate_fields
        if MetadataField.TITLE in fields and metadata.title:
            translated = await self._translate_field(metadata.title, field_language, MetadataField.TITLE, use_cache)
            if translated:
                metadata.title = translated
        if MetadataField.PLOT in fields and metadata.plot:
            translated = await self._translate_field(metadata.plot, field_language, MetadataField.PLOT, use_cache)
            if translated:
                metadata.plot = translated

    async def _translate_field(
        self, value: str, field_language: FieldLanguage, field: MetadataField, use_cache: bool
    ) -> str | None:
        """翻译单字段, 吞掉异常 (机会主义). 无目标语言或失败时返回 None."""
        assert self._translator is not None
        target = field_language.get(field)
        if target is None:
            return None
        try:
            result = await self._translator.translate(value, target, field, use_cache=use_cache)
        except Exception:
            current().warning("translation failed, keeping original", field=str(field))
            return None
        if result:
            current().debug("field translated", field=str(field), target=str(target))
        return result
