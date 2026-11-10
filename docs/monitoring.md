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

## Configuration

| Variable | Where | Default | Purpose |
|---|---|---|---|
| `CANTUSDB_METRICS_PORT` | env file | `9464` | Gunicorn bind that `/metrics` answers on |
| `PROMETHEUS_MULTIPROC_DIR` | django service only | unset | Enables multiprocess aggregation; must be a writable, ideally tmpfs, directory |
