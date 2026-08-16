"""Phase-one tests for the Kuaidaili proxy infrastructure."""

from __future__ import annotations

import asyncio
import unittest
from datetime import datetime, timedelta, timezone

import httpx

from proxy.config import KuaidailiSettings
from proxy.exceptions import (
    ProxyApiBusinessError,
    ProxyApiTransportError,
    ProxyConfigError,
    ProxyParseError,
    ProxyTtlTooShortError,
)
from proxy.kuaidaili_client import KuaidailiClient
from proxy.logging_utils import redact_url
from proxy.models import ProxyEndpoint, ProxyLease
from proxy.parser import parse_proxy_item, parse_proxy_list
from proxy.rate_limiter import DualWindowRateLimiter


def settings(**overrides) -> KuaidailiSettings:
    values = {
        "enabled": True,
        "secret_id": "secret-id-value",
        "signature": "signature-value",
        "proxy_username": "configured-user",
        "proxy_password": "configured-password",
        "min_remaining_seconds": 180,
    }
    values.update(overrides)
    return KuaidailiSettings(**values)


class ConfigTests(unittest.TestCase):
    def test_enabled_configuration_requires_all_credentials(self):
        with self.assertRaises(ProxyConfigError) as raised:
            KuaidailiSettings.from_env(
                {"KDL_ENABLED": "true", "KDL_SECRET_ID": "id"},
                load_dotenv_file=False,
            )
        self.assertIn("KDL_SIGNATURE", str(raised.exception))
        self.assertNotIn("secret-id-value", str(raised.exception))

    def test_disabled_configuration_can_be_loaded_without_credentials(self):
        value = KuaidailiSettings.from_env({}, load_dotenv_file=False)
        self.assertFalse(value.enabled)


class ParserTests(unittest.TestCase):
    def test_parses_simple_proxy_with_default_auth(self):
        endpoint = parse_proxy_item(
            "1.2.3.4:8000",
            default_username="user",
            default_password="password",
        )
        self.assertEqual(endpoint.address, "1.2.3.4:8000")
        self.assertEqual(endpoint.username, "user")

    def test_parses_extended_proxy_and_fixed_auth_wins(self):
        endpoint = parse_proxy_item(
            "1.2.3.4:8000:item-user:item-password,福建 宁德,350900,300,电信",
            default_username="fixed-user",
            default_password="fixed-password",
        )
        self.assertEqual(endpoint.location, "福建 宁德")
        self.assertEqual(endpoint.city_code, "350900")
        self.assertEqual(endpoint.remaining_seconds, 300)
        self.assertEqual(endpoint.carrier, "电信")
        self.assertEqual(endpoint.username, "fixed-user")

    def test_parses_object_shape(self):
        endpoint = parse_proxy_item(
            {
                "ip": "5.6.7.8",
                "port": 9000,
                "area": "浙江 杭州",
                "citycode": "330100",
                "et": "240",
                "isp": "联通",
            },
            default_username="user",
            default_password="password",
        )
        self.assertEqual(endpoint.address, "5.6.7.8:9000")
        self.assertEqual(endpoint.remaining_seconds, 240)

    def test_invalid_remaining_seconds_becomes_unknown(self):
        endpoint = parse_proxy_item(
            "1.2.3.4:8000,福建 宁德,350900,unknown,电信",
            default_username="user",
            default_password="password",
        )
        self.assertIsNone(endpoint.remaining_seconds)

    def test_rejects_invalid_shape_without_leaking_item_auth(self):
        with self.assertRaises(ProxyParseError) as raised:
            parse_proxy_list(["bad:user:secret"])
        self.assertNotIn("secret", str(raised.exception))


