"""分类索引 / 用户 tag / 评论 - repository 表测试."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from sqlalchemy.exc import IntegrityError

from amane.db.models import Actor, FacetKind, FacetSortField, MetadataActor, SortOrder

if TYPE_CHECKING:
    from amane.db.repository import Repository

pytestmark = pytest.mark.asyncio


class TestFacetSync:
    async def test_upsert_builds_actor_tag_studio_indexes(self, repo: Repository) -> None:
        meta = await repo.upsert_metadata(
            number="ABC-001",
            actors=["Alice", "Bob"],
            directors=["DirA"],
            tags=["tag1", "tag2"],
            studio="StudioX",
            publisher="PubY",
            series="SeriesZ",
        )
        assert meta.id is not None

        actors, total = await repo.list_facets(FacetKind.ACTOR)
        assert total == 2
        assert {a.name: a.count for a in actors} == {"Alice": 1, "Bob": 1}

        tags, _ = await repo.list_facets(FacetKind.TAG)
        assert {t.name for t in tags} == {"tag1", "tag2"}

        studios, _ = await repo.list_facets(FacetKind.STUDIO)
        assert studios[0].name == "StudioX" and studios[0].count == 1

    async def test_empty_actors_clears_junction(self, repo: Repository) -> None:
        meta = await repo.upsert_metadata(number="ABC-002", actors=["Alice"])
        assert meta.id is not None
        await repo.update_metadata(meta.id, actors=[])
        actors, total = await repo.list_facets(FacetKind.ACTOR)
        # 孤儿 Actor 保留, 但 count 为 0
        assert total == 1
        assert actors[0].count == 0
        items, n = await repo.list_metadata(actor_ids=[actors[0].id])
        assert n == 0 and items == []

    async def test_unknown_facet_id_returns_empty(self, repo: Repository) -> None:
        await repo.upsert_metadata(number="ABC-003", actors=["Alice"])
        items, n = await repo.list_metadata(actor_ids=[99999])
        assert n == 0 and items == []
        items, n = await repo.list_metadata(studio_ids=[99999])
        assert n == 0 and items == []

    async def test_scrape_upsert_preserves_user_tags_and_comments(self, repo: Repository) -> None:
        meta = await repo.upsert_metadata(number="ABC-004", actors=["Alice"], tags=["old"])
        assert meta.id is not None
        tag = await repo.create_user_tag("watched")
        assert tag.id is not None
        await repo.attach_user_tag(meta.id, tag.id)
        await repo.create_comment(meta.id, "hello")

        await repo.upsert_metadata(number="ABC-004", actors=["Bob"], tags=["new"])

        user_tags = await repo.list_metadata_user_tags(meta.id)
        assert [t.name for t in user_tags] == ["watched"]
        comments = await repo.list_comments(meta.id)
        assert [c.body for c in comments] == ["hello"]

        # 爬取 tags 已更新投影
        scraped, _ = await repo.list_facets(FacetKind.TAG)
        names = {t.name for t in scraped}
        assert "new" in names

    async def test_delete_metadata_keeps_actor_entity(self, repo: Repository) -> None:
        meta = await repo.upsert_metadata(number="ABC-005", actors=["KeepMe"])
        assert meta.id is not None
        actors, _ = await repo.list_facets(FacetKind.ACTOR)
        actor_id = actors[0].id
        await repo.delete_metadata(meta.id)
        facet = await repo.get_facet(FacetKind.ACTOR, actor_id)
        assert facet is not None
        assert facet.name == "KeepMe"
        assert facet.count == 0


class TestUserTagsAndComments:
    async def test_user_tag_crud_and_attach(self, repo: Repository) -> None:
        meta = await repo.upsert_metadata(number="UT-001")
        assert meta.id is not None
        tag = await repo.create_user_tag("fav")
        assert tag.id is not None
        assert await repo.attach_user_tag(meta.id, tag.id) is True
        assert await repo.attach_user_tag(meta.id, tag.id) is True  # 幂等
        _, n = await repo.list_metadata(user_tag_ids=[tag.id])
        assert n == 1
        assert await repo.detach_user_tag(meta.id, tag.id) is True
        assert await repo.detach_user_tag(meta.id, tag.id) is False
        await repo.update_user_tag(tag.id, name="favorite")
        updated = await repo.get_user_tag(tag.id)
        assert updated is not None and updated.name == "favorite"
        assert await repo.delete_user_tag(tag.id) is True

    async def test_duplicate_user_tag_name_raises(self, repo: Repository) -> None:
        await repo.create_user_tag("dup")
        with pytest.raises(IntegrityError):
            await repo.create_user_tag("dup")

    async def test_comment_crud(self, repo: Repository) -> None:
        meta = await repo.upsert_metadata(number="CM-001")
        assert meta.id is not None
        c = await repo.create_comment(meta.id, "body1")
        assert c is not None and c.id is not None
        updated = await repo.update_comment(c.id, body="body2")
        assert updated is not None and updated.body == "body2"
        assert await repo.delete_comment(c.id) is True
        assert await repo.create_comment(99999, "x") is None

    async def test_attach_missing_returns_false(self, repo: Repository) -> None:
        assert await repo.attach_user_tag(1, 1) is False


class TestFacetFilterCombine:
    async def test_keyword_and_actor_filter(self, repo: Repository) -> None:
        await repo.upsert_metadata(number="SSIS-001", title="Hello", actors=["Alice"])
        await repo.upsert_metadata(number="SSIS-002", title="World", actors=["Alice"])
        await repo.upsert_metadata(number="ABC-999", title="Hello", actors=["Bob"])
        actors, _ = await repo.list_facets(FacetKind.ACTOR, search="Alice")
        alice_id = actors[0].id
        items, n = await repo.list_metadata(keyword="Hello", actor_ids=[alice_id])
        assert n == 1
        assert items[0].number == "SSIS-001"

    async def test_multi_actor_and(self, repo: Repository) -> None:
        await repo.upsert_metadata(number="MA-001", actors=["Alice", "Bob"])
        await repo.upsert_metadata(number="MA-002", actors=["Alice"])
        await repo.upsert_metadata(number="MA-003", actors=["Bob", "Carol"])
        actors, _ = await repo.list_facets(FacetKind.ACTOR)
        by_name = {a.name: a.id for a in actors}
        items, n = await repo.list_metadata(actor_ids=[by_name["Alice"], by_name["Bob"]])
        assert n == 1 and items[0].number == "MA-001"

    async def test_multi_tag_and_with_actor(self, repo: Repository) -> None:
        await repo.upsert_metadata(number="MT-001", actors=["Alice"], tags=["t1", "t2"])
        await repo.upsert_metadata(number="MT-002", actors=["Alice"], tags=["t1"])
        await repo.upsert_metadata(number="MT-003", actors=["Bob"], tags=["t1", "t2"])
        actors, _ = await repo.list_facets(FacetKind.ACTOR, search="Alice")
        tags, _ = await repo.list_facets(FacetKind.TAG)
        by_tag = {t.name: t.id for t in tags}
        items, n = await repo.list_metadata(actor_ids=[actors[0].id], tag_ids=[by_tag["t1"], by_tag["t2"]])
        assert n == 1 and items[0].number == "MT-001"

    async def test_multi_studio_or(self, repo: Repository) -> None:
        await repo.upsert_metadata(number="MS-001", studio="StudioA")
        await repo.upsert_metadata(number="MS-002", studio="StudioB")
        await repo.upsert_metadata(number="MS-003", studio="StudioC")
        studios, _ = await repo.list_facets(FacetKind.STUDIO)
        by_name = {s.name: s.id for s in studios}
        items, n = await repo.list_metadata(studio_ids=[by_name["StudioA"], by_name["StudioB"]])
        assert n == 2
        assert {i.number for i in items} == {"MS-001", "MS-002"}

    async def test_multi_studio_ignores_unknown_id(self, repo: Repository) -> None:
        await repo.upsert_metadata(number="MS-010", studio="OnlyA")
        studios, _ = await repo.list_facets(FacetKind.STUDIO)
        items, n = await repo.list_metadata(studio_ids=[studios[0].id, 99999])
        assert n == 1 and items[0].number == "MS-010"


class TestFacetSort:
    @pytest.mark.parametrize(
        ("sort_by", "order", "expected"),
        [
            (FacetSortField.NAME, SortOrder.ASC, ["Alice", "Bob", "Carol"]),
            (FacetSortField.NAME, SortOrder.DESC, ["Carol", "Bob", "Alice"]),
            (FacetSortField.COUNT, SortOrder.ASC, ["Carol", "Bob", "Alice"]),
            (FacetSortField.COUNT, SortOrder.DESC, ["Alice", "Bob", "Carol"]),
        ],
    )
    async def test_link_facet_sort(
        self,
        repo: Repository,
        sort_by: FacetSortField,
        order: SortOrder,
        expected: list[str],
    ) -> None:
        await repo.upsert_metadata(number="FS-001", actors=["Alice", "Bob"])
        await repo.upsert_metadata(number="FS-002", actors=["Alice"])
        await repo.upsert_metadata(number="FS-003", actors=["Alice", "Bob", "Carol"])
        # Alice:3 Bob:2 Carol:1
        items, total = await repo.list_facets(FacetKind.ACTOR, sort_by=sort_by, order=order)
        assert total == 3
        assert [i.name for i in items] == expected

    @pytest.mark.parametrize(
        ("sort_by", "order", "expected"),
        [
            (FacetSortField.NAME, SortOrder.ASC, ["Alpha", "Beta", "Gamma"]),
            (FacetSortField.COUNT, SortOrder.DESC, ["Alpha", "Beta", "Gamma"]),
        ],
    )
    async def test_scalar_facet_sort(
        self,
        repo: Repository,
        sort_by: FacetSortField,
        order: SortOrder,
        expected: list[str],
    ) -> None:
        await repo.upsert_metadata(number="SS-001", studio="Alpha")
        await repo.upsert_metadata(number="SS-002", studio="Alpha")
        await repo.upsert_metadata(number="SS-003", studio="Beta")
        await repo.upsert_metadata(number="SS-004", studio="Gamma")
        # Alpha:2 Beta:1 Gamma:1 - count DESC ties break by id asc (Beta before Gamma)
        items, total = await repo.list_facets(FacetKind.STUDIO, sort_by=sort_by, order=order)
        assert total == 3
        assert [i.name for i in items] == expected

    async def test_sort_with_search(self, repo: Repository) -> None:
        await repo.upsert_metadata(number="SR-001", actors=["Ann", "Bob"])
        await repo.upsert_metadata(number="SR-002", actors=["Ann", "Amy"])
        items, total = await repo.list_facets(
            FacetKind.ACTOR,
            search="A",
            sort_by=FacetSortField.COUNT,
            order=SortOrder.DESC,
        )
        assert total == 2
        assert [i.name for i in items] == ["Ann", "Amy"]


class TestOrphanActorRetention:
    async def test_junction_removed_but_row_remains(self, repo: Repository) -> None:
        meta = await repo.upsert_metadata(number="OR-001", actors=["Solo"])
        assert meta.id is not None
        await repo.update_metadata(meta.id, actors=[])
        # 直接查 Actor 表仍在
        from sqlmodel import select

        async with repo._session() as session:
            row = (await session.exec(select(Actor).where(Actor.name == "Solo"))).first()
            assert row is not None
            links = (await session.exec(select(MetadataActor).where(MetadataActor.actor_id == row.id))).all()
            assert links == []
