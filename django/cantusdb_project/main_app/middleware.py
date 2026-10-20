"""Cancel abandoned searches on the production Linux/Gunicorn stack."""

from __future__ import annotations

import logging
import re
import select
import socket
import threading
import time
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

import psycopg
from django.core.exceptions import ImproperlyConfigured, MiddlewareNotUsed
from django.db import OperationalError, connection
from django.http import HttpRequest, HttpResponse
from psycopg.errors import QueryCanceled
from psycopg.pq import PollingStatus

if TYPE_CHECKING:
    from psycopg.pq import PGcancelConn

logger = logging.getLogger(__name__)

# These routes only read data. Do not extend cancellation to editing requests:
# losing a browser connection must not interrupt a partially completed edit.
SEARCH_PATH = re.compile(
    r"^/(?:chant-search|CanadianChantDB/chant-search|searchms|ci-search|id"
    r"|ajax/(?:melody-search|search-bar))(?:/|$)"
)
POLL_INTERVAL = 0.05
CANCEL_TIMEOUT = 1.0


def require_search_cancellation_support() -> None:
    """Fail the deployment prerequisite check on an unsupported driver."""
    capabilities = getattr(psycopg, "capabilities", None)
    if capabilities is None or not capabilities.has_cancel_safe():
        raise ImproperlyConfigured(
            "Search cancellation requires Psycopg with libpq 17 or newer. "
            "Rebuild the application image with the locked dependencies."
        )


def _send_cancel(
    cancel: PGcancelConn, stopped: threading.Event, deadline: float
) -> None:
    """Poll cancellation without blocking beyond the disconnect deadline."""
    if time.monotonic() >= deadline:
        raise TimeoutError("Search cancellation deadline expired")
    cancel.start()
    while not stopped.is_set():
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("Search cancellation deadline expired")
        status = cancel.poll()
        if status == PollingStatus.OK:
            return
        if status == PollingStatus.FAILED:
            raise psycopg.OperationalError(
                cancel.error_message.decode(errors="replace")
            )
        poller = select.poll()
        poller.register(
            cancel.socket,
            select.POLLOUT if status == PollingStatus.WRITING else select.POLLIN,
        )
        # The socket can change between libpq polls. Short waits also let a
        # completed query stop its sender without waiting for the deadline.
        poller.poll(min(POLL_INTERVAL, remaining) * 1000)


class SearchDisconnected(BaseException):
    """Unwind this request without Django rendering a database-backed error page.

    Like asyncio.CancelledError, cancellation must pass through broad Exception
    handlers. This middleware catches it after transaction/context cleanup.
    """


class SearchCancellation:
    def __init__(self, request_socket: socket.socket) -> None:
        self.disconnected = threading.Event()
        self.poller = select.poll()
        self.poller.register(
            request_socket,
            select.POLLRDHUP | select.POLLHUP | select.POLLERR | select.POLLNVAL,
        )

    def client_left(self) -> bool:
        if self.poller.poll(0):
            self.disconnected.set()
        return self.disconnected.is_set()

    def execute(
        self,
        execute: Callable[..., Any],
        sql: str,
        params: Any,
        many: bool,
        context: dict[str, Any],
    ) -> Any:
        # Allow transaction cleanup and session writes to finish normally.
        # ORM UNION queries can start with a parenthesized SELECT.
        if not sql.lstrip(" \t\r\n(").upper().startswith("SELECT"):
            return execute(sql, params, many, context)
        if self.client_left():
            raise SearchDisconnected

        # Capture libpq's cancellation handle on the request thread. It targets
        # this connection using its backend secret, not an untrusted process ID.
        # libpq explicitly allows a separate thread to use this handle.
        cancel = context["connection"].connection.pgconn.cancel_conn()
        stopped = threading.Event()

        def watch() -> None:
            try:
                warned = False
                deadline = None
                while not stopped.wait(POLL_INTERVAL):
                    if not self.client_left():
                        continue
                    if deadline is None:
                        deadline = time.monotonic() + CANCEL_TIMEOUT
                    try:
                        _send_cancel(cancel, stopped, deadline)
                    except Exception as error:
                        if not warned:
                            logger.warning(
                                "Could not cancel a disconnected search query",
                                exc_info=True,
                            )
                            warned = True
                        if isinstance(error, TimeoutError):
                            return
                    finally:
                        cancel.reset()
                    # A disconnect may precede the query reaching PostgreSQL. Keep
                    # trying within the same deadline until execute() finishes.
            finally:
                cancel.finish()

        watcher = threading.Thread(
            target=watch, name="search-query-cancellation", daemon=True
        )
        try:
            watcher.start()
        except Exception:
            cancel.finish()
            raise
        try:
            try:
                result = execute(sql, params, many, context)
            except OperationalError as error:
                if self.disconnected.is_set() and isinstance(
                    error.__cause__, QueryCanceled
                ):
                    raise SearchDisconnected from error
                raise
        finally:
            stopped.set()
            # The watcher owns and frees its handle, even if this thread is
            # interrupted while joining. Wait before allowing another query.
            watcher.join()
        if self.disconnected.is_set():
            raise SearchDisconnected
        return result


class CancelDisconnectedSearchMiddleware:
    """Bridge Nginx/Gunicorn disconnects to the current PostgreSQL SELECT.

    Other WSGI servers (including the development server), non-Linux systems,
    other database backends and requests outside the search routes pass through.
    Nginx must retain its default proxy_ignore_client_abort=off behavior.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        try:
            require_search_cancellation_support()
        except ImproperlyConfigured as error:
            # Deploy updates the bind-mounted source before rebuilding images.
            # Keep replacement workers serving until the new driver is running;
            # the Nginx prerequisite check still rejects this temporary state.
            logger.warning("Search cancellation is disabled: %s", error)
            raise MiddlewareNotUsed from error
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        request_socket = request.META.get("gunicorn.socket")
        if (
            request.method not in {"GET", "HEAD"}
            or not SEARCH_PATH.match(request.path_info)
            or not isinstance(request_socket, socket.socket)
            or not hasattr(select, "POLLRDHUP")
            or connection.vendor != "postgresql"
        ):
            return self.get_response(request)

        cancellation = SearchCancellation(request_socket)
        try:
            try:
                with connection.execute_wrapper(cancellation.execute):
                    return self.get_response(request)
            except SearchDisconnected:
                # The browser is already gone. Do not render an error template,
                # run its context queries, or send a server-error email.
                return HttpResponse(status=499)
        finally:
            if cancellation.disconnected.is_set():
                # Even a successfully dispatched cancel can arrive after its
                # query finishes. Retire this connection before another request
                # can use it, including when persistent connections are enabled.
                connection.close()
                logger.info("Cancelled database work for a disconnected search")
