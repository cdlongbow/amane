"""测试文件信息提取 - CD 编号, 字幕标识, 马赛克类型"""

import pytest

from amane.parsing import parse_file_info

# --- CD 编号检测 ---

CD_CASES = [
    ("MIDV-123-CD1.mp4", 1),
    ("MIDV-123-cd2.mp4", 2),
    ("MIDV-123-A.mp4", 1),
    ("MIDV-123-B.mp4", 2),
    ("MIDV-123.part2.mp4", 2),
    ("MIDV-123-1.mp4", 1),
    ("MIDV-123-2.mp4", 2),
    ("MIDV-123-3.mp4", 3),
    ("MIDV-123-9.mp4", 9),
    ("MIDV-123.mp4", None),
    ("MIDV-123-0.mp4", None),
    ("MIDV-123-01.mp4", None),
    ("MIDV-123-10.mp4", None),
    ("MIDV-123-12.mp4", None),
]


@pytest.mark.parametrize("filename,expected_cd", CD_CASES)
def test_cd_number(filename: str, expected_cd: int | None):
    info = parse_file_info(filename)
    assert info.cd == expected_cd


# --- 字幕检测 ---

SUBTITLE_CASES = [
    ("MIDV-123-C.mp4", True),
    ("MIDV-123-UC.mp4", True),
    ("[字幕]MIDV-123.mp4", True),
    ("MIDV-123.mp4", False),
]


@pytest.mark.parametrize("filename,expected", SUBTITLE_CASES)
def test_subtitle_flag(filename: str, expected: bool):
    info = parse_file_info(filename)
    assert info.has_subtitle is expected


# --- 马赛克类型检测 ---

MOSAIC_CASES = [
    ("[無碼]MIDV-123.mp4", "uncensored"),
    ("[破解]MIDV-123.mp4", "cracked"),
    ("MIDV-123-UC.mp4", "uncensored"),
    ("MIDV-123.mp4", None),
]


@pytest.mark.parametrize("filename,expected", MOSAIC_CASES)
def test_mosaic_type(filename: str, expected: str | None):
    info = parse_file_info(filename)
    assert info.mosaic == expected


# --- 与番号解析器集成 ---


@pytest.mark.parametrize(
    ("filename", "expected_cd"),
    [("MIDV-123-1.mp4", 1), ("MIDV-123-2.mp4", 2), ("MIDV-123-3.mp4", 3), ("MIDV-123-9.mp4", 9)],
)
def test_dash_number_cd_keeps_number(filename: str, expected_cd: int):
    """裸数字分集与番号提取一致性: 尾部 -1..-9 被识别为分集, 番号仍为 MIDV-123."""
    info = parse_file_info(filename)
    assert info.number == "MIDV-123"
    assert info.cd == expected_cd


def test_file_info_includes_parsed_number():
    info = parse_file_info("/media/videos/MIDV-123-CD1.mp4")
    assert info.number == "MIDV-123"
    assert info.content_type == "censored"
    assert info.cd == 1
