"""按用户选择从来源 raw 拼出 ``update_metadata`` 的 updates.

API 与 Agent 共用; 无 I/O.
"""

from .engine import RAW_TO_DB_FIELD, SCALAR_FIELD_NAMES


def compute_merge_updates(
    raw: dict[str, dict[str, object]], field_sources: dict[str, str], selections: dict[str, str]
) -> dict[str, object]:
    """从 raw 与 selections (字段 → 来源) 计算合并 updates.

    重命名字段以 ``{source: value}`` 保留来源; 标量来源并入 ``field_sources``.
    未知来源/字段抛 ``ValueError``; 值为 ``None`` 的项跳过.
    """
    updates: dict[str, object] = {}
    field_sources_updates: dict[str, str] = {}

    for field, source in selections.items():
        if source not in raw:
            raise ValueError(f"source '{source}' not found in raw data")
        if field not in raw[source]:
            raise ValueError(f"field '{field}' not found for source '{source}'")

        value = raw[source][field]
        if value is None:
            continue

        db_field = RAW_TO_DB_FIELD.get(field, field)
        updates[db_field] = {source: value} if db_field != field else value

        if field in SCALAR_FIELD_NAMES:
            field_sources_updates[field] = source

    if field_sources_updates:
        updates["field_sources"] = {**field_sources, **field_sources_updates}

    return updates
