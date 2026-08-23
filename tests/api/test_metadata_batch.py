"""/metadata/batch/* 端点测试"""

from typing import TYPE_CHECKING

import pytest
import pytest_asyncio

from amane.db.models import MediaFileStatus, TaskType

if TYPE_CHECKING:
    from httpx2 import AsyncClient

    from amane.db.repository import Repository


@pytest_asyncio.fixture(autouse=True)
async def _seed_library(repo: Repository) -> None:
    """FK 约束要求归属库存在; 这些测试以 library_id=1 创建 MediaFile."""
    if await repo.get_library(1) is None:
        await repo.create_library(name="default", path="/")


class TestBatchDeleteMetadata:
    @pytest.mark.asyncio(loop_scope="function")
    async def test_deletes_existing_and_counts_missing(self, client: AsyncClient, repo: Repository):
        m1 = await repo.upsert_metadata(number="BD-001")
        m2 = await repo.upsert_metadata(number="BD-002")
        assert m1.id is not None
        assert m2.id is not None

        resp = await client.post("metadata/batch/delete", json={"ids": [m1.id, m2.id, 9999]})
        assert resp.status_code == 200
        data = resp.json()
        assert data == {"deleted": 2, "missing": 1}

        assert await repo.get_metadata(m1.id) is None
        assert await repo.get_metadata(m2.id) is None

    @pytest.mark.asyncio(loop_scope="function")
    async def test_cascades_media_file_nullify(self, client: AsyncClient, repo: Repository):
        """批量删除对每条记录的级联行为与单条删除一致."""
        meta = await repo.upsert_metadata(number="BD-003")
        assert meta.id is not None
        media = await repo.create_media_file(library_id=1, path="/video/BD-003.mp4", number="BD-003")
        assert media.id is not None
        await repo.update_media_file(media.id, status=MediaFileStatus.SCRAPED, metadata_id=meta.id)

        resp = await client.post("metadata/batch/delete", json={"ids": [meta.id]})
        assert resp.status_code == 200
        assert resp.json() == {"deleted": 1, "missing": 0}

        updated = await repo.get_media_file(media.id)
        assert updated is not None
        assert updated.metadata_id is None
        assert updated.status == MediaFileStatus.PENDING

    @pytest.mark.asyncio(loop_scope="function")
    async def test_all_missing(self, client: AsyncClient):
        resp = await client.post("metadata/batch/delete", json={"ids": [9999, 8888]})
        assert resp.status_code == 200
        assert resp.json() == {"deleted": 0, "missing": 2}

    @pytest.mark.asyncio(loop_scope="function")
    async def test_empty_ids_rejected(self, client: AsyncClient):
        resp = await client.post("metadata/batch/delete", json={"ids": []})
        assert resp.status_code == 422


class TestBatchScrapeMetadata:
    @pytest.mark.asyncio(loop_scope="function")
    async def test_submits_tasks_for_existing_and_counts_missing(
        self, client: AsyncClient, repo: Repository, stop_worker: None
    ):
        m1 = await repo.upsert_metadata(number="BS-001")
        m2 = await repo.upsert_metadata(number="BS-002")
        assert m1.id is not None
        assert m2.id is not None

        resp = await client.post("metadata/batch/scrape", json={"ids": [m1.id, m2.id, 9999]})
        assert resp.status_code == 202
        data = resp.json()
        assert data["submitted"] == 2
        assert data["missing"] == 1
        assert len(data["task_ids"]) == 2

        numbers = set()
        for task_id in data["task_ids"]:
            task = await repo.get_task(task_id)
            assert task is not None
            assert task.type == TaskType.SCRAPE
            numbers.add(task.payload["number"])
        assert numbers == {"BS-001", "BS-002"}

    @pytest.mark.asyncio(loop_scope="function")
    async def test_default_scrape_options(self, client: AsyncClient, repo: Repository, stop_worker: None):
        meta = await repo.upsert_metadata(number="BS-003")
        assert meta.id is not None

        resp = await client.post("metadata/batch/scrape", json={"ids": [meta.id]})
        assert resp.status_code == 202
        task_id = resp.json()["task_ids"][0]
        task = await repo.get_task(task_id)
        assert task is not None
        assert task.payload["content_type"] == "censored"
        assert set(task.payload["use_cache"]) == {"metadata", "trans"}

    @pytest.mark.asyncio(loop_scope="function")
    async def test_custom_scrape_options(self, client: AsyncClient, repo: Repository, stop_worker: None):
        meta = await repo.upsert_metadata(number="BS-004")
        assert meta.id is not None

        resp = await client.post(
            "metadata/batch/scrape", json={"ids": [meta.id], "content_type": "uncensored", "use_cache": []}
        )
        assert resp.status_code == 202
        task_id = resp.json()["task_ids"][0]
        task = await repo.get_task(task_id)
        assert task is not None
        assert task.payload["content_type"] == "uncensored"
        assert task.payload["use_cache"] == []

    @pytest.mark.asyncio(loop_scope="function")
    async def test_all_missing(self, client: AsyncClient, stop_worker: None):
        resp = await client.post("metadata/batch/scrape", json={"ids": [9999]})
        assert resp.status_code == 202
        data = resp.json()
        assert data == {"submitted": 0, "missing": 1, "task_ids": []}

    @pytest.mark.asyncio(loop_scope="function")
    async def test_empty_ids_rejected(self, client: AsyncClient):
        resp = await client.post("metadata/batch/scrape", json={"ids": []})
        assert resp.status_code == 422


