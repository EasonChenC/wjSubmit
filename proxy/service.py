"""Acquire, verify, and rotate short-lived proxy browser contexts."""

from __future__ import annotations

import asyncio
import random
from collections.abc import Mapping
from typing import Any

from playwright.async_api import Browser, BrowserContext, Error as PlaywrightError

from .config import KuaidailiSettings
from .exceptions import ProxyApiBusinessError, ProxyError
from .kuaidaili_client import KuaidailiClient
from .models import ProxyLease
from .validator import ProxyValidator


PER_CONTEXT_PROXY_SERVER = "http://per-context"


def browser_launch_proxy(settings: KuaidailiSettings) -> dict[str, str] | None:
    """Return the Chromium launch proxy required for context proxies on Windows.

    Playwright requires Chromium on Windows to be launched with a global proxy
    before ``browser.new_context(proxy=...)`` can override it. The sentinel is
    never used by a context because every proxied context supplies its own
    endpoint.
    """

    return {"server": PER_CONTEXT_PROXY_SERVER} if settings.enabled else None


class ProxyService:
    def __init__(
        self,
        settings: KuaidailiSettings,
        *,
        client: KuaidailiClient | None = None,
        validator: ProxyValidator | None = None,
    ) -> None:
        settings.validate(require_credentials=settings.enabled)
        self.settings = settings
        self._owns_client = client is None
        self.client = client or KuaidailiClient(settings)
        self.validator = validator or ProxyValidator(
            settings.verify_url,
            settings.proxy_connect_timeout,
        )
        self._sticky_lease: ProxyLease | None = None

    @classmethod
    def from_env(cls) -> "ProxyService":
        return cls(KuaidailiSettings.from_env())

    async def aclose(self) -> None:
        if self._owns_client:
            await self.client.aclose()

    async def acquire_context(
        self,
        *,
        browser: Browser,
        area: str | None = None,
        carrier: int | None = None,
        context_options: Mapping[str, Any] | None = None,
        verify_exit: bool | None = None,
        match_mode: str | None = None,
    ) -> tuple[ProxyLease, BrowserContext]:
        requested_area = (area or self.settings.default_area).strip()
        if not requested_area:
            raise ValueError("proxy area is required")
        selected_carrier = self.settings.default_carrier if carrier is None else carrier
        should_verify = self.settings.verify_exit if verify_exit is None else verify_exit
        selected_mode = match_mode or self.settings.location_match
        last_error: Exception | None = None

        if not self.settings.rotate_per_submission and self._sticky_lease is not None:
            context: BrowserContext | None = None
            try:
                self._sticky_lease.ensure_minimum_ttl(
                    self.settings.min_remaining_seconds + self.settings.ttl_safety_margin
                )
                options = dict(context_options or {})
                options["proxy"] = self._sticky_lease.endpoint.to_playwright()
                context = await browser.new_context(**options)
                if should_verify:
                    await self.validator.validate(
                        context, self._sticky_lease, match_mode=selected_mode
                    )
                return self._sticky_lease, context
            except (ProxyError, PlaywrightError):
                if context is not None:
                    await context.close()
                self._sticky_lease = None

        for attempt in range(1, self.settings.max_acquire_attempts + 1):
            context: BrowserContext | None = None
            attempt_error: Exception | None = None
            try:
                lease = await self.client.acquire_lease(
                    area=requested_area,
                    carrier=selected_carrier,
                    dedup=self.settings.dedup,
                    acquisition_attempt=attempt,
                    minimum_remaining_seconds=self.settings.min_remaining_seconds,
                )
                lease.ensure_minimum_ttl(
                    self.settings.min_remaining_seconds + self.settings.ttl_safety_margin
                )
                options = dict(context_options or {})
                options["proxy"] = lease.endpoint.to_playwright()
                context = await browser.new_context(**options)
                if should_verify:
                    await self.validator.validate(context, lease, match_mode=selected_mode)
                if not self.settings.rotate_per_submission:
                    self._sticky_lease = lease
                return lease, context
            except ProxyApiBusinessError as exc:
                last_error = exc
                attempt_error = exc
                if exc.stop_task or not exc.retryable:
                    raise
            except ProxyError as exc:
                last_error = exc
                attempt_error = exc
            except PlaywrightError as exc:
                last_error = ProxyError(
                    "failed to create proxy browser context: "
                    f"{type(exc).__name__}: {' '.join(str(exc).split())}"
                )
                attempt_error = last_error
            finally:
                if context is not None and attempt_error is not None:
                    await context.close()

            if attempt < self.settings.max_acquire_attempts:
                delay = self.settings.retry_base_delay * (2 ** (attempt - 1))
                await asyncio.sleep(delay + random.uniform(0, min(delay * 0.2, 0.5)))

        assert last_error is not None
        raise last_error


async def create_submission_context(
    *,
    browser: Browser,
    settings: KuaidailiSettings,
    service: ProxyService | None,
    context_options: Mapping[str, Any] | None = None,
) -> tuple[ProxyLease | None, BrowserContext]:
    """Create one isolated context, using a proxy when it is enabled."""

    if settings.enabled:
        if service is None:
            raise ValueError("proxy service is required when proxy mode is enabled")
        try:
            return await service.acquire_context(
                browser=browser,
                area=settings.default_area,
                context_options=context_options,
            )
        except ProxyError:
            if settings.required:
                raise
            return None, await browser.new_context(**dict(context_options or {}))
    return None, await browser.new_context(**dict(context_options or {}))
