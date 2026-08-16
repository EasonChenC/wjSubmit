"""Validate the real browser exit IP and its reported location."""

from __future__ import annotations

import ipaddress
import re
import time
from dataclasses import dataclass

from playwright.async_api import BrowserContext, Error as PlaywrightError, TimeoutError

from .exceptions import (
    ProxyConnectionError,
    ProxyLocationMismatchError,
    ProxyValidationError,
)
from .models import ProxyLease


IPIP_PATTERN = re.compile(r"当前\s*IP[：:]\s*(\S+)\s+来自于[：:]\s*(.+)$")
AREA_SUFFIXES = ("特别行政区", "自治区", "自治州", "地区", "盟", "省", "市", "区", "县")


@dataclass(frozen=True, slots=True)
class ExitIpInfo:
    ip: str
    country: str = ""
    region: str = ""
    city: str = ""
    isp: str = ""

    @property
    def location(self) -> str:
        return " ".join(part for part in (self.country, self.region, self.city, self.isp) if part)


def parse_ipip_response(text: str) -> ExitIpInfo:
    value = " ".join((text or "").strip().split())
    match = IPIP_PATTERN.search(value)
    if not match:
        raise ProxyValidationError("unexpected proxy verification response")
    ip = match.group(1)
    try:
        ipaddress.ip_address(ip)
    except ValueError as exc:
        raise ProxyValidationError("proxy verification returned an invalid IP") from exc
    parts = match.group(2).split()
    return ExitIpInfo(
        ip=ip,
        country=parts[0] if len(parts) > 0 else "",
        region=parts[1] if len(parts) > 1 else "",
        city=parts[2] if len(parts) > 2 else "",
        isp=" ".join(parts[3:]) if len(parts) > 3 else "",
    )


def normalize_area(value: str) -> str:
    normalized = re.sub(r"[\s,，·\-_/]+", "", (value or "").strip()).lower()
    changed = True
    while changed and normalized:
        changed = False
        for suffix in AREA_SUFFIXES:
            if normalized.endswith(suffix) and len(normalized) > len(suffix):
                normalized = normalized[: -len(suffix)]
                changed = True
                break
    return normalized


def location_matches(
    requested_area: str,
    info: ExitIpInfo,
    *,
    provider_location: str = "",
    mode: str = "relaxed",
) -> bool:
    requested = normalize_area(requested_area)
    if not requested:
        return False
    city = normalize_area(info.city)
    reported = normalize_area("".join((info.region, info.city)))
    provider = normalize_area(provider_location)
    if mode == "strict":
        return requested == city or requested in reported
    return requested in reported or requested in provider or (bool(city) and city in requested)


class ProxyValidator:
    def __init__(self, verify_url: str, timeout_seconds: float = 8.0) -> None:
        self.verify_url = verify_url
        self.timeout_ms = max(1, int(timeout_seconds * 1000))

    async def validate(
        self,
        context: BrowserContext,
        lease: ProxyLease,
        *,
        match_mode: str = "relaxed",
    ) -> ExitIpInfo:
        page = await context.new_page()
        started = time.monotonic()
        try:
            response = await page.goto(
                self.verify_url,
                wait_until="domcontentloaded",
                timeout=self.timeout_ms,
            )
            if response is None or not response.ok:
                status = response.status if response else "no-response"
                raise ProxyConnectionError(f"proxy verification returned HTTP {status}")
            info = parse_ipip_response(await page.text_content("body") or "")
            if not location_matches(
                lease.requested_area,
                info,
                provider_location=lease.endpoint.location,
                mode=match_mode,
            ):
                raise ProxyLocationMismatchError(lease.requested_area, info.location)
            lease.exit_ip = info.ip
            lease.verified_location = info.location
            lease.latency_ms = int((time.monotonic() - started) * 1000)
            return info
        except ProxyValidationError:
            raise
        except (TimeoutError, PlaywrightError) as exc:
            raise ProxyConnectionError(
                f"proxy verification failed: {type(exc).__name__}"
            ) from exc
        finally:
            await page.close()
