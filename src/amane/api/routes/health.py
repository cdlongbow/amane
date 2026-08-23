from fastapi import APIRouter

from ...version import get_version
from ..models import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """轻量就绪检查, 返回服务状态和版本."""
    return HealthResponse(status="ok", version=get_version())
