from amane.api.models.libraries import LibraryResponse
from amane.db.models import Library
from amane.utils.model import to_resp


def test_to_resp_null_json_list_uses_response_default() -> None:
    """JSON 列读出 None 时, 非 Optional 且有默认的响应字段用默认值 (空列表)."""
    lib = Library(id=1, name="t", path="/m")
    object.__setattr__(lib, "patterns", None)
    resp = to_resp(LibraryResponse, lib)
    assert resp.patterns == []
