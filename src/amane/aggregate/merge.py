"""按用户选择从来源 raw 算出 ``update_metadata`` 的 updates. 无 I/O."""

from .engine import RAW_TO_DB_FIELD, SCALAR_FIELD_NAMES


def compute_merge_updates(
    raw: dict[str, dict[str, object]], field_sources: dict[str, str], selections: dict[str, str]
) -> dict[str, object]:
    """未知来源或字段抛 ``ValueError``; 值为 ``None`` 的项跳过.

    重命名字段以 ``{source: value}`` 保留来源; 标量来源并入 ``field_sources``.
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