class TestBatchUserTags:
    @pytest.mark.asyncio(loop_scope="function")
    async def test_attach_batch(self, client: AsyncClient, repo: Repository):
        tag = await repo.create_user_tag("watched")
        assert tag.id is not None
        m1 = await repo.upsert_metadata(number="BT-001")
        m2 = await repo.upsert_metadata(number="BT-002")
        assert m1.id is not None
        assert m2.id is not None

        resp = await client.post(
            "metadata/batch/user-tags", json={"ids": [m1.id, m2.id, 9999], "user_tag_id": tag.id, "action": "attach"}
        )
        assert resp.status_code == 200
        assert resp.json() == {"affected": 2, "missing": 1}

        detail1 = await client.get(f"metadata/{m1.id}")
        assert any(t["name"] == "watched" for t in detail1.json()["user_tags"])
        detail2 = await client.get(f"metadata/{m2.id}")
        assert any(t["name"] == "watched" for t in detail2.json()["user_tags"])

    @pytest.mark.asyncio(loop_scope="function")
    async def test_attach_idempotent(self, client: AsyncClient, repo: Repository):
        """已挂载的重复 attach 仍计入 affected, 不报错."""
        tag = await repo.create_user_tag("dup")
        assert tag.id is not None
        meta = await repo.upsert_metadata(number="BT-003")
        assert meta.id is not None
        await repo.attach_user_tag(meta.id, tag.id)

        resp = await client.post(
            "metadata/batch/user-tags", json={"ids": [meta.id], "user_tag_id": tag.id, "action": "attach"}
        )
        assert resp.status_code == 200
        assert resp.json() == {"affected": 1, "missing": 0}

    @pytest.mark.asyncio(loop_scope="function")
    async def test_attach_missing_tag_counts_all_as_missing(self, client: AsyncClient, repo: Repository):
        meta = await repo.upsert_metadata(number="BT-004")
        assert meta.id is not None

        resp = await client.post(
            "metadata/batch/user-tags", json={"ids": [meta.id], "user_tag_id": 9999, "action": "attach"}
        )
        assert resp.status_code == 200
        assert resp.json() == {"affected": 0, "missing": 1}

    @pytest.mark.asyncio(loop_scope="function")
    async def test_detach_batch(self, client: AsyncClient, repo: Repository):
        tag = await repo.create_user_tag("to-remove")
        assert tag.id is not None
        m1 = await repo.upsert_metadata(number="BT-005")
        m2 = await repo.upsert_metadata(number="BT-006")
        assert m1.id is not None
        assert m2.id is not None
        await repo.attach_user_tag(m1.id, tag.id)
        # m2 未挂载 -> 计入 missing

        resp = await client.post(
            "metadata/batch/user-tags", json={"ids": [m1.id, m2.id], "user_tag_id": tag.id, "action": "detach"}
        )
        assert resp.status_code == 200
        assert resp.json() == {"affected": 1, "missing": 1}

    @pytest.mark.asyncio(loop_scope="function")
    async def test_invalid_action_rejected(self, client: AsyncClient, repo: Repository):
        meta = await repo.upsert_metadata(number="BT-007")
        assert meta.id is not None
        resp = await client.post(
            "metadata/batch/user-tags", json={"ids": [meta.id], "user_tag_id": 1, "action": "bogus"}
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio(loop_scope="function")
    async def test_empty_ids_rejected(self, client: AsyncClient):
        resp = await client.post("metadata/batch/user-tags", json={"ids": [], "user_tag_id": 1, "action": "attach"})
        assert resp.status_code == 422
