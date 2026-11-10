"""
Prometheus collectors and helpers for CantusDB-specific metrics.

Request metrics (rates, status codes, latency per view) come from
django-prometheus. This module adds collectors that read live state
(e.g. whether backing services answer) and renders everything for the
``/metrics`` view. See docs/monitoring.md.
"""

import logging
import os
from collections.abc import Iterator

import redis
from django.conf import settings
from django.db import connection
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    REGISTRY,
    CollectorRegistry,
    generate_latest,
    multiprocess,
)
from prometheus_client.core import GaugeMetricFamily, Metric
from prometheus_client.registry import Collector

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


# CantusDB collectors live in their own registry: in multiprocess mode the
# request metrics are read from PROMETHEUS_MULTIPROC_DIR into a fresh registry
# on every scrape, which would not include collectors registered on REGISTRY.
CANTUSDB_REGISTRY = CollectorRegistry()
CANTUSDB_REGISTRY.register(DependencyCollector())


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
