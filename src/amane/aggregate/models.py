from dataclasses import dataclass, field


@dataclass
class SourcedScore:
    """带来源的评分值. 各爬虫负责归一化到 0-100."""

    site: str
    score: float  # 0-100 归一化分数


@dataclass
class AggregatedMetadata:
    """
    多源聚合后的最终结构.

    标量字段按优先级选取单值 (与当前 Aggregator 逻辑一致).
    URL/评分等字段保留所有来源的数据.
    """

    number: str

    # === 标量字段: 按优先级选取单值 ===
    title: str | None = None
    studio: str | None = None
    publisher: str | None = None
    release: str | None = None
    runtime: int | None = None
    series: str | None = None
    plot: str | None = None
    actors: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    directors: list[str] = field(default_factory=list)

    # === 多源聚合字段: 按优先级排序的 URL 列表 ===
    poster_urls: list[str] = field(default_factory=list)
    thumb_urls: list[str] = field(default_factory=list)
    trailer_urls: list[str] = field(default_factory=list)

    # 剧照: 按站点分组 (单站点可返回多张)
    extrafanart_urls: dict[str, list[str]] = field(default_factory=dict)
    # {"javdb": [url1, url2, ...], "dmm": [url3, ...]}

    # 评分: 必须保留来源 (不同站点评分体系不同)
    scores: list[SourcedScore] = field(default_factory=list)

    # === 来源追踪 ===
    external_ids: dict[str, str] = field(default_factory=dict)
    """site_name -> external_id"""

    source_urls: dict[str, str] = field(default_factory=dict)
    """site_name -> detail_page_url"""

    field_sources: dict[str, str] = field(default_factory=dict)
    """标量字段来源: field_name -> site_name"""


@dataclass
class AggregateResult:
    """多源聚合的结果."""

    metadata: AggregatedMetadata
    """最终合并的元数据."""

    field_sources: dict[str, str]
    """映射 field_name -> 提供该值的 cache_key (标量字段)."""

    failed_sites: list[str]
    """聚合过程中失败的站点 (错误或无结果)."""

    sites_queried: list[str]
    """实际被查询的 cache_key (按顺序)."""

    raw: dict[str, dict]
    """各站原始 MediaMetadata 快照: {cache_key: {field: value, ...}}."""

    log: str
    """人类可读的聚合日志, 用于调试."""
