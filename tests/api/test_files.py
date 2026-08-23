"""/files 端点测试 - 文件浏览器"""

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from httpx2 import AsyncClient


class TestListFiles:
    @pytest.mark.asyncio(loop_scope="function")
    async def test_list_directory(self, client: AsyncClient, safe_path):
        (safe_path / "z_dir").mkdir()
        (safe_path / "a_file.txt").write_text("x")
        (safe_path / "data.bin").write_bytes(b"\x00" * 100)
        (safe_path / ".hidden").write_text("secret")
        listed_file = safe_path / "somefile.txt"
        listed_file.write_text("content")

        resp = await client.get("files", params={"path": str(safe_path)})
        assert resp.status_code == 200
        items = resp.json()["items"]
        names = {e["name"] for e in items}
        assert names == {"z_dir", "a_file.txt", "data.bin", "somefile.txt"}
        assert items[0]["type"] == "directory"

        file_entry = next(e for e in items if e["name"] == "data.bin")
        assert file_entry["size"] == 100
        dir_entry = next(e for e in items if e["name"] == "z_dir")
        assert dir_entry["size"] is None

        shown = await client.get("files", params={"path": str(safe_path), "show_hidden": True})
        assert ".hidden" in {e["name"] for e in shown.json()["items"]}

        parent = await client.get("files", params={"path": str(listed_file)})
        assert parent.status_code == 200
        assert "somefile.txt" in {e["name"] for e in parent.json()["items"]}

    @pytest.mark.asyncio(loop_scope="function")
    async def test_list_rejects_illegal_paths(self, client: AsyncClient, safe_path, tmp_path):
        outside = await client.get("files", params={"path": str(tmp_path)})
        assert outside.status_code == 403
        missing = await client.get("files", params={"path": str(safe_path / "nope")})
        assert missing.status_code == 400
