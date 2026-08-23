from __future__ import annotations

import importlib.util
import struct
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[1]
_SCRIPT = ROOT / "scripts" / "generate_icons.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("generate_icons", _SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


icons = _load()


def test_favicon_matches_logo() -> None:
    logo = (ROOT / "assets" / "logo.svg").read_bytes()
    favicon = (ROOT / "web" / "public" / "favicon.svg").read_bytes()
    assert logo
    assert favicon == logo


def test_packaged_icons_exist() -> None:
    ico = (ROOT / "assets" / "app.ico").read_bytes()
    icns = (ROOT / "assets" / "app.icns").read_bytes()
    reserved, kind, count = struct.unpack_from("<HHH", ico)
    assert reserved == 0
    assert kind == 1
    assert count == len(icons.ICO_SIZES)
    assert icns.startswith(b"icns")


def test_pack_ico_header_and_offsets() -> None:
    blob_a = b"\x89PNG" + b"a" * 8
    blob_b = b"\x89PNG" + b"b" * 20
    packed = icons.pack_ico([(16, blob_a), (256, blob_b)])
    reserved, kind, count = struct.unpack_from("<HHH", packed)
    assert (reserved, kind, count) == (0, 1, 2)
    w0, h0, _colors, _res, planes, bitcount, nbytes, offset = struct.unpack_from("<BBBBHHII", packed, 6)
    assert (w0, h0, planes, bitcount, nbytes, offset) == (16, 16, 1, 32, len(blob_a), 38)
    w1, h1, _c1, _r1, _p1, _b1, n1, off1 = struct.unpack_from("<BBBBHHII", packed, 22)
    assert (w1, h1, n1, off1) == (0, 0, len(blob_b), 38 + len(blob_a))
    assert packed[offset : offset + nbytes] == blob_a
    assert packed[off1 : off1 + n1] == blob_b


def test_pack_ico_rejects_empty() -> None:
    with pytest.raises(ValueError, match="at least one"):
        icons.pack_ico([])
