from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as pkg_version
from unittest.mock import patch

import pytest

from amane.version import PACKAGE_NAME, get_version


def test_get_version_matches_installed_metadata() -> None:
    assert get_version() == pkg_version(PACKAGE_NAME)


def test_get_version_raises_when_package_missing() -> None:
    with (
        patch("amane.version.version", side_effect=PackageNotFoundError(PACKAGE_NAME)),
        pytest.raises(PackageNotFoundError),
    ):
        get_version()
