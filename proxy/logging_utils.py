"""Credential-safe values for proxy logs and metrics."""

from __future__ import annotations

from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


SENSITIVE_QUERY_KEYS = {
    "secret_id",
    "signature",
    "secret_key",
    "token",
    "password",
    "username",
}


def redact_url(url: str) -> str:
    """Redact user info and sensitive query values from a URL."""

    parts = urlsplit(url)
    hostname = parts.hostname or ""
    if ":" in hostname and not hostname.startswith("["):
        hostname = f"[{hostname}]"
    netloc = hostname
    if parts.port:
        netloc += f":{parts.port}"
    query = urlencode(
        [
            (key, "***" if key.lower() in SENSITIVE_QUERY_KEYS else value)
            for key, value in parse_qsl(parts.query, keep_blank_values=True)
        ]
    )
    return urlunsplit((parts.scheme, netloc, parts.path, query, parts.fragment))


def proxy_log_label(proxy: Any) -> str:
    """Return only the endpoint address for logs."""

    label = getattr(proxy, "log_label", None)
    if label:
        return str(label)
    host = getattr(proxy, "host", "")
    port = getattr(proxy, "port", "")
    return f"{host}:{port}" if host and port else "unknown-proxy"


def redact_secrets(text: Any, *secrets: str, limit: int = 200) -> str:
    """Compact a message and replace configured secret values."""

    value = " ".join(str(text or "").split())
    for secret in secrets:
        if secret:
            value = value.replace(secret, "***")
    return value[:limit]
