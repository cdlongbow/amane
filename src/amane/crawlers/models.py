from dataclasses import dataclass
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field, field_validator

from ..utils.dates import normalize_calendar_date

if TYPE_CHECKING:
    from ..aggregate import AggregatedMetadata
    from ..enums import Language
    from ..parsing.file_info import ContentType


@dataclass
class SearchQuery:
    number: str
    file_path: str | None = None
    file_hash: str | None = None
    content_type: ContentType | None = None
    # 前序聚合中间结果; 由 Aggregator 注入, 测试可不传.
    partial_result: AggregatedMetadata | None = None
    raw_results: dict[str, MediaMetadata | None] | None = None


@dataclass
class FetchOptions:
    language: Language | None = None


class MediaMetadata(BaseModel):
    number: str
    title: str | None = None
    actors: list[str] = Field(default_factory=list)
    studio: str | None = None
    publisher: str | None = None
    release: str | None = None
    runtime: int | None = None
    tags: list[str] = Field(default_factory=list)
    series: str | None = None
    plot: str | None = None
    poster_urls: list[str] = Field(default_factory=list)
    thumb_urls: list[str] = Field(default_factory=list)
    trailer_urls: list[str] = Field(default_factory=list)
    score: float | None = None
    external_id: str | None = None
    source_url: str | None = None
    directors: list[str] = Field(default_factory=list)
    extrafanart: list[str] = Field(default_factory=list)

    @field_validator("release", mode="before")
    @classmethod
    def _normalize_release(cls, value: object) -> str | None:
        # 存库为 YYYY-MM-DD; ISO 日期时间只取日; 无法解析视为缺省.
        if value is None or value == "":
            return None
        if not isinstance(value, str):
            msg = "release must be a string"
            raise TypeError(msg)
        return normalize_calendar_date(value)
