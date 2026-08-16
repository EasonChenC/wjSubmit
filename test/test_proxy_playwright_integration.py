"""Unit tests for phase-two proxy and Playwright orchestration."""

from __future__ import annotations

import unittest

from proxy.config import KuaidailiSettings
from proxy.exceptions import ProxyLocationMismatchError, ProxyValidationError
from proxy.models import ProxyEndpoint, ProxyLease
from proxy.service import ProxyService, browser_launch_proxy, create_submission_context
from proxy.validator import (
    ExitIpInfo,
    location_matches,
    normalize_area,
    parse_ipip_response,
)


class FakeContext:
    def __init__(self) -> None:
        self.closed = False

    async def close(self) -> None:
        self.closed = True


class FakeBrowser:
    def __init__(self) -> None:
        self.calls = []

    async def new_context(self, **options):
        context = FakeContext()
        self.calls.append((options, context))
        return context


class FakeClient:
    def __init__(self, endpoints):
        self.endpoints = list(endpoints)
        self.calls = []

    async def acquire_lease(self, **kwargs):
        self.calls.append(kwargs)
        endpoint = self.endpoints.pop(0)
        return ProxyLease.from_endpoint(
            endpoint,
            kwargs["area"],
            acquisition_attempt=kwargs["acquisition_attempt"],
        )

    async def aclose(self):
        return None


class FakeValidator:
    def __init__(self, failures=0):
        self.failures = failures
        self.calls = []

    async def validate(self, context, lease, *, match_mode):
        self.calls.append((context, lease, match_mode))
        if self.failures:
            self.failures -= 1
            raise ProxyLocationMismatchError(lease.requested_area, "中国 江苏 苏州")
        lease.exit_ip = "8.8.8.8"
        lease.verified_location = "中国 江苏 南京 电信"
        return ExitIpInfo("8.8.8.8", "中国", "江苏", "南京", "电信")


def enabled_settings(**overrides):
    values = dict(
        enabled=True,
        secret_id="id",
        signature="signature",
        proxy_username="user",
        proxy_password="password",
        default_area="南京",
        min_remaining_seconds=180,
        ttl_safety_margin=30,
        max_acquire_attempts=3,
        retry_base_delay=0,
    )
    values.update(overrides)
    return KuaidailiSettings(**values)


class ValidatorTests(unittest.TestCase):
    def test_parse_ipip_response(self):
        info = parse_ipip_response("当前 IP：1.2.3.4  来自于：中国 江苏 南京 电信")
        self.assertEqual(info.ip, "1.2.3.4")
        self.assertEqual(info.city, "南京")
        self.assertEqual(info.isp, "电信")

    def test_area_normalization_and_matching(self):
        self.assertEqual(normalize_area("南京市"), "南京")
        info = ExitIpInfo("1.2.3.4", "中国", "江苏", "南京", "电信")
        self.assertTrue(location_matches("南京市", info, mode="strict"))
        self.assertTrue(location_matches("南京", info, mode="relaxed"))
        self.assertFalse(location_matches("苏州", info, mode="strict"))
        empty = ExitIpInfo("1.2.3.4", "中国", "江苏", "", "电信")
        self.assertFalse(location_matches("南京", empty, mode="relaxed"))

    def test_bad_verify_response(self):
        with self.assertRaises(ProxyValidationError):
            parse_ipip_response("unexpected")


class ServiceTests(unittest.IsolatedAsyncioTestCase):
    def test_enabled_proxy_uses_windows_per_context_launch_sentinel(self):
        self.assertEqual(
            browser_launch_proxy(enabled_settings()),
            {"server": "http://per-context"},
        )
        self.assertIsNone(browser_launch_proxy(KuaidailiSettings(enabled=False)))

    async def test_proxy_context_contains_server_and_auth(self):
        endpoint = ProxyEndpoint(
            "1.2.3.4", 8000, "user", "password", "江苏 南京", remaining_seconds=300
        )
        browser = FakeBrowser()
        client = FakeClient([endpoint])
        validator = FakeValidator()
        service = ProxyService(
            enabled_settings(), client=client, validator=validator
        )

        lease, context = await service.acquire_context(
            browser=browser,
            context_options={"locale": "zh-CN"},
        )

        options = browser.calls[0][0]
        self.assertEqual(options["locale"], "zh-CN")
        self.assertEqual(options["proxy"]["server"], "http://1.2.3.4:8000")
        self.assertEqual(options["proxy"]["username"], "user")
        self.assertEqual(lease.exit_ip, "8.8.8.8")
        self.assertFalse(context.closed)

    async def test_failed_context_is_closed_and_second_proxy_is_used(self):
        endpoints = [
            ProxyEndpoint("1.2.3.4", 8000, "u", "p", remaining_seconds=300),
            ProxyEndpoint("5.6.7.8", 9000, "u", "p", remaining_seconds=300),
        ]
        browser = FakeBrowser()
        service = ProxyService(
            enabled_settings(),
            client=FakeClient(endpoints),
            validator=FakeValidator(failures=1),
        )

        lease, context = await service.acquire_context(browser=browser)

        self.assertEqual(len(browser.calls), 2)
        self.assertTrue(browser.calls[0][1].closed)
        self.assertFalse(context.closed)
        self.assertEqual(lease.endpoint.host, "5.6.7.8")
        self.assertEqual(lease.acquisition_attempt, 2)

    async def test_direct_context_does_not_receive_proxy(self):
        browser = FakeBrowser()
        value = KuaidailiSettings(enabled=False)
        lease, context = await create_submission_context(
            browser=browser,
            settings=value,
            service=None,
            context_options={"locale": "zh-CN"},
        )
        self.assertIsNone(lease)
        self.assertNotIn("proxy", browser.calls[0][0])
        self.assertFalse(context.closed)


if __name__ == "__main__":
    unittest.main()
