"""HTTP 限速器缓存 / 覆盖; RequestError 状态分类."""

import pytest

from amane.net.errors import FailureKind, FailureReason, RequestError, RequestFailure
from amane.net.http import RateLimiters


class TestRequestError:
    def test_classifies_http_status(self):
        err = RequestError(
            "https://example.com", RequestFailure(kind=FailureKind.HTTP_STATUS, status=429, message="HTTP 429")
        )
        assert err.reason == FailureReason.RATE_LIMITED
        assert err.http_status == 429


class TestRateLimiters:
    def test_returns_cached_limiter(self):
        rl = RateLimiters(default_rate=5)
        assert rl.get("example.com") is rl.get("example.com")

    def test_different_hosts(self):
        rl = RateLimiters(default_rate=5)
        assert rl.get("a.com") is not rl.get("b.com")

    def test_custom_rate_sets_period(self):
        rl = RateLimiters(default_rate=5)
        limiter = rl.get("custom.com", rate=42.0)
        assert limiter.time_period == pytest.approx(1 / 42.0)

    def test_localhost_uses_high_rate(self):
        rl = RateLimiters(default_rate=5)
        assert rl.get("localhost").time_period == pytest.approx(1 / 300.0)
        assert rl.get("example.com").time_period == pytest.approx(1 / 5)

    def test_set_rate_replaces_limiter(self):
        rl = RateLimiters(default_rate=5)
        old = rl.get("example.com")
        rl.set_rate("example.com", 100.0)
        new = rl.get("example.com")
        assert old is not new
        assert new.time_period == pytest.approx(1 / 100.0)

    def test_from_config_network_rate_overrides(self):
        rl = RateLimiters.from_config({"api.example.com": 20.0}, {}, {}, default_rate=5)
        assert rl.get("api.example.com").time_period == pytest.approx(1 / 20.0)
        assert rl.get("other.com").time_period == pytest.approx(1 / 5)
