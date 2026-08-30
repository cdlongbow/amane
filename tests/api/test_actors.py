"""演员浏览 API 测试. 字段筛选 SQL 见 tests/db/test_actor_browse.py."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from amane.db.models import FacetKind

if TYPE_CHECKING:
    from httpx2 import AsyncClient

    from amane.db.repository import Repository


class TestActorsApi:
    @pytest.mark.asyncio(loop_scope="function")
    async def test_list_detail_scrape_and_patch(self, client: AsyncClient, repo: Repository, stop_worker: None) -> None:
        await repo.upsert_metadata(number="ACT-BR-1", actors=["EmptyOne", "FilledOne"])
        actors, _ = await repo.list_facets(FacetKind.ACTOR)
        filled_id = next(a.id for a in actors if a.name == "FilledOne")
        assert filled_id is not None

        filled = await repo.get_actor(filled_id)
        assert filled is not None
        filled.birthday = "1991-01-01"
        filled.height = 160
        filled.image_urls = ["https://img.example/a.jpg"]
        filled.overview = "bio-not-for-list"
        await repo.save_actor(filled, aliases=["HiddenFromList"])

        resp = await client.get("actors")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] >= 2
        names = {i["name"] for i in body["items"]}
        assert "EmptyOne" in names and "FilledOne" in names
        listed = next(i for i in body["items"] if i["id"] == filled_id)
        assert listed["overview"] is None
        assert listed["aliases"] == []
        assert listed["image_urls"] == ["https://img.example/a.jpg"]

        detail = await client.get(f"actors/{filled_id}")
        assert detail.status_code == 200
        assert detail.json()["birthday"] == "1991-01-01"
        assert detail.json()["gender"] == "unknown"
        assert detail.json()["count"] >= 1
        assert detail.json()["overview"] == "bio-not-for-list"
        assert detail.json()["aliases"] == ["HiddenFromList"]
        assert "raw" in detail.json()

        patched = await client.patch(
            f"actors/{filled_id}",
            json={
                "overview": "edited bio",
                "gender": "female",
                "image_urls": ["https://img.example/b.jpg", "https://img.example/a.jpg"],
                "birthday": None,
            },
        )
        assert patched.status_code == 200
        body = patched.json()
        assert body["overview"] == "edited bio"
        assert body["gender"] == "female"
        assert body["image_urls"][0] == "https://img.example/b.jpg"
        assert body["birthday"] is None

        empty_patch = await client.patch(f"actors/{filled_id}", json={})
        assert empty_patch.status_code == 422

        scrape = await client.post(f"actors/{filled_id}/scrape")
        assert scrape.status_code == 202
        assert scrape.json()["type"] == "actor_scrape"
        assert scrape.json()["payload"]["actor_id"] == filled_id
        assert set(scrape.json()["payload"]["use_cache"]) == {"metadata", "trans"}

        force = await client.post(f"actors/{filled_id}/scrape", json={"use_cache": []})
        assert force.status_code == 202
        assert force.json()["id"] == scrape.json()["id"]

        missing = await client.get("actors/99999")
        assert missing.status_code == 404

        missing_patch = await client.patch("actors/99999", json={"overview": "x"})
        assert missing_patch.status_code == 404

        bad_bday = await client.patch(f"actors/{filled_id}", json={"birthday": "not-a-date"})
        assert bad_bday.status_code == 422

        norm_bday = await client.patch(f"actors/{filled_id}", json={"birthday": "1991年1月1日"})
        assert norm_bday.status_code == 200
        assert norm_bday.json()["birthday"] == "1991-01-01"

        inverted = await client.get("actors", params={"height_min": 200, "height_max": 150})
        assert inverted.status_code == 422
