"""异步数据库引擎初始化测试"""

import pytest
from sqlalchemy import text
from sqlmodel import select

from amane.db.engine import create_async_engine_from_path, get_session
from amane.db.models import Library, MediaFile, MediaFileStatus


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "test.db"


@pytest.mark.asyncio
async def test_create_engine_creates_tables(db_path):
    engine = await create_async_engine_from_path(db_path)
    async with get_session(engine) as session:
        session.add(Library(id=1, name="t", path="/test"))
        await session.commit()
        media = MediaFile(path="/test/file.mp4", library_id=1, status=MediaFileStatus.PENDING)
        session.add(media)
        await session.commit()
        await session.refresh(media)
        assert media.id == 1


@pytest.mark.asyncio
async def test_session_isolation(db_path):
    engine = await create_async_engine_from_path(db_path)

    # 在一个 session 中写入
    async with get_session(engine) as session:
        session.add(Library(id=1, name="t", path="/"))
        await session.commit()
        session.add(MediaFile(path="/file1.mp4", library_id=1, status=MediaFileStatus.PENDING))
        await session.commit()

    # 在另一个 session 中读取
    async with get_session(engine) as session:
        result = (await session.execute(select(MediaFile))).scalars().all()
        assert len(result) == 1
        assert result[0].path == "/file1.mp4"


@pytest.mark.asyncio
async def test_engine_uses_wal_mode(db_path):
    engine = await create_async_engine_from_path(db_path)
    async with get_session(engine) as session:
        result = await session.execute(text("PRAGMA journal_mode"))
        mode = result.scalar()
        assert mode == "wal"
