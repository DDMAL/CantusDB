"""
Views used by the monitoring stack: a public health check and the
internal-only Prometheus metrics endpoint. See docs/monitoring.md.
"""

import socket

from django.conf import settings
from django.http import Http404, HttpRequest, HttpResponse, JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_safe

from main_app.metrics import database_is_up, redis_is_up, render_metrics


@never_cache
@require_safe
def health(request: HttpRequest) -> JsonResponse:
    """
    Report whether the site can serve requests.

    Returns 503 only when the database is unreachable. Redis backs Celery
    tasks, not page rendering, so a Redis outage is reported as "degraded"
    with a 200 rather than as the site being down.
    """
    database_ok = database_is_up()
    redis_ok = redis_is_up()
    if not database_ok:
        status = "error"
    elif not redis_ok:
        status = "degraded"
    else:
        status = "ok"
    return JsonResponse(
        {
            "status": status,
            "database": "ok" if database_ok else "error",
            "redis": "ok" if redis_ok else "error",
        },
        status=200 if database_ok else 503,
    )


def _arrived_on_metrics_port(request: HttpRequest) -> bool:
    """
    Return whether gunicorn accepted this request on the metrics bind.

    This checks the local port of the connection itself, so it cannot be
    spoofed with request headers. The metrics bind is only reachable on the
    internal compose network; requests proxied from the public site arrive
    on the main bind and are refused.
    """
    request_socket = request.META.get("gunicorn.socket")
    if not isinstance(request_socket, socket.socket):
        return False
    try:
        local_port = request_socket.getsockname()[1]
    except (OSError, IndexError, TypeError):
        return False
    return local_port == settings.CANTUSDB_METRICS_PORT


@never_cache
@require_safe
def metrics(request: HttpRequest) -> HttpResponse:
    """
    Expose Prometheus metrics.

    Only served on the internal metrics port, or anywhere when DEBUG is on
    (the development server has no gunicorn socket). Everything else gets a
    404 so the endpoint is indistinguishable from a missing page.
    """
    if not (settings.DEBUG or _arrived_on_metrics_port(request)):
        raise Http404()
    body, content_type = render_metrics()
    return HttpResponse(body, content_type=content_type)
