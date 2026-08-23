"""预告片跳过正则: 匹配文件名 (含扩展名)."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from amane.db.models import Library
from amane.utils.extensions import is_skipped_media, validate_trailer_pattern

SKIP_CASES = [
    ("(?i)trailer", "trailer.mp4", True),
    ("(?i)trailer", "MIDV-123-trailer.mkv", True),
    ("(?i)trailer", "TRAILER.MP4", True),
    ("(?i)trailer", "MIDV-123.mp4", False),
    ("预告", "中文预告片.mp4", True),
    ("预告", "MIDV-123.mp4", False),
    ("", "trailer.mp4", False),
    ("(?i)trailer", "sample.mp4", False),
]


@pytest.mark.parametrize(("pattern", "name", "skipped"), SKIP_CASES)
def test_is_skipped_media(pattern: str, name: str, skipped: bool):
    assert is_skipped_media(Path("/lib") / name, pattern) is skipped


def test_validate_trailer_pattern_rejects_invalid():
    with pytest.raises(ValueError, match="invalid trailer_pattern"):
        validate_trailer_pattern("[unclosed")


def test_library_rejects_invalid_trailer_pattern():
    with pytest.raises(ValidationError):
        Library.model_validate({"name": "x", "path": "/m", "trailer_pattern": "[unclosed"})
