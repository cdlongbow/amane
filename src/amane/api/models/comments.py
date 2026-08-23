from datetime import datetime

from pydantic import BaseModel, Field


class CommentResponse(BaseModel):
    id: int
    metadata_id: int
    body: str
    created_at: datetime | None = None
    updated_at: datetime | None = None


class CommentCreateRequest(BaseModel):
    body: str = Field(min_length=1, max_length=10000)


class CommentUpdateRequest(BaseModel):
    body: str = Field(min_length=1, max_length=10000)
