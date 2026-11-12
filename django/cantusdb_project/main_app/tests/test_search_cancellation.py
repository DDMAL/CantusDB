"""Exercise cancellation against PostgreSQL, not a mocked query executor."""

import io
import logging
import multiprocessing
import select
import socket
import socketserver
import struct
import threading
import time
from queue import Queue
from collections.abc import Callable
from typing import Any
from types import SimpleNamespace
from unittest import skipUnless
from unittest.mock import patch

import psycopg
from psycopg.errors import QueryCanceled
from django.contrib.auth import get_user_model
from django.core.exceptions import ImproperlyConfigured
from django.db import OperationalError, connection, transaction
from django.db.models.expressions import RawSQL
from django.http import Http404, HttpRequest, HttpResponse, JsonResponse
from django.test import TransactionTestCase, override_settings
from django.urls import path

from main_app.middleware import (
    CANCEL_TIMEOUT,
    SearchCancellation,
    SearchDisconnected,
    _send_cancel,
    require_search_cancellation_support,
)
from main_app.models import Chant, Sequence
from main_app.tests.make_fakes import (
    make_fake_chant,
    make_fake_sequence,
    make_fake_source,
)

started: Queue[int] = Queue()


def search_view(request: HttpRequest) -> JsonResponse:
    with connection.cursor() as cursor:
        if request.GET.get("slow"):
            started.put(connection.connection.info.backend_pid)
            cursor.execute("SELECT pg_sleep(10) /* cancellation_test */")
        cursor.execute("SELECT 42")
        value = cursor.fetchone()[0]
    return JsonResponse({"value": value})


def missing_search(request: HttpRequest) -> JsonResponse:
    raise Http404


def error_response(request: HttpRequest, status: int) -> HttpResponse:
    return HttpResponse(status=status)


def transport_search(request: HttpRequest) -> JsonResponse:
    with connection.cursor() as cursor:
        started.put(connection.connection.info.backend_pid)
        cursor.execute(
            "SELECT 42, pg_sleep(%s) /* cancellation_test */",
            [float(request.GET["delay"])],
        )
        return JsonResponse({"value": cursor.fetchone()[0]})


urlpatterns = [
    path("chant-search/", search_view),
    path("CanadianChantDB/chant-search/", search_view),
    path("ajax/melody-search/", search_view),
    path("ajax/search-bar/test", search_view),
    path("searchms/123", search_view),
    path("ci-search/test", search_view),
    path("id/001234", search_view),
    path("chant/123/", search_view),
    path("chant-search/missing", missing_search),
    path("chant-search/error/<int:status>", error_response),
    path("chant-search/transport", transport_search),
]


def stalled_cancel_proxy(
    target: tuple[str, int],
    pipe: Any,
    inherited_sockets: tuple[socket.socket, socket.socket],
) -> None:
    """Forward real SQL but hold cancellation open until its sender gives up.

    A separate process lets the test fail even if a blocking driver call holds
    Python's interpreter lock. No PostgreSQL credentials or secrets are logged.
    """
    # A forked copy of the browser socket would hide the parent's disconnect.
    for inherited in inherited_sockets:
        inherited.close()

    class Handler(socketserver.BaseRequestHandler):
        def read_exact(self, count: int) -> bytes:
            data = b""
            while len(data) < count:
                chunk = self.request.recv(count - len(data))
                if not chunk:
                    break
                data += chunk
            return data

        def handle(self) -> None:
            self.request.settimeout(3)
            header = self.read_exact(8)
            if len(header) != 8:
                return
            if struct.unpack("!II", header) == (16, 80877102):
                self.read_exact(8)  # Consume the backend PID and secret.
                received = time.monotonic()
                try:
                    closed = self.request.recv(1) == b""
                except socket.timeout:
                    closed = False
                pipe.send((closed, received, time.monotonic()))
                return
            with socket.create_connection(target, timeout=3) as upstream:
                upstream.sendall(header)
                peers = {self.request: upstream, upstream: self.request}
                while True:
                    readable, _, _ = select.select(list(peers), [], [], 3)
                    if not readable:
                        return
                    for source in readable:
                        data = source.recv(65536)
                        if not data:
                            return
                        peers[source].sendall(data)

    class Server(socketserver.ThreadingTCPServer):
        daemon_threads = True

    with Server(("127.0.0.1", 0), Handler) as server:
        pipe.send(server.server_address[1])
        server.serve_forever()


