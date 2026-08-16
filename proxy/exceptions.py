"""Typed exceptions used by the proxy integration layer."""

from __future__ import annotations

from typing import Any


class ProxyError(RuntimeError):
    """Base class for proxy infrastructure errors."""


class ProxyConfigError(ProxyError):
    """Proxy configuration is missing or invalid."""


class ProxyApiTransportError(ProxyError):
    """The provider API could not be reached or decoded."""


class ProxyApiBusinessError(ProxyError):
    """The provider API returned a non-zero business code."""

    def __init__(
        self,
        code: int | str | None,
        message: str = "",
        *,
        retryable: bool = False,
        stop_task: bool = False,
    ) -> None:
        self.code = code
        self.provider_message = message
        self.retryable = retryable
        self.stop_task = stop_task
        detail = f"kuaidaili getdps failed: code={code}"
        if message:
            detail += f", msg={message}"
        super().__init__(detail)


class ProxyParseError(ProxyError):
    """A provider proxy item was malformed."""


class ProxyTtlTooShortError(ProxyError):
    """A proxy does not have enough remaining lifetime for a submission."""

    def __init__(self, remaining_seconds: int | None, minimum_seconds: int) -> None:
        self.remaining_seconds = remaining_seconds
        self.minimum_seconds = minimum_seconds
        super().__init__(
            "proxy remaining lifetime is too short: "
            f"remaining={remaining_seconds}, minimum={minimum_seconds}"
        )


class ProxyRateLimitError(ProxyError):
    """A rate-limit acquisition exceeded its caller-supplied wait timeout."""


class ProxyConnectionError(ProxyError):
    """A browser could not connect through the selected proxy."""


class ProxyValidationError(ProxyError):
    """The proxy exit verification response was unavailable or malformed."""


class ProxyLocationMismatchError(ProxyValidationError):
    """The verified exit location did not match the requested area."""

    def __init__(self, requested_area: str, reported_location: str) -> None:
        self.requested_area = requested_area
        self.reported_location = reported_location
        super().__init__(
            "proxy location mismatch: "
            f"requested={requested_area!r}, reported={reported_location!r}"
        )


def safe_error_text(value: Any, limit: int = 200) -> str:
    """Return a compact provider error string without multiline log injection."""

    text = " ".join(str(value or "").split())
    return text[:limit]
