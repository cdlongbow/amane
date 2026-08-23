from pydantic import BaseModel


class DesktopResponse(BaseModel):
    """菜单栏 / 托盘 UI 的 IPC 契约: 桌面进程需要的最小静态信息."""

    version: str
    data_dir: str
    supervised: bool = False


class ReleaseResponse(BaseModel):
    current: str
    latest: str | None
    html_url: str | None
    newer: bool
