from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "fetch_fixtures.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("fetch_fixtures", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


fx = _load()

_BODY = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789+/abcdefghij"
_PROPER = (
    "-----BEGIN OPENSSH PRIVATE KEY-----\n"
    + "\n".join(_BODY[i : i + 70] for i in range(0, len(_BODY), 70))
    + "\n-----END OPENSSH PRIVATE KEY-----\n"
)


@pytest.mark.parametrize(
    ("raw", "expect"),
    [
        ("", ""),
        ("not-a-pem", "not-a-pem\n"),
        (
            "-----BEGIN OPENSSH PRIVATE KEY----- "
            "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789+/abcdefghij "
            "-----END OPENSSH PRIVATE KEY-----",
            _PROPER,
        ),
        (
            "-----BEGIN OPENSSH PRIVATE KEY-----\\n"
            "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789+/\\n"
            "abcdefghij\\n"
            "-----END OPENSSH PRIVATE KEY-----",
            _PROPER,
        ),
        (_PROPER.rstrip("\n"), _PROPER),
    ],
    ids=["empty", "plain", "spaces", "escaped-n", "already-wrapped"],
)
def test_normalize_deploy_key(raw: str, expect: str) -> None:
    assert fx.normalize_deploy_key(raw) == expect
