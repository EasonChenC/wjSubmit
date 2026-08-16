"""Compatibility parser for Kuaidaili ``proxy_list`` response items."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .exceptions import ProxyParseError
from .models import ProxyEndpoint


def _string(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _optional_int(value: Any) -> int | None:
    text = _string(value)
    if not text:
        return None
    try:
        return int(text)
    except (TypeError, ValueError):
        return None


def _dict_value(item: Mapping[str, Any], *names: str) -> Any:
    for name in names:
        if name in item and item[name] not in (None, ""):
            return item[name]
    return None


def parse_proxy_item(
    item: Any,
    *,
    default_username: str = "",
    default_password: str = "",
) -> ProxyEndpoint:
    """Parse a provider item without exposing credentials in failures."""

    try:
        if isinstance(item, Mapping):
            host = _string(_dict_value(item, "ip", "host", "proxy_ip"))
            port_text = _string(_dict_value(item, "port", "proxy_port"))
            if not host or not port_text:
                raise ProxyParseError("proxy object does not contain host and port")
            username = _string(_dict_value(item, "username", "user", "proxy_username"))
            password = _string(_dict_value(item, "password", "pwd", "proxy_password"))
            if default_username:
                username, password = default_username, default_password
            return ProxyEndpoint(
                host=host,
                port=int(port_text),
                username=username,
                password=password,
                location=_string(_dict_value(item, "location", "loc", "area")),
                city_code=_string(_dict_value(item, "city_code", "citycode")),
                remaining_seconds=_optional_int(
                    _dict_value(item, "remaining_seconds", "et", "expire_seconds")
                ),
                carrier=_string(_dict_value(item, "carrier", "isp")),
            )

        text = _string(item)
        if not text:
            raise ProxyParseError("proxy item is empty")
        fields = [part.strip() for part in text.split(",")]
        address_and_auth = fields[0]
        parts = address_and_auth.split(":", 3)
        if len(parts) not in (2, 4):
            raise ProxyParseError("proxy string must contain IP:PORT or IP:PORT:USER:PASSWORD")
        host, port_text = parts[0].strip(), parts[1].strip()
        username = parts[2] if len(parts) == 4 else default_username
        password = parts[3] if len(parts) == 4 else default_password
        if default_username:
            username, password = default_username, default_password
        return ProxyEndpoint(
            host=host,
            port=int(port_text),
            username=username,
            password=password,
            location=fields[1] if len(fields) > 1 else "",
            city_code=fields[2] if len(fields) > 2 else "",
            remaining_seconds=_optional_int(fields[3]) if len(fields) > 3 else None,
            carrier=fields[4] if len(fields) > 4 else "",
        )
    except ProxyParseError:
        raise
    except (TypeError, ValueError) as exc:
        raise ProxyParseError("invalid proxy item fields") from exc


def parse_proxy_list(
    items: Any,
    *,
    default_username: str = "",
    default_password: str = "",
) -> list[ProxyEndpoint]:
    if items is None:
        return []
    if isinstance(items, (str, Mapping)):
        items = [items]
    if not isinstance(items, (list, tuple)):
        raise ProxyParseError("proxy_list must be a list, tuple, string, or object")
    return [
        parse_proxy_item(
            item,
            default_username=default_username,
            default_password=default_password,
        )
        for item in items
    ]
