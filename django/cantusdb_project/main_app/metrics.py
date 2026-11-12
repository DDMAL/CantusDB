"""
Prometheus collectors and helpers for CantusDB-specific metrics.

Request metrics (rates, status codes, latency per view) come from
django-prometheus. This module adds collectors that read live state
(whether backing services answer) and business metrics computed from the
database, and renders everything for the ``/metrics`` view.
See docs/monitoring.md.
"""

import logging
import os
import time
from collections.abc import Iterator
from datetime import date, datetime, timedelta
from typing import Any

import redis
from django.conf import settings
from django.core.cache import caches
from django.db import connection
from django.db.models import Count, Max, Q
from django.utils import timezone
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    REGISTRY,
    CollectorRegistry,
    generate_latest,
    multiprocess,
)
from prometheus_client.core import GaugeMetricFamily, Metric
from prometheus_client.registry import Collector
from reversion.models import Revision

from main_app.models import Chant, DataCheckReport, Sequence, Source
from users.models import Group, User

logger = logging.getLogger(__name__)

# Keep health checks well inside the blackbox probe and scrape timeouts.
REDIS_TIMEOUT_SECONDS = 1


def database_is_up() -> bool:
    """Return whether the default database answers a trivial query."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception as error:  # pylint: disable=broad-exception-caught
        logger.warning("Database health check failed: %s", error)
        return False
    return True


def redis_is_up() -> bool:
    """Return whether the Celery broker (Redis) answers a PING."""
    client = redis.Redis.from_url(
        settings.CELERY_BROKER_URL,
        socket_timeout=REDIS_TIMEOUT_SECONDS,
        socket_connect_timeout=REDIS_TIMEOUT_SECONDS,
    )
    try:
        return bool(client.ping())
    except (redis.RedisError, OSError) as error:
        logger.warning("Redis health check failed: %s", error)
        return False
    finally:
        client.close()


class DependencyCollector(Collector):
    """Report whether each backing service is reachable, checked on every scrape."""

    def collect(self) -> Iterator[Metric]:
        gauge = GaugeMetricFamily(
            "cantusdb_dependency_up",
            "Whether a backing service answered a health check (1) or not (0).",
            labels=["dependency"],
        )
        gauge.add_metric(["postgres"], float(database_is_up()))
        gauge.add_metric(["redis"], float(redis_is_up()))
        yield gauge


## Business metrics ###########################################################

# Computing these scans whole tables, so a snapshot is cached and shared by
# all gunicorn workers (each scrape may land on a different worker).
BUSINESS_METRICS_CACHE_ALIAS = "metrics"
BUSINESS_METRICS_CACHE_KEY = "cantusdb:business-metrics:v1"
BUSINESS_METRICS_TTL_SECONDS = 300

ACTIVITY_WINDOWS: tuple[tuple[str, timedelta], ...] = (
    ("24h", timedelta(hours=24)),
    ("7d", timedelta(days=7)),
)
LOGIN_WINDOW: tuple[str, timedelta] = ("30d", timedelta(days=30))

# Label value -> BaseChant boolean field.
PROOFREAD_FIELDS: tuple[tuple[str, str], ...] = (
    ("full_text", "manuscript_full_text_proofread"),
    ("full_text_std", "manuscript_full_text_std_proofread"),
    ("volpiano", "volpiano_proofread"),
    ("other_fields", "other_fields_proofread"),
)

# Same definition of "has a melody" as Source.number_of_melodies
# (see main_app/signals.py).
HAS_MELODY = Q(volpiano__isnull=False) & ~Q(volpiano="")

# One metric family as plain data: (name, help, label names,
# [(label values, value), ...]). Plain tuples so snapshots can be cached.
Sample = tuple[tuple[str, ...], float]
FamilySpec = tuple[str, str, tuple[str, ...], list[Sample]]


def _window_counts(now: datetime) -> dict[str, Any]:
    """Aggregate expressions counting rows created/updated in each window."""
    aggregates: dict[str, Any] = {}
    for window, delta in ACTIVITY_WINDOWS:
        since = now - delta
        aggregates[f"created_{window}"] = Count("id", filter=Q(date_created__gte=since))
        aggregates[f"updated_{window}"] = Count("id", filter=Q(date_updated__gte=since))
    return aggregates


def _content_families(now: datetime) -> tuple[list[FamilySpec], dict[str, dict]]:
    """
    Inventory of sources, chants and sequences.

    Also returns each model's per-window created/updated counts, gathered in
    the same table scan, for the editorial activity families.
    """
    method_names = {
        choice.value: choice.label.lower() for choice in Source.ProductionMethodChoices
    }
    # Emit every combination, including zeros, so series don't disappear.
    by_published_method = {
        (published, method): 0 for published in (True, False) for method in method_names
    }
    for row in Source.objects.values("published", "production_method").annotate(
        n=Count("id")
    ):
        key = (row["published"], row["production_method"])
        by_published_method[key] = by_published_method.get(key, 0) + row["n"]

    by_status = {value: 0 for value, _ in Source.source_status_choices}
    by_status["unset"] = 0
    for row in Source.objects.values("source_status").annotate(n=Count("id")):
        status = row["source_status"] or "unset"
        by_status[status] = by_status.get(status, 0) + row["n"]

    proofread = {
        f"proofread_{label}": Count("id", filter=Q(**{field: True}))
        for label, field in PROOFREAD_FIELDS
    }
    chants = Chant.objects.aggregate(
        total=Count("id"),
        with_volpiano=Count("id", filter=HAS_MELODY),
        **proofread,
        **_window_counts(now),
    )
    sequences = Sequence.objects.aggregate(total=Count("id"), **_window_counts(now))
    sources = Source.objects.aggregate(**_window_counts(now))

    families: list[FamilySpec] = [
        (
            "cantusdb_sources",
            "Number of sources, by published state and production method.",
            ("published", "production_method"),
            [
                ((str(published).lower(), method_names.get(method, str(method))), n)
                for (published, method), n in sorted(by_published_method.items())
            ],
        ),
        (
            "cantusdb_sources_by_status",
            "Number of sources, by source status.",
            ("source_status",),
            [((status,), n) for status, n in sorted(by_status.items())],
        ),
        ("cantusdb_chants", "Number of chants.", (), [((), chants["total"])]),
        (
            "cantusdb_sequences",
            "Number of sequences.",
            (),
            [((), sequences["total"])],
        ),
        (
            "cantusdb_chants_with_volpiano",
            "Number of chants with a melody (non-empty volpiano).",
            (),
            [((), chants["with_volpiano"])],
        ),
        (
            "cantusdb_chants_proofread",
            "Number of chants with the given field marked as proofread.",
            ("field",),
            [((label,), chants[f"proofread_{label}"]) for label, _ in PROOFREAD_FIELDS],
        ),
    ]
    window_counts = {"chant": chants, "sequence": sequences, "source": sources}
    return families, window_counts


def _activity_families(
    now: datetime, window_counts: dict[str, dict]
) -> list[FamilySpec]:
    """Recent editing activity and the last completed data check."""
    created: list[Sample] = []
    updated: list[Sample] = []
    for model, counts in window_counts.items():
        for window, _ in ACTIVITY_WINDOWS:
            created.append(((model, window), counts[f"created_{window}"]))
            updated.append(((model, window), counts[f"updated_{window}"]))

    longest = max(delta for _, delta in ACTIVITY_WINDOWS)
    revision_counts: dict[str, Any] = {}
    for window, delta in ACTIVITY_WINDOWS:
        in_window = Q(date_created__gte=now - delta)
        revision_counts[f"revisions_{window}"] = Count("id", filter=in_window)
        # Revisions from management commands have no user and are not counted.
        revision_counts[f"editors_{window}"] = Count(
            "user", filter=in_window, distinct=True
        )
    revisions = Revision.objects.filter(date_created__gte=now - longest).aggregate(
        **revision_counts
    )

    families: list[FamilySpec] = [
        (
            "cantusdb_objects_created",
            "Number of objects created within the window.",
            ("model", "window"),
            created,
        ),
        (
            "cantusdb_objects_updated",
            "Number of objects saved (created or edited) within the window.",
            ("model", "window"),
            updated,
        ),
        (
            "cantusdb_revisions",
            "Number of django-reversion revisions (saved edits) within the window.",
            ("window",),
            [((w,), revisions[f"revisions_{w}"]) for w, _ in ACTIVITY_WINDOWS],
        ),
        (
            "cantusdb_active_editors",
            "Number of distinct users who saved a revision within the window.",
            ("window",),
            [((w,), revisions[f"editors_{w}"]) for w, _ in ACTIVITY_WINDOWS],
        ),
    ]

    last_check = DataCheckReport.objects.filter(completed=True).aggregate(
        latest=Max("created_at")
    )["latest"]
    # Omitted, not zero, when no data check has ever completed.
    if last_check is not None:
        families.append(
            (
                "cantusdb_data_check_last_completed_timestamp_seconds",
                "Unix time at which the most recent completed data check started.",
                (),
                [((), last_check.timestamp())],
            )
        )
    return families


def _user_families(now: datetime, today: date) -> list[FamilySpec]:
    """User accounts and group memberships."""
    login_window, login_delta = LOGIN_WINDOW
    users = User.objects.aggregate(
        active=Count("id", filter=Q(is_active=True)),
        inactive=Count("id", filter=Q(is_active=False)),
        indexers=Count("id", filter=Q(is_indexer=True)),
        logged_in=Count("id", filter=Q(last_login__gte=now - login_delta)),
    )
    # Same rule as main_app.permissions.user_group_valid: a membership counts
    # until its expiration date has passed. This is users.Group, not
    # django.contrib.auth's Group.
    unexpired = Q(groupmembership__expiration__isnull=True) | Q(
        groupmembership__expiration__gte=today
    )
    group_members = (
        Group.objects.annotate(members=Count("groupmembership", filter=unexpired))
        .order_by("name")
        .values_list("name", "members")
    )
    return [
        (
            "cantusdb_users",
            "Number of user accounts, by whether the account is active.",
            ("is_active",),
            [(("true",), users["active"]), (("false",), users["inactive"])],
        ),
        (
            "cantusdb_users_logged_in",
            "Number of users who logged in within the window.",
            ("window",),
            [((login_window,), users["logged_in"])],
        ),
        (
            "cantusdb_indexers",
            "Number of users listed as indexers.",
            (),
            [((), users["indexers"])],
        ),
        (
            "cantusdb_group_members",
            "Number of users with an unexpired membership in the group.",
            ("group",),
            [((name,), members) for name, members in group_members],
        ),
    ]


def compute_business_metrics() -> list[FamilySpec]:
    """Query the database for all business metrics."""
    started = time.perf_counter()
    now = timezone.now()
    content, window_counts = _content_families(now)
    families = (
        content
        + _activity_families(now, window_counts)
        + _user_families(now, date.today())
    )
    families += [
        (
            "cantusdb_business_metrics_compute_seconds",
            "Time taken to compute the cached business metrics snapshot.",
            (),
            [((), time.perf_counter() - started)],
        ),
        (
            "cantusdb_business_metrics_computed_timestamp_seconds",
            "Unix time at which the cached business metrics snapshot was computed.",
            (),
            [((), now.timestamp())],
        ),
    ]
    return families


def get_business_metrics() -> list[FamilySpec]:
    """Return the shared cached snapshot, computing it if missing or expired."""
    cache = caches[BUSINESS_METRICS_CACHE_ALIAS]
    cache_available = True
    try:
        snapshot = cache.get(BUSINESS_METRICS_CACHE_KEY)
    except (redis.RedisError, OSError) as error:
        # Metrics stay available without Redis, just uncached.
        logger.warning("Business metrics cache unavailable: %s", error)
        snapshot, cache_available = None, False
    if snapshot is not None:
        return snapshot

    snapshot = compute_business_metrics()
    if cache_available:
        try:
            cache.set(
                BUSINESS_METRICS_CACHE_KEY, snapshot, BUSINESS_METRICS_TTL_SECONDS
            )
        except (redis.RedisError, OSError) as error:
            logger.warning("Could not cache business metrics: %s", error)
    return snapshot


def _gauge(name: str, documentation: str, labels, samples) -> GaugeMetricFamily:
    gauge = GaugeMetricFamily(name, documentation, labels=list(labels))
    for label_values, value in samples:
        gauge.add_metric(list(label_values), float(value))
    return gauge


class BusinessMetricsCollector(Collector):
    """Expose the business metrics snapshot. A failure never fails the scrape."""

    def collect(self) -> Iterator[Metric]:
        try:
            snapshot = get_business_metrics()
        except Exception as error:  # pylint: disable=broad-exception-caught
            logger.warning("Business metrics could not be computed: %s", error)
            snapshot, up = [], 0
        else:
            up = 1
        for name, documentation, labels, samples in snapshot:
            yield _gauge(name, documentation, labels, samples)
        yield _gauge(
            "cantusdb_business_metrics_up",
            "Whether the business metrics could be computed (1) or not (0).",
            (),
            [((), up)],
        )


# CantusDB collectors live in their own registry: in multiprocess mode the
# request metrics are read from PROMETHEUS_MULTIPROC_DIR into a fresh registry
# on every scrape, which would not include collectors registered on REGISTRY.
CANTUSDB_REGISTRY = CollectorRegistry()
CANTUSDB_REGISTRY.register(DependencyCollector())
CANTUSDB_REGISTRY.register(BusinessMetricsCollector())


def render_metrics() -> tuple[bytes, str]:
    """Return the Prometheus exposition body and its content type."""
    if os.environ.get("PROMETHEUS_MULTIPROC_DIR"):
        # Gunicorn runs several worker processes; aggregate all of their
        # request metrics, not just those of the worker serving this scrape.
        request_registry = CollectorRegistry()
        multiprocess.MultiProcessCollector(request_registry)
    else:
        request_registry = REGISTRY
    body = generate_latest(request_registry) + generate_latest(CANTUSDB_REGISTRY)
    return body, CONTENT_TYPE_LATEST
