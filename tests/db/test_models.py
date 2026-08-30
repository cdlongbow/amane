"""SQLModel 表约束: 唯一性由 SQLite 强制, 不经 Repository."""

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, SQLModel, create_engine

from amane.db.models import MediaFile, MediaFileStatus, Metadata


@pytest.fixture
def engine():
    engine = create_engine("sqlite://", echo=False)
    SQLModel.metadata.create_all(engine)
    with engine.connect() as conn:
        yield conn
    engine.dispose()


@pytest.fixture
def session(engine):
    with Session(engine) as session:
        yield session


class TestMediaFile:
    def test_path_is_unique(self, session: Session):
        media1 = MediaFile(path="/media/video/MIDV-123.mp4", library_id=1, status=MediaFileStatus.PENDING)
        media2 = MediaFile(path="/media/video/MIDV-123.mp4", library_id=1, status=MediaFileStatus.PENDING)
        session.add(media1)
        session.commit()
        session.add(media2)
        with pytest.raises(IntegrityError):
            session.commit()


class TestMetadata:
    def test_number_is_unique(self, session: Session):
        m1 = Metadata(number="MIDV-123")
        m2 = Metadata(number="MIDV-123")
        session.add(m1)
        session.commit()
        session.add(m2)
        with pytest.raises(IntegrityError):
            session.commit()
