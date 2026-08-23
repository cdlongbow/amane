"""测试 UPSCALE handler - 扫描资源就地超分, meta 去重."""

from typing import TYPE_CHECKING

import pytest
from PIL import Image

from amane.config import HotSettings
from amane.handlers import UpscaleHandler, UpscalePayload
from amane.handlers import upscale as upscale_mod
from amane.media import ResourceStore

if TYPE_CHECKING:
    from pathlib import Path


async def _seed_image(store: ResourceStore, url: str, size: tuple[int, int]) -> None:
    async def producer(dest: Path) -> bool:
        Image.new("RGB", size, "blue").save(dest)
        return True

    await store.acquire_derived(url, "crop", "0.7", producer)


@pytest.fixture
def _fake_sr(monkeypatch):
    from amane.sr.run import SrResult

    async def fake_run_sr(inp, out, cfg, data_dir, **kwargs):
        Image.new("RGB", (1600, 1076), "green").save(out)
        return SrResult(success=True, output=out)

    monkeypatch.setattr(upscale_mod, "run_SR", fake_run_sr)


@pytest.mark.asyncio
async def test_upscales_low_quality(resource_store: ResourceStore, _fake_sr):
    await _seed_image(resource_store, "https://s/small.jpg", (800, 538))  # max=800<1200 → 超分
    cfg = HotSettings()
    handler = UpscaleHandler(resource_store, cfg)
    result = await handler.handle(UpscalePayload())
    assert result.success
    assert result.result is not None
    assert result.result.upscaled == 1
    # 已打 sr 标记
    all_res = await resource_store.list_all()
    assert len(all_res) == 1
    res = await resource_store.get_by_url(all_res[0].url)
    assert res is not None and res.meta is not None and "sr" in res.meta


@pytest.mark.asyncio
async def test_skips_already_upscaled(resource_store: ResourceStore, _fake_sr):
    await _seed_image(resource_store, "https://s/small.jpg", (800, 538))
    handler = UpscaleHandler(resource_store, HotSettings())
    await handler.handle(UpscalePayload())  # 第一次超分
    result = await handler.handle(UpscalePayload())  # 第二次应全部跳过
    assert result.result is not None
    assert result.result.upscaled == 0
    assert result.result.skipped == 1


@pytest.mark.asyncio
async def test_skips_high_resolution(resource_store: ResourceStore, _fake_sr):
    await _seed_image(resource_store, "https://s/big.jpg", (2000, 1346))  # max=2000≥1200 → 跳过
    handler = UpscaleHandler(resource_store, HotSettings())
    result = await handler.handle(UpscalePayload())
    assert result.result is not None
    assert result.result.upscaled == 0
    assert result.result.skipped == 1


@pytest.mark.asyncio
async def test_empty_store(resource_store: ResourceStore):
    handler = UpscaleHandler(resource_store, HotSettings())
    result = await handler.handle(UpscalePayload())
    assert result.result is not None
    assert result.result.scanned == 0
    assert result.result.upscaled == 0


@pytest.mark.asyncio
async def test_limit_caps_batch(resource_store: ResourceStore, _fake_sr):
    for i in range(3):
        await _seed_image(resource_store, f"https://s/img{i}.jpg", (800, 538))
    handler = UpscaleHandler(resource_store, HotSettings())
    result = await handler.handle(UpscalePayload(limit=2))
    assert result.result is not None
    assert result.result.upscaled == 2  # 上限 2