@skipUnless(hasattr(select, "POLLRDHUP"), "Cancellation requires Linux poll")
@override_settings(ROOT_URLCONF=__name__, SECURE_SSL_REDIRECT=False)
class SearchCancellationTests(TransactionTestCase):
    def setUp(self) -> None:
        self.server, self.client_socket = socket.socketpair()
        self.addCleanup(self.server.close)
        self.addCleanup(self.client_socket.close)
        while not started.empty():
            started.get_nowait()
        connection.ensure_connection()
        self.db_params = connection.get_connection_params()

    def disconnect_during_query(self) -> threading.Thread:
        self.observer_errors: list[BaseException] = []

        def observe() -> None:
            try:
                pid = started.get(timeout=3)
                with psycopg.connect(**self.db_params, autocommit=True) as observer:
                    deadline = time.monotonic() + 3
                    while time.monotonic() < deadline:
                        row = observer.execute(
                            "SELECT state, query FROM pg_stat_activity WHERE pid = %s",
                            [pid],
                        ).fetchone()
                        if row and row[0] == "active" and "cancellation_test" in row[1]:
                            self.client_socket.close()
                            # The observer is a different connection and must
                            # remain usable while the request query is cancelled.
                            self.assertEqual(
                                observer.execute("SELECT 7").fetchone(), (7,)
                            )
                            return
                        time.sleep(0.01)
                    self.fail("Search never reached the expected PostgreSQL query")
            except BaseException as error:
                self.observer_errors.append(error)
                self.client_socket.close()

        observer = threading.Thread(target=observe)
        observer.start()
        self.addCleanup(observer.join)
        return observer

    def test_abandoned_search_stops_database_work_and_next_request_succeeds(
        self,
    ) -> None:
        observer = self.disconnect_during_query()
        start = time.monotonic()
        response = self.client.get(
            "/ajax/melody-search/?slow=1", **{"gunicorn.socket": self.server}
        )
        elapsed = time.monotonic() - start
        observer.join()
        self.assertEqual(self.observer_errors, [])
        self.assertEqual(response.status_code, 499)
        self.assertLess(elapsed, 3, "The ten-second query must actually be cancelled")
        self.assertIsNone(
            connection.connection, "Cancelled connections must be retired"
        )
        self.assertEqual(self.client.get("/ajax/melody-search/").json(), {"value": 42})
        self.assertFalse(
            any(t.name == "search-query-cancellation" for t in threading.enumerate())
        )

    def test_completed_searches_keep_their_results_on_all_supported_routes(
        self,
    ) -> None:
        for route in (
            "/chant-search/",
            "/CanadianChantDB/chant-search/",
            "/ajax/melody-search/",
            "/ajax/search-bar/test",
            "/searchms/123",
            "/ci-search/test",
            "/id/001234",
        ):
            with self.subTest(route=route):
                response = self.client.get(route, **{"gunicorn.socket": self.server})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json(), {"value": 42})

    def test_already_disconnected_search_returns_cancelled_response(self) -> None:
        self.client_socket.close()
        response = self.client.get("/chant-search/", **{"gunicorn.socket": self.server})
        self.assertEqual(response.status_code, 499)

    @override_settings(DEBUG=False)
    def test_disconnect_logs_once_at_info_with_production_logging(self) -> None:
        self.client_socket.close()
        logger = logging.getLogger("main_app.middleware")
        self.assertTrue(logger.isEnabledFor(logging.INFO))
        output = io.StringIO()
        # Exercise the configured console handler, without assertLogs changing
        # the logger's level and masking missing production configuration.
        with patch.object(logger.handlers[0], "stream", output):
            with self.assertNoLogs("django.request", level="WARNING"):
                response = self.client.get(
                    "/chant-search/?private-search=text",
                    **{"gunicorn.socket": self.server},
                )
        self.assertEqual(response.status_code, 499)
        self.assertEqual(
            output.getvalue().splitlines(),
            ["Client disconnected from search: /chant-search/"],
        )

    @override_settings(DEBUG=False)
    def test_other_request_warnings_and_errors_are_still_logged(self) -> None:
        for route, status, level in (
            ("/chant-search/error/404", 404, "WARNING"),
            ("/chant-search/error/500", 500, "ERROR"),
        ):
            with self.subTest(status=status):
                with self.assertLogs("django.request", level=level) as log:
                    response = self.client.get(
                        route, **{"gunicorn.socket": self.server}
                    )
                self.assertEqual(response.status_code, status)
                self.assertEqual(len(log.records), 1)
                self.assertEqual(log.records[0].levelname, level)
                self.assertEqual(log.records[0].status_code, status)

    def test_disconnect_during_flatpage_fallback_is_not_a_server_error(self) -> None:
        self.client_socket.close()
        response = self.client.get(
            "/chant-search/missing", **{"gunicorn.socket": self.server}
        )
        self.assertEqual(response.status_code, 499)

    def test_nonsearch_and_post_requests_are_not_cancelled(self) -> None:
        self.client_socket.close()
        response = self.client.get("/chant/123/", **{"gunicorn.socket": self.server})
        self.assertEqual(response.json(), {"value": 42})
        response = self.client.post(
            "/chant-search/", **{"gunicorn.socket": self.server}
        )
        self.assertEqual(response.json(), {"value": 42})

    def test_development_server_without_gunicorn_socket_keeps_working(self) -> None:
        self.assertEqual(self.client.get("/chant-search/").json(), {"value": 42})

    @override_settings(ROOT_URLCONF="cantusdb.urls")
    def test_real_melody_search_preserves_results_and_source_access(self) -> None:
        public = make_fake_chant(
            source=make_fake_source(published=True), volpiano="1---a-b-c---4"
        )
        assigned = make_fake_chant(
            source=make_fake_source(published=False), volpiano="1---a-b-c---4"
        )
        private = make_fake_chant(
            source=make_fake_source(published=False), volpiano="1---a-b-c---4"
        )
        user = get_user_model().objects.create_user(
            email="search-reader@example.test", password=None
        )
        assigned.source.current_editors.add(user)

        def result_ids() -> list[int]:
            response = self.client.get(
                "/ajax/melody-search/?notes=abc",
                **{"gunicorn.socket": self.server},
            )
            self.assertEqual(response.status_code, 200)
            body = response.json()
            self.assertEqual(body["result_count"], len(body["results"]))
            return [row["id"] for row in body["results"]]

        self.assertEqual(result_ids(), [public.id])
        self.client.force_login(user)
        self.assertCountEqual(result_ids(), [public.id, assigned.id])
        user.is_superuser = True
        user.is_staff = True
        user.save()
        self.assertCountEqual(result_ids(), [public.id, assigned.id, private.id])

    def test_other_database_errors_are_not_reported_as_cancellation(self) -> None:
        cancellation = SearchCancellation(self.server)
        with connection.execute_wrapper(cancellation.execute):
            with self.assertRaisesMessage(Exception, "division by zero"):
                with connection.cursor() as cursor:
                    cursor.execute("SELECT 1 / 0")
        self.assertFalse(cancellation.disconnected.is_set())

    def test_disconnect_does_not_hide_an_unrelated_operational_error(self) -> None:
        cancellation = SearchCancellation(self.server)
        failure = OperationalError("database connection lost")

        def fail_after_disconnect(*_args: Any) -> Any:
            self.client_socket.close()
            cancellation.disconnected.set()
            raise failure from psycopg.OperationalError("database connection lost")

        with connection.execute_wrapper(cancellation.execute):
            with connection.execute_wrapper(fail_after_disconnect):
                with self.assertRaises(OperationalError) as caught:
                    with connection.cursor() as cursor:
                        cursor.execute("SELECT 1")
        self.assertIs(caught.exception, failure)
        connection.close()

    def test_parenthesized_union_query_is_cancelled(self) -> None:
        chant = make_fake_chant()
        sequence = make_fake_sequence()
        # Use Django's actual UNION compiler, as chant search and /id/ do.
        rows = (
            Chant.objects.filter(pk=chant.pk)
            .order_by()
            .annotate(pause=RawSQL("pg_sleep(10) /* cancellation_test */", []))
            .values_list("pk", "pause")
        )
        sequence_rows = (
            Sequence.objects.filter(pk=sequence.pk)
            .order_by()
            .annotate(pause=RawSQL("pg_sleep(10) /* cancellation_test */", []))
            .values_list("pk", "pause")
        )
        query = rows.union(sequence_rows, all=True)
        cancellation = SearchCancellation(self.server)
        observer = self.disconnect_during_query()

        def announce_query(
            execute: Callable[..., Any],
            sql: str,
            params: Any,
            many: bool,
            context: dict[str, Any],
        ) -> Any:
            started.put(connection.connection.info.backend_pid)
            return execute(sql, params, many, context)

        start = time.monotonic()
        with connection.execute_wrapper(cancellation.execute):
            with connection.execute_wrapper(announce_query):
                with self.assertRaises(SearchDisconnected):
                    list(query)
        observer.join()
        self.assertEqual(self.observer_errors, [])
        self.assertLess(time.monotonic() - start, 3)
        connection.close()

    def test_cancel_before_query_is_sent_is_retried(self) -> None:
        cancellation = SearchCancellation(self.server)
        # Wait for a real cancel to reach the idle backend before sending SQL.
        # A later cancel must still stop the subsequent query.
        first_dispatch = threading.Event()

        def announce_dispatch(*args: Any) -> bool:
            dispatched = _send_cancel(*args)
            if dispatched:
                first_dispatch.set()
            return dispatched

        original_client_left = cancellation.client_left
        first_check = True

        def disconnect_after_initial_check() -> bool:
            nonlocal first_check
            if first_check:
                first_check = False
                self.client_socket.close()
                return False
            return original_client_left()

        def delayed_execute(
            execute: Callable[..., Any],
            sql: str,
            params: Any,
            many: bool,
            context: dict[str, Any],
        ) -> Any:
            self.assertTrue(first_dispatch.wait(3), "First cancel was not dispatched")
            return execute(sql, params, many, context)

        with patch.object(
            cancellation, "client_left", disconnect_after_initial_check
        ), patch("main_app.middleware._send_cancel", side_effect=announce_dispatch):
            start = time.monotonic()
            with connection.execute_wrapper(cancellation.execute):
                with connection.execute_wrapper(delayed_execute):
                    with self.assertRaises(SearchDisconnected):
                        with connection.cursor() as cursor:
                            cursor.execute("SELECT pg_sleep(10)")
            self.assertLess(time.monotonic() - start, 3)
        connection.close()

    def test_successful_dispatch_does_not_become_a_failure_at_retry_deadline(
        self,
    ) -> None:
        cancellation = SearchCancellation(self.server)
        observer = self.disconnect_during_query()

        def delay_cancelled_result(
            execute: Callable[..., Any],
            sql: str,
            params: Any,
            many: bool,
            context: dict[str, Any],
        ) -> Any:
            started.put(connection.connection.info.backend_pid)
            try:
                return execute(sql, params, many, context)
            except OperationalError as error:
                if not isinstance(error.__cause__, QueryCanceled):
                    raise
                # PostgreSQL has cancelled the real query, but the request
                # thread has not yet returned from execute().
                time.sleep(CANCEL_TIMEOUT + 0.2)
                raise

        with self.assertLogs("main_app.middleware", level="INFO") as log:
            with connection.execute_wrapper(cancellation.execute):
                with connection.execute_wrapper(delay_cancelled_result):
                    with self.assertRaises(SearchDisconnected):
                        with connection.cursor() as cursor:
                            cursor.execute(
                                "SELECT pg_sleep(10) /* cancellation_test */"
                            )
        observer.join()
        self.assertEqual(self.observer_errors, [])
        self.assertEqual(len(log.records), 1)
        self.assertEqual(log.records[0].levelname, "INFO")
        self.assertIn("retry deadline reached after dispatch", log.output[0])
        self.assertFalse(
            any(t.name == "search-query-cancellation" for t in threading.enumerate())
        )
        connection.close()

    def test_transaction_cleanup_is_allowed_after_cancellation(self) -> None:
        cancellation = SearchCancellation(self.server)
        with connection.execute_wrapper(cancellation.execute):
            with transaction.atomic():
                try:
                    with transaction.atomic():
                        self.client_socket.close()
                        with connection.cursor() as cursor:
                            cursor.execute("SELECT 1")
                except SearchDisconnected:
                    pass
                # Rolling back the inner savepoint must not raise another
                # cancellation or leave the outer transaction broken.
                self.assertFalse(connection.needs_rollback)
        with connection.cursor() as cursor:
            cursor.execute("SELECT 42")
            self.assertEqual(cursor.fetchone(), (42,))

    def run_stalled_cancel(self, query_seconds: float) -> float:
        context = multiprocessing.get_context("fork")
        parent, child = context.Pipe()
        target = (self.db_params["host"], int(self.db_params.get("port") or 5432))
        proxy = context.Process(
            target=stalled_cancel_proxy,
            args=(target, child, (self.server, self.client_socket)),
        )
        proxy.start()
        try:
            self.assertTrue(parent.poll(3), "Cancellation proxy did not start")
            params = dict(
                self.db_params,
                host="127.0.0.1",
                port=parent.recv(),
                sslmode="disable",
                gssencmode="disable",
            )
            connection.close()
            observer = self.disconnect_during_query()
            before = time.monotonic()
            with patch.object(connection, "get_connection_params", return_value=params):
                response = self.client.get(
                    f"/chant-search/transport?delay={query_seconds}",
                    **{"gunicorn.socket": self.server},
                )
            returned = time.monotonic()
            observer.join()
            self.assertEqual(self.observer_errors, [])
            self.assertEqual(response.status_code, 499)
            self.assertLess(returned - before, query_seconds + 0.75)
            self.assertTrue(parent.poll(2), "Cancellation socket was not closed")
            closed, received_at, closed_at = parent.recv()
            self.assertTrue(closed, "Proxy had to release a stuck cancellation sender")
            self.assertLessEqual(closed_at, returned + 0.1)
            self.assertIsNone(connection.connection)
            self.assertFalse(
                any(
                    t.name == "search-query-cancellation" for t in threading.enumerate()
                )
            )
            self.assertEqual(self.client.get("/chant-search/").json(), {"value": 42})
            return closed_at - received_at
        finally:
            connection.close()
            proxy.terminate()
            proxy.join(3)
            parent.close()
            child.close()

    def test_finished_sql_does_not_wait_for_stalled_cancellation(self) -> None:
        with self.assertNoLogs("main_app.middleware", level="WARNING"):
            cancel_seconds = self.run_stalled_cancel(0.25)
        self.assertLess(cancel_seconds, 0.75)

    def test_stalled_cancellation_expires_while_sql_is_still_running(self) -> None:
        with self.assertLogs("main_app.middleware", level="WARNING") as log:
            cancel_seconds = self.run_stalled_cancel(CANCEL_TIMEOUT + 0.5)
        self.assertLess(cancel_seconds, CANCEL_TIMEOUT + 0.25)
        self.assertEqual(len(log.records), 1)
        self.assertIsInstance(log.records[0].exc_info[1], TimeoutError)

    def test_connected_search_can_run_longer_than_cancellation_deadline(self) -> None:
        response = self.client.get(
            f"/chant-search/transport?delay={CANCEL_TIMEOUT + 0.1}",
            **{"gunicorn.socket": self.server},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"value": 42})

    def test_deployment_check_rejects_unsupported_cancellation(self) -> None:
        with patch(
            "main_app.middleware.psycopg.capabilities.has_cancel_safe",
            return_value=False,
        ):
            with self.assertRaisesMessage(ImproperlyConfigured, "libpq 17 or newer"):
                require_search_cancellation_support()

    def test_old_driver_keeps_serving_during_image_rebuild(self) -> None:
        # Psycopg 3.1 has no capabilities object. Worker boot must still succeed
        # when the new source is mounted into the old image during deployment.
        with patch("main_app.middleware.psycopg.capabilities", None):
            with patch.object(
                SearchCancellation,
                "execute",
                side_effect=AssertionError("Unsupported cancellation must not run"),
            ):
                with self.assertLogs("main_app.middleware", level="WARNING") as log:
                    response = self.client.get(
                        "/chant-search/", **{"gunicorn.socket": self.server}
                    )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"value": 42})
        self.assertIn("Search cancellation is disabled", log.output[0])

    def test_thread_start_failure_releases_handle_without_executing_sql(self) -> None:
        connection.ensure_connection()
        cancel = connection.connection.pgconn.cancel_conn()
        context = {
            "connection": SimpleNamespace(
                connection=SimpleNamespace(
                    pgconn=SimpleNamespace(cancel_conn=lambda: cancel)
                )
            )
        }
        executed = []
        with patch(
            "main_app.middleware.threading.Thread.start",
            side_effect=RuntimeError("cannot start new thread"),
        ):
            with self.assertRaisesRegex(RuntimeError, "cannot start new thread"):
                SearchCancellation(self.server).execute(
                    lambda *args: executed.append(True),
                    "SELECT 1",
                    None,
                    False,
                    context,
                )
        self.assertEqual(executed, [])
        with self.assertRaises(psycopg.OperationalError):
            cancel.start()
