"""分类索引 / 用户注解 API 测试."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from httpx2 import AsyncClient

    from amane.db.repository import Repository


class TestFacetsApi:
    @pytest.mark.asyncio(loop_scope="function")
    async def test_list_and_filter(self, client: AsyncClient, repo: Repository) -> None:
        await repo.upsert_metadata(number="F-001", actors=["Alice"], studio="StudioX", tags=["hot"])
        resp = await client.get("facets/actor")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        actor_id = next(i["id"] for i in data["items"] if i["name"] == "Alice")

        resp = await client.get(f"metadata?actor_id={actor_id}")
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

        await repo.upsert_metadata(number="F-002", actors=["Alice", "Bob"])
        resp = await client.get("facets/actor")
        bob_id = next(i["id"] for i in resp.json()["items"] if i["name"] == "Bob")
        resp = await client.get(f"metadata?actor_id={actor_id}&actor_id={bob_id}")
        assert resp.status_code == 200
        assert resp.json()["total"] == 1
        assert resp.json()["items"][0]["number"] == "F-002"

        resp = await client.get(f"facets/actor/{actor_id}")
        assert resp.status_code == 200
        catalog = resp.json()
        assert set(catalog) == {"id", "name", "count"}
        assert catalog["id"] == actor_id
        assert catalog["name"] == "Alice"
        assert catalog["count"] >= 1

    @pytest.mark.asyncio(loop_scope="function")
    async def test_unknown_kind(self, client: AsyncClient) -> None:
        resp = await client.get("facets/not_a_kind")
        assert resp.status_code == 422


class TestUserTagsApi:
    @pytest.mark.asyncio(loop_scope="function")
    async def test_crud_and_attach(self, client: AsyncClient, repo: Repository) -> None:
        meta = await repo.upsert_metadata(number="UT-API-1")
        assert meta.id is not None

        resp = await client.post("facets/user_tag", json={"name": "watched"})
        assert resp.status_code == 201
        tag_id = resp.json()["id"]

        resp = await client.put(f"metadata/{meta.id}/user-tags/{tag_id}")
        assert resp.status_code == 204

        resp = await client.get(f"metadata/{meta.id}")
        assert resp.status_code == 200
        assert any(t["name"] == "watched" for t in resp.json()["user_tags"])

        resp = await client.delete(f"metadata/{meta.id}/user-tags/{tag_id}")
        assert resp.status_code == 204

        resp = await client.post("facets/user_tag", json={"name": "watched"})
        assert resp.status_code == 409

        denied = await client.post("facets/studio", json={"name": "Nope"})
        assert denied.status_code == 405


class TestCommentsApi:
    @pytest.mark.asyncio(loop_scope="function")
    async def test_comment_lifecycle(self, client: AsyncClient, repo: Repository) -> None:
        meta = await repo.upsert_metadata(number="CM-API-1")
        assert meta.id is not None

        resp = await client.post(f"metadata/{meta.id}/comments", json={"body": "nice"})
        assert resp.status_code == 201
        comment_id = resp.json()["id"]

        detail = await client.get(f"metadata/{meta.id}")
        assert detail.status_code == 200
        assert len(detail.json()["comments"]) == 1

        resp = await client.patch(f"comments/{comment_id}", json={"body": "updated"})
        assert resp.status_code == 200
        assert resp.json()["body"] == "updated"

        resp = await client.delete(f"comments/{comment_id}")
        assert resp.status_code == 204

        detail = await client.get(f"metadata/{meta.id}")
        assert detail.json()["comments"] == []
