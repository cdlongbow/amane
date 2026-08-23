from datetime import datetime

from pydantic import BaseModel


class UserTagResponse(BaseModel):
    id: int
    name: str
    created_at: datetime | None = None
    updated_at: datetime | None = None
