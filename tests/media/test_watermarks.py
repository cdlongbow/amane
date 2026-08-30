"""用户覆盖目录优先于包内置; 非法主干拒绝."""

from typing import TYPE_CHECKING

import pytest
from PIL import Image

from amane.media.watermarks import is_stamp_stem, load_stamp, user_watermark_dir

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.parametrize(
    ("stem", "expected"),
    [
        ("subtitle", True),
        ("4k", True),
        ("1080p", True),
        ("", False),
        ("subtitle.png", False),
        ("../subtitle", False),
        ("sub/title", False),
        ("SUBTITLE", False),
        ("4K", False),
    ],
)
def test_is_stamp_stem(stem: str, expected: bool) -> None:
    assert is_stamp_stem(stem) is expected


def test_user_watermark_dir(tmp_path: Path) -> None:
    assert user_watermark_dir(tmp_path) == tmp_path / "watermarks"


def test_load_builtin_subtitle() -> None:
    img = load_stamp("subtitle", None)
    assert img is not None
    assert img.mode == "RGBA"
    assert img.getbbox() is not None


def test_load_unknown_definition_without_user_file() -> None:
    assert load_stamp("1080p", None) is None


def test_user_file_wins(tmp_path: Path) -> None:
    user_dir = tmp_path / "watermarks"
    user_dir.mkdir()
    Image.new("RGBA", (8, 8), (0, 255, 0, 255)).save(user_dir / "subtitle.png")
    img = load_stamp("subtitle", user_dir)
    assert img is not None
    pixel = img.getpixel((0, 0))
    assert pixel == (0, 255, 0, 255)


def test_user_1080p_without_builtin(tmp_path: Path) -> None:
    user_dir = tmp_path / "watermarks"
    user_dir.mkdir()
    Image.new("RGBA", (8, 8), (0, 0, 255, 255)).save(user_dir / "1080p.png")
    img = load_stamp("1080p", user_dir)
    assert img is not None
    assert img.getpixel((0, 0)) == (0, 0, 255, 255)


def test_corrupt_user_falls_back(tmp_path: Path) -> None:
    user_dir = tmp_path / "watermarks"
    user_dir.mkdir()
    (user_dir / "subtitle.png").write_bytes(b"garbage")
    img = load_stamp("subtitle", user_dir)
    assert img is not None
    assert img.getbbox() is not None


def test_rejects_path_stem(tmp_path: Path) -> None:
    user_dir = tmp_path / "watermarks"
    user_dir.mkdir()
    Image.new("RGBA", (4, 4), (255, 0, 0, 255)).save(user_dir / "subtitle.png")
    assert load_stamp("../watermarks/subtitle", user_dir) is None
    assert load_stamp("subtitle.png", user_dir) is None
