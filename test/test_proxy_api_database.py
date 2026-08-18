"""Tests for phase-three proxy API and database mappings."""

from __future__ import annotations

import unittest
from datetime import datetime, timezone

from pydantic import ValidationError

from api.models import ProxyConfig, SubmitRequest, SubmitResult, TaskStatusResponse
from api.routers.questionnaire import (
    apply_proxy_config,
    disabled_proxy_config,
    proxy_config_from_settings,
    proxy_settings_from_task,
    record_proxy_lease,
)
from db.models import QuestionnaireTask, TaskSubmission
from proxy.config import KuaidailiSettings
from proxy.models import ProxyEndpoint, ProxyLease


class ProxyApiModelTests(unittest.TestCase):
    def test_omitted_proxy_policy_is_explicitly_disabled(self):
        request = SubmitRequest(task_id="task-id", count=1, mode="random")
        policy = request.proxy.model_dump() if request.proxy else disabled_proxy_config()
        self.assertFalse(policy["enabled"])

    def test_explicit_disabled_proxy_policy_remains_disabled(self):
        request = SubmitRequest(
            task_id="task-id", count=1, mode="random", proxy={"enabled": False}
        )
        self.assertFalse(request.proxy.enabled)

    def test_enabled_proxy_requires_area(self):
        with self.assertRaises(ValidationError):
            ProxyConfig(enabled=True, area="")

    def test_submit_request_accepts_task_proxy_policy(self):
        request = SubmitRequest(
            task_id="task-id",
            count=2,
            mode="random",
            proxy={
                "enabled": True,
                "area": " 南京市 ",
                "carrier": 2,
                "verify_exit": True,
                "max_acquire_attempts": 4,
            },
        )
        self.assertEqual(request.proxy.area, "南京市")
        self.assertEqual(request.proxy.carrier, 2)

    def test_task_status_exposes_proxy_without_credentials(self):
        response = TaskStatusResponse(
            task_id="task-id",
            status="completed",
            total=1,
            start_time="2026-08-15T00:00:00+00:00",
            proxy=ProxyConfig(enabled=True, area="南京"),
            results=[
                SubmitResult(
                    index=1,
                    status="success",
                    proxy_endpoint="1.2.3.4:8000",
                    proxy_exit_ip="5.6.7.8",
                )
            ],
        )
        payload = response.model_dump()
        serialized = str(payload)
        self.assertNotIn("password", serialized)
        self.assertNotIn("signature", serialized)


class ProxyDatabaseMappingTests(unittest.TestCase):
    def test_expected_proxy_columns_exist(self):
        task_columns = QuestionnaireTask.__table__.columns
        submission_columns = TaskSubmission.__table__.columns
        for name in (
            "browser_debug",
            "proxy_enabled",
            "proxy_provider",
            "proxy_area",
            "proxy_carrier",
            "proxy_rotate_per_submission",
            "proxy_verify_exit",
            "proxy_required",
            "proxy_max_acquire_attempts",
        ):
            self.assertIn(name, task_columns)
        for name in (
            "proxy_host",
            "proxy_port",
            "proxy_requested_area",
            "proxy_reported_location",
            "proxy_exit_ip",
            "proxy_attempts",
            "failure_stage",
        ):
            self.assertIn(name, submission_columns)

    def test_task_policy_round_trip_uses_environment_credentials(self):
        base = KuaidailiSettings(
            enabled=True,
            secret_id="secret-id",
            signature="signature",
            proxy_username="username",
            proxy_password="password",
            default_area="南京",
        )
        task = QuestionnaireTask(
            url="https://example.com",
            analyzed_schema={},
        )
        policy = ProxyConfig(
            enabled=True,
            area="杭州",
            carrier=1,
            rotate_per_submission=False,
            dedup=False,
            verify_exit=False,
            location_match="strict",
            required=True,
            max_acquire_attempts=5,
        ).model_dump()
        apply_proxy_config(task, policy)
        restored = proxy_settings_from_task(task, base)
        self.assertEqual(restored.default_area, "杭州")
        self.assertEqual(restored.signature, "signature")
        self.assertFalse(restored.rotate_per_submission)
        self.assertEqual(restored.max_acquire_attempts, 5)

    def test_proxy_lease_is_recorded_without_credentials(self):
        submission = TaskSubmission(task_id=None, submit_index=1)
        endpoint = ProxyEndpoint(
            "1.2.3.4",
            8000,
            "secret-user",
            "secret-password",
            location="江苏 南京",
            city_code="320100",
            carrier="电信",
            remaining_seconds=300,
        )
        lease = ProxyLease.from_endpoint(
            endpoint,
            "南京",
            acquired_at=datetime.now(timezone.utc),
        )
        lease.exit_ip = "5.6.7.8"
        lease.verified_location = "中国 江苏 南京 电信"
        lease.latency_ms = 123
        record_proxy_lease(submission, lease)
        self.assertEqual(submission.proxy_host, "1.2.3.4")
        self.assertEqual(submission.proxy_city_code, "320100")
        self.assertEqual(submission.proxy_exit_ip, "5.6.7.8")
        values = " ".join(str(value) for value in submission.__dict__.values())
        self.assertNotIn("secret-user", values)
        self.assertNotIn("secret-password", values)

    def test_environment_policy_contains_no_credentials(self):
        settings = KuaidailiSettings(
            enabled=True,
            secret_id="secret-id",
            signature="signature",
            proxy_username="username",
            proxy_password="password",
            default_area="南京",
        )
        policy = proxy_config_from_settings(settings)
        serialized = str(policy)
        for secret in ("secret-id", "signature", "username", "password"):
            self.assertNotIn(secret, serialized)


if __name__ == "__main__":
    unittest.main()