class ModelAndLoggingTests(unittest.TestCase):
    def test_repr_and_log_url_do_not_expose_credentials(self):
        endpoint = ProxyEndpoint("1.2.3.4", 8000, "secret-user", "secret-password")
        self.assertNotIn("secret-user", repr(endpoint))
        self.assertNotIn("secret-password", repr(endpoint))
        redacted = redact_url(
            "https://secret-user:secret-password@example.com/path?signature=abc&area=x"
        )
        self.assertNotIn("secret-user", redacted)
        self.assertNotIn("secret-password", redacted)
        self.assertNotIn("abc", redacted)
        self.assertIn("signature=%2A%2A%2A", redacted)

    def test_ttl_boundary(self):
        accepted = ProxyEndpoint("1.2.3.4", 8000, remaining_seconds=180)
        accepted.ensure_minimum_ttl(180)
        rejected = ProxyEndpoint("1.2.3.4", 8000, remaining_seconds=179)
        with self.assertRaises(ProxyTtlTooShortError):
            rejected.ensure_minimum_ttl(180)

    def test_lease_remaining_time(self):
        now = datetime(2026, 8, 14, tzinfo=timezone.utc)
        lease = ProxyLease.from_endpoint(
            ProxyEndpoint("1.2.3.4", 8000, remaining_seconds=300),
            "宁德",
            acquired_at=now,
        )
        self.assertEqual(
            lease.remaining_seconds(now=now + timedelta(seconds=120)), 180
        )


class ClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_mock_transport_success_and_request_parameters(self):
        captured = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured.update(dict(request.url.params))
            return httpx.Response(
                200,
                json={
                    "code": 0,
                    "msg": "",
                    "data": {
                        "proxy_list": [
                            "1.2.3.4:8000:response-user:response-password,福建 宁德,350900,300,电信"
                        ]
                    },
                },
            )

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            client = KuaidailiClient(settings(), http_client=http)
            endpoints = await client.acquire(area="宁德", carrier=2)

        self.assertEqual(captured["area"], "宁德")
        self.assertEqual(captured["carrier"], "2")
        self.assertEqual(captured["f_et"], "1")
        self.assertEqual(endpoints[0].username, "configured-user")
        self.assertEqual(endpoints[0].remaining_seconds, 300)

    async def test_business_error_is_classified(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={"code": -51, "msg": "调用频率受限 signature-value"},
            )

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            client = KuaidailiClient(settings(), http_client=http)
            with self.assertRaises(ProxyApiBusinessError) as raised:
                await client.acquire(area="宁德")
        self.assertTrue(raised.exception.retryable)
        self.assertFalse(raised.exception.stop_task)
        self.assertNotIn("signature-value", str(raised.exception))

    async def test_http_error_becomes_transport_error(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(503, text="unavailable")

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            client = KuaidailiClient(settings(), http_client=http)
            with self.assertRaises(ProxyApiTransportError):
                await client.acquire(area="宁德")

    async def test_short_ttl_is_rejected(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "code": 0,
                    "data": {"proxy_list": ["1.2.3.4:8000,福建 宁德,350900,179,电信"]},
                },
            )

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            client = KuaidailiClient(settings(), http_client=http)
            with self.assertRaises(ProxyTtlTooShortError):
                await client.acquire(area="宁德")


class RateLimiterTests(unittest.IsolatedAsyncioTestCase):
    async def test_short_window_delays_third_acquisition(self):
        limiter = DualWindowRateLimiter(
            per_second=2,
            per_minute=100,
            second_window=0.04,
            minute_window=1.0,
        )
        loop = asyncio.get_running_loop()
        started = loop.time()
        await limiter.acquire()
        await limiter.acquire()
        await limiter.acquire()
        self.assertGreaterEqual(loop.time() - started, 0.03)

    async def test_long_window_delays_third_acquisition(self):
        limiter = DualWindowRateLimiter(
            per_second=100,
            per_minute=2,
            second_window=0.01,
            minute_window=0.04,
        )
        loop = asyncio.get_running_loop()
        started = loop.time()
        await limiter.acquire()
        await limiter.acquire()
        await limiter.acquire()
        self.assertGreaterEqual(loop.time() - started, 0.03)


if __name__ == "__main__":
    unittest.main()
