"""Asynchronous Kuaidaili private dynamic proxy API client."""

from __future__ import annotations

from typing import Any

import httpx

from .config import KuaidailiSettings
from .exceptions import (
    ProxyApiBusinessError,
    ProxyApiTransportError,
    ProxyParseError,
)
from .logging_utils import redact_secrets
from .models import ProxyEndpoint, ProxyLease
from .parser import parse_proxy_list
from .rate_limiter import DualWindowRateLimiter


STOP_TASK_CODES = {1, 2, -11, -12, -13, -14, -15, -16}
RETRYABLE_CODES = {3, -4, -51}


class KuaidailiClient:
    """Fetch and parse short-lived private proxy endpoints."""

    def __init__(
        self,
        settings: KuaidailiSettings,
        *,
        http_client: httpx.AsyncClient | None = None,
        rate_limiter: DualWindowRateLimiter | None = None,
    ) -> None:
        settings.validate(require_credentials=True)
        self.settings = settings
        self._owns_http_client = http_client is None
        self._http_client = http_client or httpx.AsyncClient(
            timeout=httpx.Timeout(settings.request_timeout)
        )
        self._rate_limiter = rate_limiter or DualWindowRateLimiter(
            per_second=settings.per_second_limit,
            per_minute=settings.per_minute_limit,
        )

    @classmethod
    def from_env(cls) -> "KuaidailiClient":
        return cls(KuaidailiSettings.from_env())

    async def __aenter__(self) -> "KuaidailiClient":
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        if self._owns_http_client:
            await self._http_client.aclose()

    async def acquire(
        self,
        *,
        area: str,
        num: int = 1,
        carrier: int = 0,
        dedup: bool = True,
        minimum_remaining_seconds: int | None = None,
    ) -> list[ProxyEndpoint]:
        normalized_area = area.strip()
        if not normalized_area:
            raise ValueError("area cannot be empty")
        if not 1 <= num <= 100:
            raise ValueError("num must be between 1 and 100")
        if carrier not in (0, 1, 2, 3):
            raise ValueError("carrier must be 0, 1, 2, or 3")

        await self._rate_limiter.acquire()
        params = {
            "secret_id": self.settings.secret_id,
            "signature": self.settings.signature,
            "num": num,
            "area": normalized_area,
            "format": "json",
            "sep": 1,
            "f_auth": 1,
            "generateType": 1,
            "f_loc": 1,
            "f_citycode": 1,
            "f_et": 1,
            "f_carrier": 1,
            "dedup": int(dedup),
            "carrier": carrier,
        }
        payload = await self._request_payload(params)
        code = payload.get("code")
        if code != 0:
            raise ProxyApiBusinessError(
                code,
                redact_secrets(
                    payload.get("msg"),
                    self.settings.secret_id,
                    self.settings.signature,
                    self.settings.proxy_username,
                    self.settings.proxy_password,
                ),
                retryable=code in RETRYABLE_CODES,
                stop_task=code in STOP_TASK_CODES,
            )

        data = payload.get("data") or {}
        if not isinstance(data, dict):
            raise ProxyParseError("provider response data must be an object")
        endpoints = parse_proxy_list(
            data.get("proxy_list"),
            default_username=self.settings.proxy_username,
            default_password=self.settings.proxy_password,
        )
        if not endpoints:
            raise ProxyParseError("provider returned an empty proxy_list")

        minimum = (
            self.settings.min_remaining_seconds
            if minimum_remaining_seconds is None
            else minimum_remaining_seconds
        )
        for endpoint in endpoints:
            endpoint.ensure_minimum_ttl(minimum)
        return endpoints

    async def acquire_lease(
        self,
        *,
        area: str,
        carrier: int = 0,
        dedup: bool = True,
        acquisition_attempt: int = 1,
        minimum_remaining_seconds: int | None = None,
    ) -> ProxyLease:
        endpoints = await self.acquire(
            area=area,
            num=1,
            carrier=carrier,
            dedup=dedup,
            minimum_remaining_seconds=minimum_remaining_seconds,
        )
        return ProxyLease.from_endpoint(
            endpoints[0],
            area.strip(),
            acquisition_attempt=acquisition_attempt,
        )

    async def _request_payload(self, params: dict[str, Any]) -> dict[str, Any]:
        try:
            response = await self._http_client.get(self.settings.api_url, params=params)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise ProxyApiTransportError(
                f"kuaidaili API returned HTTP {exc.response.status_code}"
            ) from exc
        except httpx.RequestError as exc:
            raise ProxyApiTransportError(
                f"kuaidaili API request failed: {type(exc).__name__}"
            ) from exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise ProxyApiTransportError("kuaidaili API returned invalid JSON") from exc
        if not isinstance(payload, dict):
            raise ProxyApiTransportError("kuaidaili API response must be a JSON object")
        return payload
