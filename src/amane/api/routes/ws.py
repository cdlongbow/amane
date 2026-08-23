import hmac
from typing import TYPE_CHECKING

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..middleware import API_TOKEN_COOKIE

if TYPE_CHECKING:
    from ...app.runtime import AppRuntime

router = APIRouter()


def _get_runtime(ws: WebSocket) -> AppRuntime:
    """从 app.state 获取运行时 (WebSocket 不支持 Depends 注入)"""
    return ws.app.state.runtime


@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket) -> None:
    """
    WebSocket 端点, 用于实时事件流.

    单向: 服务端 broadcast 事件, 客户端只读. 连接保持打开直到客户端断开.
    保活由 WebSocket 协议层 PING/PONG 帧处理 (uvicorn 发, 浏览器自动回), 无需应用层心跳.
    """
    runtime = _get_runtime(ws)
    # token 校验: 浏览器 WebSocket 无法自定义 header, 握手即 HTTP GET, 同源时
    # 自动携带 API_TOKEN_COOKIE (与 HTTP 中间件同一信任模型; None = 关闭).
    # token 不进 URL / 访问日志.
    token = runtime.api_token
    if token is not None and not hmac.compare_digest(ws.cookies.get(API_TOKEN_COOKIE, ""), token):
        await ws.close(code=1008)  # policy violation
        return
    event_bus = runtime.event_bus
    await event_bus.connect(ws)
    try:
        while True:
            # 客户端当前不发送任何消息; 仅借 receive 阻塞以感知断开
            await ws.receive_text()
    except WebSocketDisconnect:
        event_bus.disconnect(ws)
