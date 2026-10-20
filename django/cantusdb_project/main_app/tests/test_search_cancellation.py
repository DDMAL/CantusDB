"""Exercise cancellation against PostgreSQL, not a mocked query executor."""

import select
import socket
import threading
import time
from queue import Queue
from collections.abc import Callable
from typing import Any
from types import SimpleNamespace
from unittest import skipUnless
from unittest.mock import patch

import psycopg
from django.contrib.auth import get_user_model
from django.db import OperationalError, connection, transaction
from django.db.models.expressions import RawSQL
from django.http import Http404, HttpRequest, JsonResponse
from django.test import TransactionTestCase, override_settings
from django.urls import path

from main_app.middleware import SearchCancellation, SearchDisconnected
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
]


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
            self.assertTrue(cancellation.client_left())
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
        # Hold execute() briefly after the watcher starts. Its first cancel will
        # hit an idle connection; a later cancel must stop the subsequent SQL.
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
            time.sleep(0.2)
            return execute(sql, params, many, context)

        with patch.object(cancellation, "client_left", disconnect_after_initial_check):
            start = time.monotonic()
            with connection.execute_wrapper(cancellation.execute):
                with connection.execute_wrapper(delayed_execute):
                    with self.assertRaises(SearchDisconnected):
                        with connection.cursor() as cursor:
                            cursor.execute("SELECT pg_sleep(10)")
            self.assertLess(time.monotonic() - start, 3)
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

    def test_query_cannot_return_while_a_late_cancel_is_still_in_flight(self) -> None:
        cancellation = SearchCancellation(self.server)
        cancel_started = threading.Event()
        release_cancel = threading.Event()
        query_finished = threading.Event()
        returned = threading.Event()
        errors: list[BaseException] = []

        def delayed_cancel() -> None:
            cancel_started.set()
            release_cancel.wait(3)

        def finish_query(*_args: Any) -> None:
            self.client_socket.close()
            if not cancel_started.wait(2):
                raise AssertionError("Watcher never sent cancellation")
            query_finished.set()

        context = {
            "connection": SimpleNamespace(
                connection=SimpleNamespace(
                    pgconn=SimpleNamespace(
                        get_cancel=lambda: SimpleNamespace(cancel=delayed_cancel)
                    )
                )
            )
        }

        def run_query() -> None:
            try:
                cancellation.execute(finish_query, "SELECT 1", None, False, context)
            except SearchDisconnected:
                pass
            except BaseException as error:
                errors.append(error)
            finally:
                returned.set()

        query = threading.Thread(target=run_query)
        query.start()
        try:
            self.assertTrue(query_finished.wait(2))
            self.assertFalse(
                returned.wait(0.1),
                "The request must wait for its cancellation sender before returning",
            )
        finally:
            release_cancel.set()
            query.join(3)
        self.assertFalse(query.is_alive())
        self.assertEqual(errors, [])
