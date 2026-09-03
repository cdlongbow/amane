from datetime import datetime

from pydantic import BaseModel, Field


class FacetResponse(BaseModel):
    id: int
    name: str
    count: int


class FacetListResponse(BaseModel):
    items: list[FacetResponse]
    total: int


class FacetCreateRequest(BaseModel):
    """仅 kind=user_tag 可创建."""

    name: str = Field(min_length=1, max_length=200)


class FacetRenameRequest(BaseModel):
    name: str = Field(min_length=1, description="新名称")


class FacetMergeRequest(BaseModel):
    target_id: int
    source_ids: list[int] = Field(min_length=1, description="待合并的来源 facet id 列表")


class FacetRuleResponse(BaseModel):
    id: int
    kind: str
    source_name: str
    action: str
    target_name: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class FacetRuleListResponse(BaseModel):
    items: list[FacetRuleResponse]
