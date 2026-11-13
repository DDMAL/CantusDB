# Monitoring

CantusDB exposes a health check and Prometheus metrics. These are scraped and probed by the shared DDMAL monitoring stack (kube-prometheus-stack on k3s, see the `Kubernetes-Monitoring` repository). Its Grafana and Alertmanager handle the dashboards and Slack alerts.

## Endpoints

### `/health/` (public)

Returns JSON and is never cached. It is meant for uptime probes.

| Situation | HTTP status | Body |
|---|---|---|
| Database and Redis reachable | 200 | `{"status": "ok", "database": "ok", "redis": "ok"}` |
| Redis unreachable | 200 | `{"status": "degraded", "database": "ok", "redis": "error"}` |
| Database unreachable | 503 | `{"status": "error", "database": "error", ...}` |

Redis backs Celery tasks, not page rendering. A Redis outage therefore doesn't count as the site being down; it shows up in `cantusdb_dependency_up` instead. The response never includes error details. Failures are logged as warnings by `main_app.metrics`.

The checks are bounded so they finish before the probe and scrape timeouts:
- Connecting to PostgreSQL times out after 3 seconds. This is `connect_timeout` in `DATABASES`, and it applies to the whole app. A `PGCONNECT_TIMEOUT` set in the environment takes precedence.
- The database query times out after 1 second (`statement_timeout`).
- Redis calls time out after 1 second.
- The business metrics queries share a 4 second budget, described under Metrics below.

### `/metrics` (internal only)

Returns metrics in the Prometheus text format. The endpoint only answers when gunicorn accepted the connection on its **metrics bind** (`CANTUSDB_METRICS_PORT`, default `9464`). It checks the local port of the connection socket (`gunicorn.socket`), which request headers cannot spoof. Any other request gets a 404, including requests proxied from the public site on port 8000.

The metrics bind is never published to the host. It is reachable only on the internal Compose network, where nginx proxies a dedicated port to it. That nginx port allows only the monitoring cluster's IP addresses. The deployment side is in `ansible.cantus-db`.

With `DEBUG` on, the endpoint is served on any port, because the development server has no gunicorn socket.

## Gunicorn multiprocess mode

Gunicorn runs several worker processes, and each one counts only the requests it serves. In production, the django container sets `PROMETHEUS_MULTIPROC_DIR` to a tmpfs directory. Every worker writes its metrics there, and `/metrics` aggregates them across all workers. `gunicorn.conf.py` clears the directory when the server starts and drops the files of workers that exit. Only the django service gets this variable. Celery processes do not serve requests, so they don't get it.

Without the variable, which covers the development server and tests, metrics stay in memory in the single process.

Example production command:

```
gunicorn -c gunicorn.conf.py cantusdb.wsgi:application --bind :8000 --bind :9464 --workers 5
```

## Metrics

**Requests**, from [django-prometheus](https://github.com/django-commons/django-prometheus):

| Metric | Labels | Use |
|---|---|---|
| `django_http_requests_total_by_view_transport_method_total` | `view`, `method`, `transport` | Usage per page, e.g. `view="chant-search"`, `"json-cid-export"`, `"csv-export"` |
| `django_http_responses_total_by_status_view_method_total` | `status`, `view`, `method` | Error rates (5xx) per view |
| `django_http_requests_latency_seconds_by_view_method` | `view`, `method` | Latency histogram per view |
| `django_http_exceptions_total_by_type_total` | `type` | Unhandled exceptions |

`view` is the URL pattern name from `main_app/urls.py`. nginx answers some requests without ever reaching Django, so they never appear in these metrics. Examples are 429s from the search concurrency limit and 502s while Django is down. The health probe catches outages.

**Dependencies**, from `main_app/metrics.py`, checked on every scrape:

| Metric | Labels | Meaning |
|---|---|---|
| `cantusdb_dependency_up` | `dependency` = `postgres` \| `redis` | 1 if the service answered, 0 if not |

**Business metrics** come from `BusinessMetricsCollector` in `main_app/metrics.py`. They are all gauges.

| Metric | Labels | Meaning |
|---|---|---|
| `cantusdb_sources` | `published` (`true`/`false`), `production_method` (`manuscript`/`print`) | Sources. Every combination is reported, including zeros |
| `cantusdb_sources_by_status` | `source_status` (one of the `Source.source_status` choices, or `unset`) | Sources by status |
| `cantusdb_chants`, `cantusdb_sequences` | | Total chants and total sequences |
| `cantusdb_chants_with_volpiano` | | Chants with a melody, meaning volpiano is non-empty (same rule as `Source.number_of_melodies`) |
| `cantusdb_chants_proofread` | `field` (`full_text`, `full_text_std`, `volpiano`, `other_fields`) | Chants with that field marked as proofread |
| `cantusdb_objects_created` | `model` (`chant`, `sequence`, `source`), `window` (`24h`, `7d`) | Objects created within the window |
| `cantusdb_objects_updated` | `model`, `window` | Objects saved within the window. This also counts newly created objects |
| `cantusdb_revisions` | `window` | django-reversion revisions, i.e. saved edits |
| `cantusdb_active_editors` | `window` | Distinct users with a revision. Revisions from management commands have no user and don't count |
| `cantusdb_data_check_last_completed_timestamp_seconds` | | Start time of the latest completed data check. Not reported if no check has ever completed |
| `cantusdb_users` | `is_active` | User accounts |
| `cantusdb_users_logged_in` | `window` (`30d`) | Users who logged in within the window |
| `cantusdb_indexers` | | Users with `is_indexer` |
| `cantusdb_group_members` | `group` | Users with a membership in the group (`users.Group`) that hasn't expired. Same rule as `user_group_valid` |
| `cantusdb_business_metrics_up` | | 1 if the metrics were computed, 0 if computing them failed. A failure never fails the scrape |
| `cantusdb_business_metrics_compute_seconds` | | How long the last computation took |
| `cantusdb_business_metrics_computed_timestamp_seconds` | | When the snapshot being served was computed |

Computing these metrics scans whole tables. The result is therefore cached for 5 minutes in the `metrics` cache alias (Redis database 1, separate from the Celery broker on database 0) and shared by all gunicorn workers. If Redis is unavailable, the metrics are computed on every scrape instead.

All the business metrics queries together get 4 seconds (`BUSINESS_METRICS_BUDGET_SECONDS`). Before each query, `statement_timeout` is set to whatever is left of that budget. If a query runs out of time, for example because a migration is locking a table, the business metrics are reported as unavailable (`cantusdb_business_metrics_up 0`). The request and dependency metrics are still served, because the scrape finishes well within Prometheus's 10 second timeout. A failed computation is not cached, so the next scrape tries again.

## Configuration

| Variable | Where | Default | Purpose |
|---|---|---|---|
| `CANTUSDB_METRICS_PORT` | env file | `9464` | Gunicorn bind that `/metrics` answers on |
| `PROMETHEUS_MULTIPROC_DIR` | django service only | unset | Enables multiprocess aggregation; must be a writable, ideally tmpfs, directory |
