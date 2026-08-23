"""GET /health."""

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from httpx2 import AsyncClient


class TestHealth:
    @pytest.mark.asyncio(loop_scope="function")
    async def test_health_check(self, client: AsyncClient):
        resp = await client.get("health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "version" in data
