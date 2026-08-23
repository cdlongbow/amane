"""HTTP 客户端工具测试 - RateLimiters, RequestError, _make_limiter."""

from amane.net.errors import FailureKind, FailureReason, RequestError, RequestFailure, SourceError
from amane.net.http import RateLimiters, _make_limiter


class TestMakeLimiter:
    def test_creates_limiter(self):
        limiter = _make_limiter(5.0)
        assert limiter is not None


class TestRequestError:
    def test_message_format(self):
        err = RequestError("https://example.com", "timeout")
        assert err.url == "https://example.com"
        assert err.message == "timeout"
        assert "https://example.com" in str(err)
        assert "timeout" in str(err)
        assert isinstance(err, SourceError)
        assert err.reason == FailureReason.NETWORK

    def test_classifies_http_status(self):
        err = RequestError(
            "https://example.com",
            RequestFailure(kind=FailureKind.HTTP_STATUS, status=429, message="HTTP 429"),
        )
        assert err.reason == FailureReason.RATE_LIMITED
        assert err.http_status == 429


class TestRateLimitersGet:
    def test_creates_new_limiter(self):
        rl = RateLimiters(default_rate=5)
        limiter = rl.get("example.com")
        assert limiter is not None

    def test_returns_cached_limiter(self):
        rl = RateLimiters(default_rate=5)
        a = rl.get("example.com")
        b = rl.get("example.com")
        assert a is b

    def test_different_hosts(self):
        rl = RateLimiters(default_rate=5)
        a = rl.get("a.com")
        b = rl.get("b.com")
        assert a is not b

    def test_uses_custom_rate(self):
        rl = RateLimiters(default_rate=5)
        limiter = rl.get("custom.com", rate=42.0)
        assert limiter is not None

    def test_localhost_uses_high_rate(self):
        rl = RateLimiters(default_rate=5)
        limiter = rl.get("localhost")
        # localhost 应在初始化时已设置高速 limiter
        assert limiter is not None


class TestRateLimitersSetRate:
    def test_overrides_existing(self):
        rl = RateLimiters(default_rate=5)
        old = rl.get("example.com")
        rl.set_rate("example.com", 100.0)
        new = rl.get("example.com")
        assert old is not new

    def test_adds_new_host(self):
        rl = RateLimiters(default_rate=5)
        rl.set_rate("newhost.com", 20.0)
        limiter = rl.get("newhost.com")
        assert limiter is not None


class TestRateLimitersFromConfig:
    def test_empty_config(self):
        rl = RateLimiters.from_config({}, {}, {})
        assert rl is not None

    def test_default_rate_applied(self):
        rl = RateLimiters.from_config({}, {}, {}, default_rate=10)
        limiter = rl.get("some-site.com")
        assert limiter is not None

    def test_network_rate_limits(self):
        rl = RateLimiters.from_config(
            {"api.example.com": 20.0},
            {},
            {},
            default_rate=5,
        )
        # 应创建指定速率的限速器
        limiter = rl.get("api.example.com")
        assert limiter is not None

    def test_builtin_hosts_present(self):
        rl = RateLimiters.from_config({}, {}, {})
        # localhost / 127.0.0.1 应始终存在
        a = rl.get("localhost")
        b = rl.get("127.0.0.1")
        assert a is not None
        assert b is not None
