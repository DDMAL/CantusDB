"""
Tests for the business metrics collected in main_app.metrics.
"""

import socket
import time
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import redis
from django.core.cache import caches
from django.db import connection
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from reversion.models import Revision

from main_app.metrics import (
    BUSINESS_METRICS_CACHE_ALIAS,
    BusinessMetricsCollector,
    compute_business_metrics,
)
from main_app.models import Chant, DataCheckConfig, DataCheckReport, Source
from main_app.tasks import FREQUENCY_DELTAS
from main_app.tests.make_fakes import (
    make_fake_chant,
    make_fake_sequence,
    make_fake_source,
    make_fake_user,
    make_groups,
)
from users.models import GroupMembership

# Tests must not depend on Redis: use an in-memory cache for the snapshot.
LOCMEM_CACHES = {
    "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"},
    BUSINESS_METRICS_CACHE_ALIAS: {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "business-metrics-tests",
    },
}


def sleep_in_database(*_args) -> None:
    """Stand-in for a business metrics query blocked in the database."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_sleep(5)")


def show_statement_timeout() -> str:
    with connection.cursor() as cursor:
        cursor.execute("SHOW statement_timeout")
        return cursor.fetchone()[0]


def as_samples(families) -> dict:
    """Flatten family specs to {(metric name, label values...): value}."""
    return {
        (name, *label_values): value
        for name, _, _, samples in families
        for label_values, value in samples
    }


@override_settings(CACHES=LOCMEM_CACHES)
class BusinessMetricsTestCase(TestCase):
    def setUp(self) -> None:
        caches[BUSINESS_METRICS_CACHE_ALIAS].clear()

    def metrics(self) -> dict:
        return as_samples(compute_business_metrics())


class ContentMetricsTest(BusinessMetricsTestCase):
    def test_sources_by_published_and_production_method(self) -> None:
        make_fake_source(published=True)
        make_fake_source(published=True)
        make_fake_source(
            published=True,
            production_method=Source.ProductionMethodChoices.PRINT,
        )
        make_fake_source(published=False)
        metrics = self.metrics()
        self.assertEqual(metrics[("cantusdb_sources", "true", "manuscript")], 2)
        self.assertEqual(metrics[("cantusdb_sources", "true", "print")], 1)
        self.assertEqual(metrics[("cantusdb_sources", "false", "manuscript")], 1)
        # Combinations without sources are reported as zero, not omitted.
        self.assertEqual(metrics[("cantusdb_sources", "false", "print")], 0)

    def test_sources_by_status(self) -> None:
        make_fake_source(source_status="Published / Complete")
        make_fake_source(source_status="Published / Complete")
        make_fake_source(source_status=None)
        metrics = self.metrics()
        self.assertEqual(
            metrics[("cantusdb_sources_by_status", "Published / Complete")], 2
        )
        self.assertEqual(metrics[("cantusdb_sources_by_status", "unset")], 1)
        self.assertEqual(
            metrics[("cantusdb_sources_by_status", "Unpublished / Editing process")],
            0,
        )

    def test_chant_and_sequence_counts(self) -> None:
        source = make_fake_source()
        make_fake_chant(source=source, volpiano="1---c---d---e")
        make_fake_chant(source=source, volpiano="")
        make_fake_chant(source=source, volpiano=None)
        make_fake_chant(
            source=source,
            manuscript_full_text_proofread=True,
            volpiano_proofread=True,
        )
        make_fake_sequence(source=source)
        metrics = self.metrics()
        self.assertEqual(metrics[("cantusdb_chants",)], 4)
        self.assertEqual(metrics[("cantusdb_sequences",)], 1)
        # Empty and missing volpiano are not melodies; the fake default is.
        self.assertEqual(
            metrics[("cantusdb_chants_with_volpiano",)],
            Chant.objects.exclude(volpiano__isnull=True)
            .exclude(volpiano__exact="")
            .count(),
        )
        self.assertEqual(metrics[("cantusdb_chants_with_volpiano",)], 2)
        self.assertEqual(metrics[("cantusdb_chants_proofread", "full_text")], 1)
        self.assertEqual(metrics[("cantusdb_chants_proofread", "volpiano")], 1)
        self.assertEqual(metrics[("cantusdb_chants_proofread", "full_text_std")], 0)
        self.assertEqual(metrics[("cantusdb_chants_proofread", "other_fields")], 0)


class ActivityMetricsTest(BusinessMetricsTestCase):
    def test_created_and_updated_windows(self) -> None:
        source = make_fake_source()
        make_fake_chant(source=source)  # created just now
        this_week = make_fake_chant(source=source)
        old = make_fake_chant(source=source)
        now = timezone.now()
        # date_created/date_updated are auto fields; backdate with update().
        Chant.objects.filter(pk=this_week.pk).update(
            date_created=now - timedelta(days=3), date_updated=now - timedelta(days=3)
        )
        Chant.objects.filter(pk=old.pk).update(
            date_created=now - timedelta(days=30), date_updated=now - timedelta(hours=1)
        )
        Source.objects.filter(pk=source.pk).update(
            date_created=now - timedelta(days=30), date_updated=now - timedelta(days=30)
        )
        metrics = self.metrics()
        self.assertEqual(metrics[("cantusdb_objects_created", "chant", "24h")], 1)
        self.assertEqual(metrics[("cantusdb_objects_created", "chant", "7d")], 2)
        # The old chant was edited an hour ago.
        self.assertEqual(metrics[("cantusdb_objects_updated", "chant", "24h")], 2)
        self.assertEqual(metrics[("cantusdb_objects_updated", "chant", "7d")], 3)
        self.assertEqual(metrics[("cantusdb_objects_created", "source", "7d")], 0)
        self.assertEqual(metrics[("cantusdb_objects_updated", "source", "7d")], 0)
        self.assertEqual(metrics[("cantusdb_objects_created", "sequence", "7d")], 0)

    def test_revisions_and_active_editors(self) -> None:
        editor = make_fake_user()
        other_editor = make_fake_user()
        now = timezone.now()
        Revision.objects.create(user=editor, date_created=now - timedelta(hours=1))
        Revision.objects.create(user=editor, date_created=now - timedelta(hours=2))
        Revision.objects.create(user=other_editor, date_created=now - timedelta(days=3))
        # Management commands save revisions without a user.
        Revision.objects.create(user=None, date_created=now - timedelta(hours=1))
        Revision.objects.create(user=editor, date_created=now - timedelta(days=30))
        metrics = self.metrics()
        self.assertEqual(metrics[("cantusdb_revisions", "24h")], 3)
        self.assertEqual(metrics[("cantusdb_revisions", "7d")], 4)
        self.assertEqual(metrics[("cantusdb_active_editors", "24h")], 1)
        self.assertEqual(metrics[("cantusdb_active_editors", "7d")], 2)


@override_settings(DATA_CHECKS_ENABLED=True)
class DataCheckMetricsTest(BusinessMetricsTestCase):
    LAST_RUN = ("cantusdb_data_check_last_run_timestamp_seconds",)
    INTERVAL = ("cantusdb_data_check_interval_seconds",)

    def test_reports_last_run_and_interval_of_latest_config(self) -> None:
        last_run = timezone.now() - timedelta(days=2)
        DataCheckConfig.objects.create(
            frequency=DataCheckConfig.Frequency.DAILY,
            last_run=last_run - timedelta(days=30),
        )
        # run_data_checks uses the most recently created configuration.
        DataCheckConfig.objects.create(
            frequency=DataCheckConfig.Frequency.WEEKLY, last_run=last_run
        )
        metrics = self.metrics()
        self.assertAlmostEqual(metrics[self.LAST_RUN], last_run.timestamp(), places=3)
        self.assertEqual(metrics[self.INTERVAL], timedelta(weeks=1).total_seconds())

    def test_interval_follows_configured_frequency(self) -> None:
        config = DataCheckConfig.objects.create(last_run=timezone.now())
        for frequency, interval in FREQUENCY_DELTAS.items():
            with self.subTest(frequency=frequency):
                config.frequency = frequency
                config.save()
                self.assertEqual(
                    self.metrics()[self.INTERVAL], interval.total_seconds()
                )

    def test_staff_review_checkbox_does_not_count_as_a_run(self) -> None:
        # DataCheckReport.completed means "reviewed by staff", not "ran".
        DataCheckReport.objects.create(completed=True)
        DataCheckConfig.objects.create()
        metrics = self.metrics()
        self.assertNotIn(self.LAST_RUN, metrics)
        self.assertNotIn(self.INTERVAL, metrics)

    def test_omitted_without_configuration(self) -> None:
        self.assertNotIn(self.LAST_RUN, self.metrics())

    @override_settings(DATA_CHECKS_ENABLED=False)
    def test_omitted_when_checks_are_disabled(self) -> None:
        # Staging has production's configuration but never runs the checks.
        DataCheckConfig.objects.create(last_run=timezone.now())
        metrics = self.metrics()
        self.assertNotIn(self.LAST_RUN, metrics)
        self.assertNotIn(self.INTERVAL, metrics)


class UserMetricsTest(BusinessMetricsTestCase):
    def test_user_counts(self) -> None:
        active = make_fake_user()
        inactive = make_fake_user()
        inactive.is_active = False
        inactive.save()
        indexer = make_fake_user()
        indexer.is_indexer = True
        indexer.save()
        now = timezone.now()
        active.last_login = now - timedelta(days=1)
        active.save()
        indexer.last_login = now - timedelta(days=60)
        indexer.save()
        metrics = self.metrics()
        self.assertEqual(metrics[("cantusdb_users", "true")], 2)
        self.assertEqual(metrics[("cantusdb_users", "false")], 1)
        self.assertEqual(metrics[("cantusdb_indexers",)], 1)
        self.assertEqual(metrics[("cantusdb_users_logged_in", "30d")], 1)

    def test_group_members_exclude_expired_memberships(self) -> None:
        groups = make_groups()
        editor, viewer = groups["editor"], groups["global viewer"]
        today = date.today()
        make_fake_user(groups=[(editor, today + timedelta(days=10))])
        # Expires today: still valid, as in permissions.user_group_valid.
        make_fake_user(groups=[(editor, today)])
        make_fake_user(groups=[(editor, today - timedelta(days=1))])
        no_expiry = make_fake_user()
        GroupMembership.objects.create(user=no_expiry, group=viewer, expiration=None)
        metrics = self.metrics()
        self.assertEqual(metrics[("cantusdb_group_members", "editor")], 2)
        self.assertEqual(metrics[("cantusdb_group_members", "global viewer")], 1)


class BusinessMetricsCollectorTest(BusinessMetricsTestCase):
    def collect(self) -> dict:
        return {
            (sample.name, *sample.labels.values()): sample.value
            for family in BusinessMetricsCollector().collect()
            for sample in family.samples
        }

    def test_snapshot_is_cached(self) -> None:
        make_fake_source()
        first = self.collect()
        self.assertEqual(first[("cantusdb_business_metrics_up",)], 1)
        make_fake_source()
        with self.assertNumQueries(0):
            second = self.collect()
        # Served from the cache, so the new source is not counted yet.
        self.assertEqual(
            second[("cantusdb_sources", "true", "manuscript")],
            first[("cantusdb_sources", "true", "manuscript")],
        )
        caches[BUSINESS_METRICS_CACHE_ALIAS].clear()
        self.assertEqual(
            self.collect()[("cantusdb_sources", "true", "manuscript")],
            first[("cantusdb_sources", "true", "manuscript")] + 1,
        )

    def test_failure_reports_down_without_raising(self) -> None:
        with patch(
            "main_app.metrics.compute_business_metrics",
            side_effect=RuntimeError("database unavailable"),
        ):
            samples = self.collect()
        self.assertEqual(samples, {("cantusdb_business_metrics_up",): 0})

    def test_failure_is_not_cached(self) -> None:
        with patch(
            "main_app.metrics.compute_business_metrics",
            side_effect=RuntimeError("database unavailable"),
        ):
            self.collect()
        self.assertEqual(self.collect()[("cantusdb_business_metrics_up",)], 1)

    def test_queries_over_budget_report_down(self) -> None:
        statement_timeout_before = show_statement_timeout()
        started = time.monotonic()
        with patch("main_app.metrics.BUSINESS_METRICS_BUDGET_SECONDS", 0.2), patch(
            "main_app.metrics._content_families", side_effect=sleep_in_database
        ):
            samples = self.collect()
        # PostgreSQL cancelled the query at the budget, not after pg_sleep(5).
        self.assertLess(time.monotonic() - started, 2)
        self.assertEqual(samples, {("cantusdb_business_metrics_up",): 0})
        # The per-query limit does not stay on the connection.
        self.assertEqual(show_statement_timeout(), statement_timeout_before)

    def test_budget_used_up_before_a_query_reports_down(self) -> None:
        with patch("main_app.metrics.BUSINESS_METRICS_BUDGET_SECONDS", 0):
            samples = self.collect()
        self.assertEqual(samples, {("cantusdb_business_metrics_up",): 0})

    def test_computes_without_cache_when_redis_is_down(self) -> None:
        broken_cache = MagicMock()
        broken_cache.get.side_effect = redis.ConnectionError("refused")
        with patch("main_app.metrics.caches") as caches_mock:
            caches_mock.__getitem__.return_value = broken_cache
            samples = self.collect()
        self.assertEqual(samples[("cantusdb_business_metrics_up",)], 1)
        self.assertIn(("cantusdb_chants",), samples)
        broken_cache.set.assert_not_called()


@override_settings(CACHES=LOCMEM_CACHES)
@patch("main_app.metrics.redis_is_up", return_value=True)
class MetricsEndpointBusinessMetricsTest(TestCase):
    def setUp(self) -> None:
        caches[BUSINESS_METRICS_CACHE_ALIAS].clear()
        self.listener = socket.create_server(("127.0.0.1", 0))
        self.addCleanup(self.listener.close)

    def test_business_metrics_are_exposed(self, _redis_is_up: MagicMock) -> None:
        make_fake_source(published=True)
        with override_settings(CANTUSDB_METRICS_PORT=self.listener.getsockname()[1]):
            response = self.client.get(
                reverse("metrics"), **{"gunicorn.socket": self.listener}
            )
        self.assertEqual(response.status_code, 200)
        body = response.content.decode()
        self.assertIn(
            'cantusdb_sources{production_method="manuscript",published="true"} 1.0',
            body,
        )
        self.assertIn("cantusdb_business_metrics_up 1.0", body)
        self.assertIn("# TYPE cantusdb_group_members gauge", body)

    def test_slow_business_metrics_keep_the_rest_of_the_scrape(
        self, _redis_is_up: MagicMock
    ) -> None:
        with patch("main_app.metrics.BUSINESS_METRICS_BUDGET_SECONDS", 0.2), patch(
            "main_app.metrics._content_families", side_effect=sleep_in_database
        ), override_settings(CANTUSDB_METRICS_PORT=self.listener.getsockname()[1]):
            response = self.client.get(
                reverse("metrics"), **{"gunicorn.socket": self.listener}
            )
        self.assertEqual(response.status_code, 200)
        body = response.content.decode()
        self.assertIn("cantusdb_business_metrics_up 0.0", body)
        self.assertIn('cantusdb_dependency_up{dependency="postgres"} 1.0', body)
        self.assertIn("django_http_requests_total_by_view_transport_method", body)
