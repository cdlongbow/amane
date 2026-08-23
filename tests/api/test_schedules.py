"""/schedules 端点测试"""

from typing import TYPE_CHECKING

import pytest

from amane.db.models import RoutineType

if TYPE_CHECKING:
    from httpx2 import AsyncClient

    from amane.db.repository import Repository


class TestListSchedules:
    @pytest.mark.asyncio(loop_scope="function")
    async def test_empty(self, client: AsyncClient):
        resp = await client.get("schedules")
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["total"] == 0

    @pytest.mark.asyncio(loop_scope="function")
    async def test_with_items(self, client: AsyncClient, repo: Repository):
        await repo.create_schedule(cron="0 0 * * *", task_type=RoutineType.CLEANUP, payload={})
        await repo.create_schedule(cron="0 12 * * *", task_type=RoutineType.CLEANUP, payload={})
        resp = await client.get("schedules")
        assert resp.status_code == 200
        assert resp.json()["total"] == 2


class TestCreateSchedule:
    @pytest.mark.asyncio(loop_scope="function")
    async def test_create_cleanup(self, client: AsyncClient):
        resp = await client.post(
            "schedules",
            json={
                "cron": "0 */6 * * *",
                "submission": {"type": "cleanup", "remove_missing_files": False},
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["cron"] == "0 */6 * * *"
        assert data["task_type"] == "cleanup"
        assert data["enabled"] is True
        assert data["payload"]["remove_missing_files"] is False
        fetched = await client.get(f"schedules/{data['id']}")
        assert fetched.status_code == 200
        assert fetched.json()["id"] == data["id"]
        missing = await client.get("schedules/9999")
        assert missing.status_code == 404

    @pytest.mark.asyncio(loop_scope="function")
    async def test_create_with_name_and_disabled(self, client: AsyncClient):
        resp = await client.post(
            "schedules",
            json={
                "cron": "0 8 * * *",
                "name": "daily",
                "enabled": False,
                "submission": {"type": "cleanup"},
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "daily"
        assert data["enabled"] is False
        assert data["task_type"] == "cleanup"

    @pytest.mark.asyncio(loop_scope="function")
    async def test_create_upscale(self, client: AsyncClient):
        resp = await client.post(
            "schedules",
            json={
                "cron": "0 3 * * *",
                "submission": {"type": "upscale", "limit": 50},
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["task_type"] == "upscale"
        assert data["payload"]["limit"] == 50

    @pytest.mark.asyncio(loop_scope="function")
    async def test_invalid_cron_rejected(self, client: AsyncClient):
        resp = await client.post("schedules", json={"cron": "invalid", "submission": {"type": "cleanup"}})
        assert resp.status_code == 422

    @pytest.mark.asyncio(loop_scope="function")
    async def test_invalid_submission_type_rejected(self, client: AsyncClient):
        resp = await client.post("schedules", json={"cron": "0 * * * *", "submission": {"type": "invalid_type"}})
        assert resp.status_code == 422


class TestUpdateSchedule:
    @pytest.mark.asyncio(loop_scope="function")
    async def test_update_fields(self, client: AsyncClient, repo: Repository):
        sched = await repo.create_schedule(cron="0 0 * * *", task_type=RoutineType.CLEANUP, payload={}, name="old")
        resp = await client.patch(f"schedules/{sched.id}", json={"name": "updated", "enabled": False})
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "updated"
        assert data["enabled"] is False

    @pytest.mark.asyncio(loop_scope="function")
    async def test_update_not_found(self, client: AsyncClient):
        resp = await client.patch("schedules/9999", json={"name": "x"})
        assert resp.status_code == 404

    @pytest.mark.asyncio(loop_scope="function")
    async def test_update_invalid_cron(self, client: AsyncClient, repo: Repository):
        sched = await repo.create_schedule(cron="0 0 * * *", task_type=RoutineType.CLEANUP, payload={})
        resp = await client.patch(f"schedules/{sched.id}", json={"cron": "bad"})
        assert resp.status_code == 422

    @pytest.mark.asyncio(loop_scope="function")
    async def test_update_meta_only(self, client: AsyncClient, repo: Repository):
        """PUT 仅改 name/cron/enabled; 不支持改任务内容 (删除重建)."""
        sched = await repo.create_schedule(cron="0 0 * * *", task_type=RoutineType.CLEANUP, payload={}, name="old")
        resp = await client.patch(f"schedules/{sched.id}", json={"name": "renamed", "cron": "0 6 * * *"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "renamed"
        assert data["cron"] == "0 6 * * *"
        assert data["task_type"] == "cleanup"


class TestDeleteSchedule:
    @pytest.mark.asyncio(loop_scope="function")
    async def test_delete(self, client: AsyncClient, repo: Repository):
        sched = await repo.create_schedule(cron="0 0 * * *", task_type=RoutineType.CLEANUP, payload={})
        resp = await client.delete(f"schedules/{sched.id}")
        assert resp.status_code == 204

    @pytest.mark.asyncio(loop_scope="function")
    async def test_delete_not_found(self, client: AsyncClient):
        resp = await client.delete("schedules/9999")
        assert resp.status_code == 404


class TestTriggerSchedule:
    @pytest.mark.asyncio(loop_scope="function")
    async def test_trigger_sets_next_run(self, client: AsyncClient, repo: Repository):
        sched = await repo.create_schedule(cron="0 0 * * *", task_type=RoutineType.CLEANUP, payload={})
        resp = await client.post(f"schedules/{sched.id}/trigger")
        assert resp.status_code == 200
        data = resp.json()
        assert data["task_type"] == "cleanup"
        assert data["next_run"] is not None

    @pytest.mark.asyncio(loop_scope="function")
    async def test_trigger_not_found(self, client: AsyncClient):
        resp = await client.post("schedules/9999/trigger")
        assert resp.status_code == 404
