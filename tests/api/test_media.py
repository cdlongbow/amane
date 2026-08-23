"""/media 端点测试"""

from typing import TYPE_CHECKING

import pytest
import pytest_asyncio

from amane.db.models import MediaFileStatus

if TYPE_CHECKING:
    from httpx2 import AsyncClient

    from amane.db.repository import Repository


@pytest_asyncio.fixture(autouse=True)
async def _seed_library(repo: Repository) -> None:
    """FK 约束要求归属库存在; 这些测试以 library_id=1 创建 MediaFile."""
    if await repo.get_library(1) is None:
        await repo.create_library(name="default", path="/")


class TestListMedia:
    @pytest.mark.asyncio(loop_scope="function")
    async def test_empty_list(self, client: AsyncClient):
        resp = await client.get("media")
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["total"] == 0

    @pytest.mark.asyncio(loop_scope="function")
    async def test_list_with_data(self, client: AsyncClient, repo: Repository):
        await repo.create_media_file(library_id=1, path="/video/a.mp4", number="ABC-001")
        await repo.create_media_file(library_id=1, path="/video/b.mp4", number="DEF-002")

        resp = await client.get("media")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2

    @pytest.mark.asyncio(loop_scope="function")
    async def test_filter_by_status(self, client: AsyncClient, repo: Repository):
        m1 = await repo.create_media_file(library_id=1, path="/a.mp4")
        await repo.create_media_file(library_id=1, path="/b.mp4")
        assert m1.id is not None
        await repo.update_media_file(m1.id, status=MediaFileStatus.SCRAPED)

        resp = await client.get("media?status=pending")
        assert resp.json()["total"] == 1

    @pytest.mark.asyncio(loop_scope="function")
    async def test_pagination(self, client: AsyncClient, repo: Repository):
        for i in range(5):
            await repo.create_media_file(library_id=1, path=f"/video/{i}.mp4")

        resp = await client.get("media?limit=2&offset=0")
        data = resp.json()
        assert len(data["items"]) == 2
        assert data["total"] == 5

    @pytest.mark.asyncio(loop_scope="function")
    async def test_search_by_path(self, client: AsyncClient, repo: Repository):
        await repo.create_media_file(library_id=1, path="/video/a.mp4", number="ABC-001")
        await repo.create_media_file(library_id=1, path="/other/b.mkv", number="DEF-002")

        resp = await client.get("media?search=other")
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["path"] == "/other/b.mkv"

    @pytest.mark.asyncio(loop_scope="function")
    async def test_search_by_number(self, client: AsyncClient, repo: Repository):
        await repo.create_media_file(library_id=1, path="/video/a.mp4", number="ABC-001")
        await repo.create_media_file(library_id=1, path="/video/b.mp4", number="DEF-002")

        resp = await client.get("media?search=ABC")
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["number"] == "ABC-001"


class TestGetMedia:
    @pytest.mark.asyncio(loop_scope="function")
    async def test_get_existing(self, client: AsyncClient, repo: Repository):
        media = await repo.create_media_file(library_id=1, path="/video/x.mp4", number="XYZ-001")
        resp = await client.get(f"media/{media.id}")
        assert resp.status_code == 200
        assert resp.json()["number"] == "XYZ-001"

    @pytest.mark.asyncio(loop_scope="function")
    async def test_get_not_found(self, client: AsyncClient):
        resp = await client.get("media/9999")
        assert resp.status_code == 404


class TestUpdateMedia:
    @pytest.mark.asyncio(loop_scope="function")
    async def test_update_fields(self, client: AsyncClient, repo: Repository):
        media = await repo.create_media_file(library_id=1, path="/video/x.mp4", number="OLD-001")
        resp = await client.patch(f"media/{media.id}", json={"number": "NEW-001", "status": "scraped"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["number"] == "NEW-001"
        assert data["status"] == "scraped"

    @pytest.mark.asyncio(loop_scope="function")
    async def test_update_path_and_metadata_id(self, client: AsyncClient, repo: Repository):
        media = await repo.create_media_file(library_id=1, path="/video/x.mp4")
        meta = await repo.upsert_metadata(number="ABC-123")
        resp = await client.patch(f"media/{media.id}", json={"path": "/new/location/x.mp4", "metadata_id": meta.id})
        assert resp.status_code == 200
        data = resp.json()
        assert data["path"] == "/new/location/x.mp4"
        assert data["metadata_id"] == meta.id

    @pytest.mark.asyncio(loop_scope="function")
    async def test_not_found(self, client: AsyncClient):
        resp = await client.patch("media/9999", json={"number": "X"})
        assert resp.status_code == 404

    @pytest.mark.asyncio(loop_scope="function")
    async def test_empty_body_rejected(self, client: AsyncClient, repo: Repository):
        media = await repo.create_media_file(library_id=1, path="/video/x.mp4")
        resp = await client.patch(f"media/{media.id}", json={})
        assert resp.status_code == 422

    @pytest.mark.asyncio(loop_scope="function")
    async def test_extra_field_ignored(self, client: AsyncClient, repo: Repository):
        """PATCH 的 cast 通过 exclude_unset 过滤 - 未知字段应被 Pydantic 静默丢弃."""
        media = await repo.create_media_file(library_id=1, path="/video/x.mp4", number="OLD")
        resp = await client.patch(f"media/{media.id}", json={"number": "NEW", "unknown_field": "should_be_ignored"})
        assert resp.status_code == 200
        assert resp.json()["number"] == "NEW"

    @pytest.mark.parametrize(
        "bad_payload", [{"status": "invalid_status"}, {"number": 12345}], ids=["invalid_status", "number_int"]
    )
    @pytest.mark.asyncio(loop_scope="function")
    async def test_wrong_type_rejected(self, client: AsyncClient, repo: Repository, bad_payload):
        media = await repo.create_media_file(library_id=1, path="/video/x.mp4")
        resp = await client.patch(f"media/{media.id}", json=bad_payload)
        assert resp.status_code == 422


class TestDeleteMedia:
    @pytest.mark.asyncio(loop_scope="function")
    async def test_delete(self, client: AsyncClient, repo: Repository):
        media = await repo.create_media_file(library_id=1, path="/video/x.mp4")
        resp = await client.delete(f"media/{media.id}")
        assert resp.status_code == 204

    @pytest.mark.asyncio(loop_scope="function")
    async def test_not_found(self, client: AsyncClient):
        resp = await client.delete("media/9999")
        assert resp.status_code == 404
