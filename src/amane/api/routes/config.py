from typing import Any

import structlog
from fastapi import APIRouter, HTTPException
from pydantic import ValidationError

from ...config import HotSettings
from ...events import Event, EventType
from ..deps import ConfigDep, PluginManagerDep, RuntimeDep

logger = structlog.get_logger()

router = APIRouter(prefix="/config", tags=["config"])


@router.get("")
async def get_config(config: ConfigDep) -> HotSettings:
    """返回按分区分组的当前配置快照"""
    return config.hot


@router.patch("")
async def update_config(req: dict[str, Any], config: ConfigDep, runtime: RuntimeDep) -> HotSettings:
    """
    应用部分配置更新.

    验证补丁, 持久化到 TOML, 重建依赖的运行时对象 (worker, 网络客户端),
    并广播 config.updated 事件.
    """
    # 记录变更的字段
    changed_sections = list(req.keys())
    logger.info("config update requested", sections=changed_sections)

    # 先用当前会话的插件目录校验新路由和插件配置，再持久化。
    try:
        preview = config.preview(req)
        if runtime.plugin_manager is not None:
            runtime.plugin_manager.validate_hot_settings(preview, require_available=False)
        config.update(req)
    except (KeyError, ValidationError, ValueError) as e:
        logger.warning("config update rejected", error=str(e), sections=changed_sections)
        raise HTTPException(status_code=422, detail=str(e)) from e

    await runtime.apply_rebuild()
    logger.info("runtime rebuilt after config update", sections=changed_sections)

    # 广播配置变更事件
    await runtime.event_bus.broadcast(Event(type=EventType.LOG, data={"type": "config.updated"}))

    return config.hot


@router.get("/schema")
async def get_config_schema(plugin_manager: PluginManagerDep) -> dict:
    return plugin_manager.augment_config_schema(HotSettings.model_json_schema())
