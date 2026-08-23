import sys
from pathlib import Path

import pytest

from amane.utils.path import is_descendant


@pytest.mark.skipif(sys.platform == "win32", reason="此测试不适用于 Windows")
@pytest.mark.parametrize(
    "p, parent, expected",
    [
        # 基本场景
        ("/a/b/c", "/a/b", True),
        ("/a/b/c", "/a/b/./", True),
        ("/a/b", "/a/b", True),
        ("/a/b", "/a/b/", True),
        ("/a/b", "/a/b/.", True),
        ("/a/c", "/a/b", False),
        ("/a/b", "/a/b/c", False),
        ("/a/b/../c", "/a", True),
        ("/a/b/../c", "/a/c", True),
        ("/a/b/.", "/a/b", True),
        # 相对路径
        ("a/b/c", "a/b", True),
        ("a/b", "a/b", True),
        ("a/c", "a/b", False),
        ("a/c", "a/b/..", True),
        # Path 对象
        (Path("/a/b/c"), Path("/a/b"), True),
        (Path("a/b/c"), Path("a/b"), True),
        # 边界情况
        ("/a/barbar", "/a/bar", False),
        ("/a/bar", "/a/barbar", False),
        ("/", "/", True),
        ("/..", "/", True),
        ("/a", "/", True),
        # 混合类型
        (Path("/a/b/c"), "/a/b", True),
        ("/a/b/c", Path("/a/b"), True),
    ],
)
def test_is_descendant_posix(p, parent, expected):
    assert is_descendant(p, parent) == expected


@pytest.mark.skipif(sys.platform != "win32", reason="此测试仅适用于 Windows 路径")
@pytest.mark.parametrize(
    "p, parent, expected",
    [
        ("C:\\Users\\Test", "C:\\Users", True),
        ("C:\\Users\\Test", "C:\\", True),
        ("C:\\Users\\Test", "D:\\Users", False),
        ("C:\\Users\\Test\\", "C:\\Users", True),
        ("C:\\Users\\Test", "C:\\Users\\", True),
        ("C:/Users/Test", "C:/Users", True),
        (Path("C:/Users/Test"), Path("C:/Users"), True),
        (Path("C:/Users/Test"), "C:/Users", True),
        ("C:/Users/Test", Path("C:/Users"), True),
    ],
)
def test_is_descendant_windows(p, parent, expected):
    assert is_descendant(p, parent) == expected
