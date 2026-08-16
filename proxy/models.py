"""Value objects shared by proxy clients and submission integrations."""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

from .exceptions import ProxyParseError, ProxyTtlTooShortError


@dataclass(frozen=True, slots=True)
class ProxyEndpoint:
    host: str
    port: int
    username: str = ""
    password: str = ""
    location: str = ""
    city_code: str = ""
    carrier: str = ""
    remaining_seconds: int | None = None

    def __post_init__(self) -> None:
        host = self.host.strip()
        if not host or any(char.isspace() for char in host):
            raise ProxyParseError("proxy host is empty or contains whitespace")
        try:
            ipaddress.ip_address(host)
        except ValueError:
            if "." not in host and ":" not in host and host != "localhost":
                raise ProxyParseError("proxy host is neither an IP address nor a hostname")
        if not 1 <= int(self.port) <= 65535:
            raise ProxyParseError("proxy port must be between 1 and 65535")
        if bool(self.username) != bool(self.password):
            raise ProxyParseError("proxy username and password must be supplied together")
        if self.remaining_seconds is not None and self.remaining_seconds < 0:
            raise ProxyParseError("proxy remaining seconds cannot be negative")
        object.__setattr__(self, "host", host)
        object.__setattr__(self, "port", int(self.port))

    @property
    def address(self) -> str:
        host = f"[{self.host}]" if ":" in self.host and not self.host.startswith("[") else self.host
        return f"{host}:{self.port}"

    @property
    def log_label(self) -> str:
        return self.address

    @property
    def url(self) -> str:
        if not self.username:
            return f"http://{self.address}"
        username = quote(self.username, safe="")
        password = quote(self.password, safe="")
        return f"http://{username}:{password}@{self.address}"

    @property
    def requests_proxies(self) -> dict[str, str]:
        return {"http": self.url, "https": self.url}

    def to_playwright(self) -> dict[str, str]:
        result = {"server": f"http://{self.address}"}
        if self.username:
            result["username"] = self.username
            result["password"] = self.password
        return result

    def ensure_minimum_ttl(self, minimum_seconds: int) -> None:
        if (
            self.remaining_seconds is not None
            and self.remaining_seconds < minimum_seconds
        ):
            raise ProxyTtlTooShortError(self.remaining_seconds, minimum_seconds)

    def __repr__(self) -> str:
        return (
            "ProxyEndpoint("
            f"address={self.address!r}, location={self.location!r}, "
            f"city_code={self.city_code!r}, carrier={self.carrier!r}, "
            f"remaining_seconds={self.remaining_seconds!r}, authenticated={bool(self.username)!r})"
        )


@dataclass(slots=True)
class ProxyLease:
    endpoint: ProxyEndpoint
    requested_area: str
    acquired_at: datetime
    expires_at: datetime | None
    acquisition_attempt: int
    exit_ip: str | None = None
    verified_location: str | None = None
    latency_ms: int | None = None

    @classmethod
    def from_endpoint(
        cls,
        endpoint: ProxyEndpoint,
        requested_area: str,
        *,
        acquisition_attempt: int = 1,
        acquired_at: datetime | None = None,
    ) -> "ProxyLease":
        now = acquired_at or datetime.now(timezone.utc)
        expires_at = (
            now + timedelta(seconds=endpoint.remaining_seconds)
            if endpoint.remaining_seconds is not None
            else None
        )
        return cls(
            endpoint=endpoint,
            requested_area=requested_area,
            acquired_at=now,
            expires_at=expires_at,
            acquisition_attempt=acquisition_attempt,
        )

    def remaining_seconds(self, *, now: datetime | None = None) -> int | None:
        if self.expires_at is None:
            return None
        current = now or datetime.now(timezone.utc)
        return max(0, int((self.expires_at - current).total_seconds()))

    def ensure_minimum_ttl(
        self, minimum_seconds: int, *, now: datetime | None = None
    ) -> None:
        remaining = self.remaining_seconds(now=now)
        if remaining is not None and remaining < minimum_seconds:
            raise ProxyTtlTooShortError(remaining, minimum_seconds)

    def __repr__(self) -> str:
        return (
            "ProxyLease("
            f"endpoint={self.endpoint.log_label!r}, requested_area={self.requested_area!r}, "
            f"acquisition_attempt={self.acquisition_attempt}, exit_ip={self.exit_ip!r}, "
            f"verified_location={self.verified_location!r})"
        )
