"""Cancel abandoned searches on the production Linux/Gunicorn stack."""

import logging
import re
import select
import socket
import threading
from collections.abc import Callable
from typing import Any

from django.db import OperationalError, connection
from django.http import HttpRequest, HttpResponse
from psycopg.errors import QueryCanceled

logger = logging.getLogger(__name__)

# These routes only read data. Do not extend cancellation to editing requests:
# losing a browser connection must not interrupt a partially completed edit.
SEARCH_PATH = re.compile(
    r"^/(?:chant-search|CanadianChantDB/chant-search|searchms|ci-search|id"
    r"|ajax/(?:melody-search|search-bar))(?:/|$)"
)
POLL_INTERVAL = 0.05


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
        cancel = context["connection"].connection.pgconn.get_cancel()
        stopped = threading.Event()

        def watch() -> None:
            warned = False
            while not stopped.wait(POLL_INTERVAL):
                if not self.client_left():
                    continue
                try:
                    cancel.cancel()
                except Exception:
                    if not warned:
                        logger.warning(
                            "Could not cancel a disconnected search query",
                            exc_info=True,
                        )
                        warned = True
                # A disconnect may precede the query reaching PostgreSQL. Keep
                # trying until execute() finishes, rather than lose that cancel.

        watcher = threading.Thread(
            target=watch, name="search-query-cancellation", daemon=True
        )
        watcher.start()
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
            # Do not let a late cancellation reach another query/request.
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
