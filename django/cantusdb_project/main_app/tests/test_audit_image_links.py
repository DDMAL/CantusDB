"""Tests for the audit_image_links management command (issue #2170)."""

import io
from unittest.mock import patch

import requests
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase

from main_app.management.commands.audit_image_links import (
    BLOCKED,
    BROKEN,
    UNREACHABLE,
    WORKING,
    cannot_check,
    check_url,
    classify,
)
from main_app.models import SourceURL
from main_app.tests.make_fakes import make_fake_chant, make_fake_source

COMMAND = "audit_image_links"
CHECK_URL = "main_app.management.commands.audit_image_links.check_url"


class FakeResponse:
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code

    def close(self) -> None:
        pass


class FakeSession:
    def __init__(self, outcome) -> None:
        self.outcome = outcome

    def get(self, url, **kwargs):
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return FakeResponse(self.outcome)


class CheckUrlTest(SimpleTestCase):
    def test_status_codes(self) -> None:
        self.assertEqual(classify(200), WORKING)
        for code in (404, 410, 400):
            self.assertEqual(classify(code), BROKEN)
        for code in (401, 403, 429):
            self.assertEqual(classify(code), BLOCKED)
        for code in (500, 503):
            self.assertEqual(classify(code), UNREACHABLE)

    def test_answers(self) -> None:
        url = "https://example.org/page"
        self.assertEqual(check_url(FakeSession(200), url, 1), (WORKING, "200"))
        self.assertEqual(check_url(FakeSession(404), url, 1), (BROKEN, "404"))
        self.assertEqual(
            check_url(FakeSession(requests.Timeout()), url, 1),
            (UNREACHABLE, "timed out"),
        )
        self.assertEqual(
            check_url(FakeSession(requests.ConnectionError()), url, 1),
            (UNREACHABLE, "connection failed"),
        )

    def test_dead_domain_bad_certificate_and_malformed_links(self) -> None:
        url = "https://example.org/page"
        dns = requests.ConnectionError("NameResolutionError: Failed to resolve")
        self.assertEqual(
            check_url(FakeSession(dns), url, 1), (BROKEN, "domain not found")
        )
        self.assertEqual(
            check_url(FakeSession(requests.exceptions.SSLError()), url, 1),
            (UNREACHABLE, "certificate problem"),
        )
        self.assertEqual(
            check_url(FakeSession(requests.exceptions.InvalidURL()), url, 1),
            (BROKEN, "not a web address"),
        )
        for malformed in ("https://[bad", "http://", "www.example.org/page"):
            self.assertEqual(
                check_url(FakeSession(200), malformed, 1),
                (BROKEN, "not a web address"),
            )

    def test_not_a_web_address(self) -> None:
        self.assertEqual(
            check_url(FakeSession(200), "ftp://example.org/x", 1),
            (BROKEN, "not a web address"),
        )

    def test_sites_we_cannot_check(self) -> None:
        self.assertIsNotNone(cannot_check("gallica.bnf.fr"))
        self.assertIsNotNone(cannot_check("www.gallica.bnf.fr"))
        self.assertIsNone(cannot_check("www.e-codices.unifr.ch"))


