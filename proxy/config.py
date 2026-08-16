"""Environment-backed configuration for Kuaidaili private proxies."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping
from urllib.parse import urlparse

from dotenv import load_dotenv

from .exceptions import ProxyConfigError


def _parse_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ProxyConfigError(f"invalid boolean environment value: {value!r}")


def _parse_float(env: Mapping[str, str], name: str, default: float) -> float:
    raw = env.get(name)
    if raw in (None, ""):
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise ProxyConfigError(f"{name} must be a number") from exc


def _parse_int(env: Mapping[str, str], name: str, default: int) -> int:
    raw = env.get(name)
    if raw in (None, ""):
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ProxyConfigError(f"{name} must be an integer") from exc


@dataclass(frozen=True, slots=True)
class KuaidailiSettings:
    """Validated immutable settings for the provider client."""

    enabled: bool = False
    secret_id: str = ""
    signature: str = ""
    proxy_username: str = ""
    proxy_password: str = ""
    api_url: str = "https://dps.kdlapi.com/api/getdps/"
    request_timeout: float = 12.0
    proxy_connect_timeout: float = 8.0
    verify_url: str = "https://myip.ipip.net/"
    min_remaining_seconds: int = 180
    ttl_safety_margin: int = 30
    max_acquire_attempts: int = 3
    per_second_limit: int = 10
    per_minute_limit: int = 120
    default_area: str = ""
    default_carrier: int = 0
    dedup: bool = True
    rotate_per_submission: bool = True
    verify_exit: bool = True
    location_match: str = "relaxed"
    required: bool = True
    retry_base_delay: float = 1.0

    @classmethod
    def from_env(
        cls,
        env: Mapping[str, str] | None = None,
        *,
        load_dotenv_file: bool = True,
    ) -> "KuaidailiSettings":
        if load_dotenv_file:
            load_dotenv()
        values = os.environ if env is None else env
        settings = cls(
            enabled=_parse_bool(values.get("KDL_ENABLED"), False),
            secret_id=values.get("KDL_SECRET_ID", "").strip(),
            signature=values.get("KDL_SIGNATURE", "").strip(),
            proxy_username=values.get("KDL_PROXY_USERNAME", "").strip(),
            proxy_password=values.get("KDL_PROXY_PASSWORD", ""),
            api_url=values.get(
                "KDL_API_URL", "https://dps.kdlapi.com/api/getdps/"
            ).strip(),
            request_timeout=_parse_float(values, "KDL_REQUEST_TIMEOUT", 12.0),
            proxy_connect_timeout=_parse_float(
                values, "KDL_PROXY_CONNECT_TIMEOUT", 8.0
            ),
            verify_url=values.get(
                "KDL_PROXY_VERIFY_URL", "https://myip.ipip.net/"
            ).strip(),
            min_remaining_seconds=_parse_int(
                values, "KDL_PROXY_MIN_REMAINING_SECONDS", 180
            ),
            ttl_safety_margin=_parse_int(
                values, "KDL_PROXY_TTL_SAFETY_MARGIN", 30
            ),
            max_acquire_attempts=_parse_int(
                values, "KDL_PROXY_MAX_ACQUIRE_ATTEMPTS", 3
            ),
            per_second_limit=_parse_int(values, "KDL_API_PER_SECOND_LIMIT", 10),
            per_minute_limit=_parse_int(values, "KDL_API_PER_MINUTE_LIMIT", 120),
            default_area=values.get("KDL_DEFAULT_AREA", "").strip(),
            default_carrier=_parse_int(values, "KDL_DEFAULT_CARRIER", 0),
            dedup=_parse_bool(values.get("KDL_PROXY_DEDUP"), True),
            rotate_per_submission=_parse_bool(
                values.get("KDL_PROXY_ROTATE_PER_SUBMISSION"), True
            ),
            verify_exit=_parse_bool(values.get("KDL_PROXY_VERIFY_EXIT"), True),
            location_match=values.get("KDL_PROXY_LOCATION_MATCH", "relaxed").strip().lower(),
            required=_parse_bool(values.get("KDL_PROXY_REQUIRED"), True),
            retry_base_delay=_parse_float(values, "KDL_PROXY_RETRY_BASE_DELAY", 1.0),
        )
        settings.validate()
        return settings

    def validate(self, *, require_credentials: bool | None = None) -> None:
        require = self.enabled if require_credentials is None else require_credentials
        if require:
            missing = [
                name
                for name, value in (
                    ("KDL_SECRET_ID", self.secret_id),
                    ("KDL_SIGNATURE", self.signature),
                    ("KDL_PROXY_USERNAME", self.proxy_username),
                    ("KDL_PROXY_PASSWORD", self.proxy_password),
                )
                if not value
            ]
            if missing:
                raise ProxyConfigError(
                    "missing required proxy environment variables: " + ", ".join(missing)
                )

        for name, url in (("KDL_API_URL", self.api_url), ("KDL_PROXY_VERIFY_URL", self.verify_url)):
            parsed = urlparse(url)
            if parsed.scheme != "https" or not parsed.netloc:
                raise ProxyConfigError(f"{name} must be a valid HTTPS URL")

        if self.request_timeout <= 0 or self.proxy_connect_timeout <= 0:
            raise ProxyConfigError("proxy timeouts must be greater than zero")
        if self.min_remaining_seconds < 0 or self.ttl_safety_margin < 0:
            raise ProxyConfigError("proxy TTL settings cannot be negative")
        if not 1 <= self.max_acquire_attempts <= 10:
            raise ProxyConfigError("KDL_PROXY_MAX_ACQUIRE_ATTEMPTS must be between 1 and 10")
        if not 1 <= self.per_second_limit <= 10:
            raise ProxyConfigError("KDL_API_PER_SECOND_LIMIT must be between 1 and 10")
        if not 1 <= self.per_minute_limit <= 120:
            raise ProxyConfigError("KDL_API_PER_MINUTE_LIMIT must be between 1 and 120")
        if self.default_carrier not in (0, 1, 2, 3):
            raise ProxyConfigError("KDL_DEFAULT_CARRIER must be 0, 1, 2, or 3")
        if self.location_match not in {"strict", "relaxed"}:
            raise ProxyConfigError("KDL_PROXY_LOCATION_MATCH must be strict or relaxed")
        if self.retry_base_delay < 0:
            raise ProxyConfigError("KDL_PROXY_RETRY_BASE_DELAY cannot be negative")
