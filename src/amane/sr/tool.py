from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping


class SrTool(StrEnum):
    """支持的图像超分工具 (底层二进制)."""

    REALESRGAN = "realesrgan"
    WAIFU2X = "waifu2x"


class SrPreset(StrEnum):
    REALESR_PHOTO_4X = "realesr-photo-4x"
    """Real-ESRGAN 通用照片模型, 4x 原生倍率, 无降噪."""
    WAIFU_PHOTO_2X = "waifu-photo-2x"
    """waifu2x 照片模型, 2x 原生倍率, 无降噪."""


@dataclass(frozen=True, slots=True)
class PresetMeta:
    """预设的完整参数解析结果."""

    tool: SrTool
    """使用的超分工具."""
    model: str
    scale: int
    """放大倍率."""
    noise_level: int
    """降噪级别."""


# 预设 → 参数的映射表.
_PRESET_META: Mapping[SrPreset, PresetMeta] = {
    SrPreset.REALESR_PHOTO_4X: PresetMeta(
        tool=SrTool.REALESRGAN,
        model="realesrgan-x4plus",
        scale=4,
        noise_level=-1,
    ),
    SrPreset.WAIFU_PHOTO_2X: PresetMeta(
        tool=SrTool.WAIFU2X,
        model="models-upconv_7_photo",
        scale=2,
        noise_level=-1,
    ),
}


def get_preset_meta(preset: SrPreset) -> PresetMeta:
    """获取预设的完整参数."""
    return _PRESET_META[preset]


@dataclass(frozen=True, slots=True)
class ToolMeta:
    """超分工具元数据."""

    binary_name: str
    default_model: str
    models: tuple[str, ...]
    """可用模型."""
    native_scale: int
    """原生放大倍率."""
    scales: tuple[int, ...]
    """可选放大倍率."""
    download_urls: dict[str, str] = field(default_factory=dict)
    """sys.platform → 下载 URL. key: darwin/linux/win32."""


_REALESRGAN_RELEASE = "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0"

_WAIFU2X_RELEASE = "https://github.com/nihui/waifu2x-ncnn-vulkan/releases/download/20250915"


_TOOL_META: Mapping[SrTool, ToolMeta] = {
    SrTool.REALESRGAN: ToolMeta(
        binary_name="realesrgan-ncnn-vulkan",
        default_model="realesrgan-x4plus",
        models=(
            "realesrgan-x4plus",
            "realesrgan-x4plus-anime",
            "realesr-animevideov3",
            "realesrnet-x4plus",
        ),
        native_scale=4,
        scales=(2, 3, 4),
        download_urls={
            "darwin": f"{_REALESRGAN_RELEASE}/realesrgan-ncnn-vulkan-20220424-macos.zip",
            "linux": f"{_REALESRGAN_RELEASE}/realesrgan-ncnn-vulkan-20220424-ubuntu.zip",
            "win32": f"{_REALESRGAN_RELEASE}/realesrgan-ncnn-vulkan-20220424-windows.zip",
        },
    ),
    SrTool.WAIFU2X: ToolMeta(
        binary_name="waifu2x-ncnn-vulkan",
        default_model="models-upconv_7_photo",
        models=(
            "models-upconv_7_photo",
            "models-cunet",
            "models-upconv_7_anime_style_art_rgb",
        ),
        native_scale=2,
        scales=(1, 2, 4, 8, 16, 32),
        download_urls={
            "darwin": f"{_WAIFU2X_RELEASE}/waifu2x-ncnn-vulkan-20250915-macos.zip",
            "linux": f"{_WAIFU2X_RELEASE}/waifu2x-ncnn-vulkan-20250915-linux.zip",
            "win32": f"{_WAIFU2X_RELEASE}/waifu2x-ncnn-vulkan-20250915-windows.zip",
        },
    ),
}


def get_tool_meta(tool: SrTool) -> ToolMeta:
    """获取工具的静态元数据."""
    return _TOOL_META[tool]
