"""
Tests for the monitoring views: the public health check and the
internal-only Prometheus metrics endpoint.
"""

import os
import socket
from unittest import skipIf
from unittest.mock import MagicMock, patch

from django.db import OperationalError, connection
from django.test import TestCase, override_settings
from django.urls import reverse

from main_app.metrics import database_is_up, redis_is_up
from main_app.tests.test_metrics import LOCMEM_CACHES


class DependencyCheckTest(TestCase):
    def test_database_is_up(self) -> None:
        self.assertTrue(database_is_up())

    def test_database_check_does_not_leak_statement_timeout(self) -> None:
        with connection.cursor() as cursor:
            cursor.execute("SHOW statement_timeout")
            before = cursor.fetchone()[0]
            self.assertTrue(database_is_up())
            cursor.execute("SHOW statement_timeout")
            self.assertEqual(cursor.fetchone()[0], before)

    @skipIf(os.getenv("PGCONNECT_TIMEOUT"), "PGCONNECT_TIMEOUT overrides the default")
    def test_database_connect_timeout_configured(self) -> None:
        self.assertEqual(connection.settings_dict["OPTIONS"]["connect_timeout"], 3)

    def test_database_is_down(self) -> None:
        broken_connection = MagicMock()
        broken_connection.cursor.side_effect = OperationalError("connection refused")
        with patch("main_app.metrics.connection", broken_connection):
            self.assertFalse(database_is_up())

    @override_settings(CELERY_BROKER_URL="redis://127.0.0.1:1/0")
    def test_redis_is_down(self) -> None:
        self.assertFalse(redis_is_up())

    def test_redis_is_up(self) -> None:
        with patch("main_app.metrics.redis.Redis.ping", return_value=True):
            self.assertTrue(redis_is_up())


@patch("main_app.views.monitoring.redis_is_up", return_value=True)
class HealthViewTest(TestCase):
    def test_healthy(self, _redis_is_up: MagicMock) -> None:
        response = self.client.get(reverse("health"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(), {"status": "ok", "database": "ok", "redis": "ok"}
        )
        self.assertIn("no-cache", response.headers["Cache-Control"])

    def test_database_down_is_unavailable(self, _redis_is_up: MagicMock) -> None:
        with patch("main_app.views.monitoring.database_is_up", return_value=False):
            response = self.client.get(reverse("health"))
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["status"], "error")
        self.assertEqual(response.json()["database"], "error")

    def test_redis_down_is_degraded_not_unavailable(
        self, redis_is_up_mock: MagicMock
    ) -> None:
        redis_is_up_mock.return_value = False
        response = self.client.get(reverse("health"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(), {"status": "degraded", "database": "ok", "redis": "error"}
        )

    def test_anonymous_access_allowed(self, _redis_is_up: MagicMock) -> None:
        # The blackbox prober is not logged in; the URL must not redirect.
        response = self.client.get("/health/")
        self.assertEqual(response.status_code, 200)

    def test_rejects_post(self, _redis_is_up: MagicMock) -> None:
        response = self.client.post(reverse("health"))
        self.assertEqual(response.status_code, 405)


@override_settings(CACHES=LOCMEM_CACHES)
@patch("main_app.metrics.redis_is_up", return_value=False)
class MetricsViewTest(TestCase):
    """
    /metrics is only served when gunicorn accepted the connection on the
    internal metrics bind. Tests use real sockets so the local port check
    runs exactly as it does under gunicorn.
    """

    def setUp(self) -> None:
        self.listener = socket.create_server(("127.0.0.1", 0))
        self.addCleanup(self.listener.close)
        self.listener_port = self.listener.getsockname()[1]

    def get_metrics(self, **extra):
        return self.client.get(reverse("metrics"), **extra)

    def test_not_found_without_gunicorn_socket(self, _redis_is_up: MagicMock) -> None:
        self.assertEqual(self.get_metrics().status_code, 404)

    def test_not_found_on_public_bind(self, _redis_is_up: MagicMock) -> None:
        # The listener is the "public" bind; the metrics port is elsewhere.
        with override_settings(CANTUSDB_METRICS_PORT=self.listener_port + 1):
            response = self.get_metrics(**{"gunicorn.socket": self.listener})
        self.assertEqual(response.status_code, 404)

    def test_server_port_cannot_spoof_metrics_port(
        self, _redis_is_up: MagicMock
    ) -> None:
        with override_settings(CANTUSDB_METRICS_PORT=self.listener_port + 1):
            response = self.get_metrics(
                **{
                    "gunicorn.socket": self.listener,
                    "SERVER_PORT": str(self.listener_port + 1),
                }
            )
        self.assertEqual(response.status_code, 404)

    def test_served_on_metrics_bind(self, _redis_is_up: MagicMock) -> None:
        with override_settings(CANTUSDB_METRICS_PORT=self.listener_port):
            response = self.get_metrics(**{"gunicorn.socket": self.listener})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response["Content-Type"].startswith("text/plain"))
        body = response.content.decode()
        # Request metrics from django-prometheus.
        self.assertIn("django_http_requests_total_by_view_transport_method", body)
        # CantusDB dependency checks.
        self.assertIn('cantusdb_dependency_up{dependency="postgres"} 1.0', body)
        self.assertIn('cantusdb_dependency_up{dependency="redis"} 0.0', body)

    def test_request_metrics_are_labelled_by_view(
        self, _redis_is_up: MagicMock
    ) -> None:
        with patch("main_app.views.monitoring.redis_is_up", return_value=True):
            self.client.get(reverse("health"))
        with override_settings(CANTUSDB_METRICS_PORT=self.listener_port):
            body = self.get_metrics(**{"gunicorn.socket": self.listener})
        self.assertIn('view="health"', body.content.decode())

    @override_settings(DEBUG=True)
    def test_served_without_gunicorn_in_debug(self, _redis_is_up: MagicMock) -> None:
        self.assertEqual(self.get_metrics().status_code, 200)

    def test_non_standard_methods_share_one_label(
        self, _redis_is_up: MagicMock
    ) -> None:
        # Arbitrary method names must not each add metric series.
        for method in ("REVIEWAAA", "REVIEWBBB", "REVIEWCCC"):
            self.client.generic(method, reverse("health"))
        with override_settings(CANTUSDB_METRICS_PORT=self.listener_port):
            body = self.get_metrics(**{"gunicorn.socket": self.listener})
        body = body.content.decode()
        self.assertNotIn("REVIEW", body)
        self.assertIn(
            "django_http_requests_latency_seconds_by_view_method_count"
            '{method="<invalid method>",view="health"}',
            body,
        )
        self.assertIn(
            "django_http_requests_total_by_view_transport_method_total"
            '{method="<invalid method>",transport="http",view="health"}',
            body,
        )
