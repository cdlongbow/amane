"""HTTP 录制经 ``net.recording`` 可选绑定, 不依赖 observability."""

from .errors import FailureKind, FailureReason, RequestError, RequestFailure, SourceError
from .http import BrowserClient, RateLimiters, WebClient
from .recording import bind_http_recorder_lookup, reset_skip_http_body, set_skip_http_body, skip_http_body

__all__ = [
    "BrowserClient",
    "FailureKind",
    "FailureReason",
    "RateLimiters",
    "RequestError",
    "RequestFailure",
    "SourceError",
    "WebClient",
    "bind_http_recorder_lookup",
    "reset_skip_http_body",
    "set_skip_http_body",
    "skip_http_body",
]