class AuditImageLinksCommandTest(TestCase):
    def setUp(self) -> None:
        self.source = make_fake_source(image_link="https://a.org/source")
        for folio in ("001r", "002r", "003r"):
            make_fake_chant(
                source=self.source, folio=folio, image_link=f"https://a.org/{folio}"
            )
        make_fake_chant(source=self.source, folio="004r", image_link="https://b.org/4")
        self.requested: list[str] = []
        self.answers: dict[str, list[tuple[str, str]]] = {}

    def fake_check_url(self, session, url, timeout):
        self.requested.append(url)
        answers = self.answers.get(url)
        return answers.pop(0) if answers else (WORKING, "200")

    def run_command(self, *args: str) -> str:
        out = io.StringIO()
        with patch(CHECK_URL, side_effect=self.fake_check_url):
            call_command(
                COMMAND, "--delay", "0", *args, stdout=out, stderr=io.StringIO()
            )
        return out.getvalue()

    def test_checks_first_and_last_chant_link_per_site(self) -> None:
        self.run_command("--source", str(self.source.pk))
        self.assertCountEqual(
            self.requested,
            [
                "https://a.org/source",
                "https://a.org/001r",
                "https://a.org/003r",
                "https://b.org/4",
            ],
        )

    def test_all_chant_links(self) -> None:
        self.run_command("--source", str(self.source.pk), "--all-chant-links")
        self.assertIn("https://a.org/002r", self.requested)

    def test_broken_link_is_reported_with_its_source(self) -> None:
        self.answers["https://a.org/003r"] = [(BROKEN, "404"), (BROKEN, "404")]
        output = self.run_command("--source", str(self.source.pk))
        self.assertIn("BROKEN", output)
        self.assertIn(f"source {self.source.pk} (", output)
        self.assertIn("https://a.org/003r [404]", output)
        self.assertNotIn("https://a.org/001r [", output)
        self.assertIn("4 link(s): 3 working, 1 broken", output)

    def test_failed_link_is_tried_again(self) -> None:
        self.answers["https://b.org/4"] = [(UNREACHABLE, "timed out"), (WORKING, "200")]
        output = self.run_command("--source", str(self.source.pk))
        self.assertEqual(self.requested.count("https://b.org/4"), 2)
        self.assertIn("4 link(s): 4 working", output)
        self.assertNotIn("COULDN'T REACH", output)

    def test_sites_we_cannot_check_are_listed_but_not_requested(self) -> None:
        SourceURL.objects.create(
            source=self.source,
            url="https://gallica.bnf.fr/ark:/12148/btv1b1",
            url_type=SourceURL.URLTypes.EXTERNAL_IMAGES,
        )
        output = self.run_command("--source", str(self.source.pk))
        self.assertNotIn("https://gallica.bnf.fr/ark:/12148/btv1b1", self.requested)
        self.assertIn("NOT CHECKED", output)
        self.assertIn("gallica.bnf.fr: 1 link(s) in 1 source(s)", output)

    def test_blocked_site_gets_one_line_not_one_per_link(self) -> None:
        for url in ("https://a.org/source", "https://a.org/001r", "https://a.org/003r"):
            self.answers[url] = [(BLOCKED, "403"), (BLOCKED, "403")]
        output = self.run_command("--source", str(self.source.pk))
        self.assertIn("BLOCKED", output)
        self.assertIn("a.org: 3 link(s) in 1 source(s)", output)
        self.assertNotIn("[403]", output)

    def test_url_used_in_several_places_is_listed_once(self) -> None:
        SourceURL.objects.create(
            source=self.source,
            url="https://a.org/source",
            url_type=SourceURL.URLTypes.EXTERNAL_IMAGES,
        )
        self.answers["https://a.org/source"] = [(BROKEN, "404"), (BROKEN, "404")]
        output = self.run_command("--source", str(self.source.pk))
        self.assertEqual(output.count("https://a.org/source [404]"), 1)
        self.assertIn("(source image link, source link (External Images))", output)

    def test_an_unexpected_error_on_one_link_does_not_stop_the_run(self) -> None:
        def fake(session, url, timeout):
            if url == "https://a.org/001r":
                raise RuntimeError("something odd")
            return WORKING, "200"

        out = io.StringIO()
        with patch(CHECK_URL, side_effect=fake):
            call_command(
                COMMAND,
                "--delay",
                "0",
                "--source",
                str(self.source.pk),
                stdout=out,
                stderr=io.StringIO(),
            )
        self.assertIn("https://a.org/001r [RuntimeError]", out.getvalue())
        self.assertIn("3 working", out.getvalue())

    def test_site_option_limits_the_check_to_one_site(self) -> None:
        self.run_command("--source", str(self.source.pk), "--site", "b.org")
        self.assertEqual(self.requested, ["https://b.org/4"])

    def test_source_option_leaves_other_sources_out(self) -> None:
        make_fake_source(image_link="https://c.org/other")
        self.run_command("--source", str(self.source.pk))
        self.assertNotIn("https://c.org/other", self.requested)
