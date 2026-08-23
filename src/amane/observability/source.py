"""一次来源调用的边界: catch + 写入站点 outcome. 爬虫 / 插件不 import 本模块."""

from collections.abc import Awaitable, Callable

from ..net.errors import FailureReason, SourceError
from .models import SiteOutcomeKind
from .recorder import current


async def invoke_source[T](source_id: str, fetch: Callable[[], Awaitable[T | None]]) -> T | None:
    """执行一次来源 fetch, 把结果记进当前任务 Recorder.

    - 有数据 → OK
    - None → no_usable_metadata
    - SourceError → 异常上的 reason
    - 其它 Exception → unexpected (继续其它源, 不炸任务)
    """
    rec = current()
    try:
        result = await fetch()
    except SourceError as exc:
        rec.record_site_outcome(
            site=source_id,
            outcome=SiteOutcomeKind.FAILED,
            reason=exc.reason,
            http_status=exc.http_status,
            detail=exc.detail,
        )
        return None
    except Exception:
        rec.exception("source fetch failed", source=source_id)
        rec.record_site_outcome(site=source_id, outcome=SiteOutcomeKind.FAILED, reason=FailureReason.UNEXPECTED)
        return None
    if result is None:
        rec.record_site_outcome(site=source_id, outcome=SiteOutcomeKind.FAILED, reason=FailureReason.NO_USABLE_METADATA)
        return None
    rec.record_site_outcome(site=source_id, outcome=SiteOutcomeKind.OK)
    return result
