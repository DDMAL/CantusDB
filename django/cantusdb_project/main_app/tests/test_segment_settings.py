"""Segment-dependent pages and commands must follow the configured IDs."""

import csv
from importlib import reload
from io import StringIO

from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.core.management import call_command
from django.test import RequestFactory, TestCase, override_settings
from django.urls import clear_url_caches, resolve, reverse

from main_app.management.commands.update_proofread_status import EXCLUDE
from main_app.models import Segment
from main_app.tests.make_fakes import (
    make_fake_chant,
    make_fake_institution,
    make_fake_segment,
    make_fake_sequence,
    make_fake_source,
)
from main_app.views.source import SourceListView


class SegmentSettingsTest(TestCase):
    @override_settings(
        CANTUS_SEGMENT_ID=9063, BOWER_SEGMENT_ID=9064, CCDB_SEGMENT_ID=9066
    )
    def test_source_filter_and_navigation_use_settings(self) -> None:
        response = self.client.get(reverse("source-list"))
        for segment_id, label in (
            (settings.CANTUS_SEGMENT_ID, "Cantus Database"),
            (settings.BOWER_SEGMENT_ID, "Bower Sequence Database"),
            (settings.CCDB_SEGMENT_ID, "Canadian Chant Database"),
        ):
            with self.subTest(segment=label):
                self.assertContains(
                    response,
                    f'<option value="{segment_id}">{label}</option>',
                    html=True,
                )
        for segment_id in (settings.CANTUS_SEGMENT_ID, settings.BOWER_SEGMENT_ID):
            self.assertContains(
                response, f'href="{reverse("source-list")}?segment={segment_id}"'
            )

    @override_settings(CCDB_SEGMENT_ID=9066, CANTORALES_SEGMENT_ID=9067)
    def test_scoped_source_templates_and_membership_use_settings(self) -> None:
        for segment_id, template_name in (
            (settings.CCDB_SEGMENT_ID, "canadian_chant_db.html"),
            (settings.CANTORALES_SEGMENT_ID, "cantorales.html"),
        ):
            with self.subTest(segment=segment_id):
                segment = make_fake_segment(id=segment_id)
                source = make_fake_source(published=True, segment=[segment])
                make_fake_source(published=False, segment=[segment])
                make_fake_source(published=True)
                request = RequestFactory().get("/sources/")
                request.user = AnonymousUser()
                response = SourceListView.as_view()(request, segment_id=segment_id)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(
                    response.template_name, [f"source_lists/{template_name}"]
                )
                self.assertQuerySetEqual(response.context_data["sources"], [source])
                response.render()
                if segment_id == settings.CCDB_SEGMENT_ID:
                    self.assertContains(
                        response,
                        f'<input type="hidden" name="segment" value="{segment_id}" />',
                        html=True,
                    )

    def test_scoped_routes_use_settings(self) -> None:
        from cantusdb import urls as project_urls
        from main_app import urls

        try:
            with self.settings(
                CCDB_SEGMENT_ID=9066,
                CANTORALES_SEGMENT_ID=9067,
            ):
                # Rebuild startup kwargs with alternate IDs and refresh the
                # project resolver so it includes the new app URL patterns.
                reload(urls)
                reload(project_urls)
                clear_url_caches()
                for route, segment_id, template_name in (
                    (
                        "canadian-chant-db-source-list",
                        settings.CCDB_SEGMENT_ID,
                        "canadian_chant_db.html",
                    ),
                    ("ccdb-browse", settings.CCDB_SEGMENT_ID, "ccdb_browse.html"),
                    (
                        "cantorales-source-list",
                        settings.CANTORALES_SEGMENT_ID,
                        "cantorales.html",
                    ),
                ):
                    with self.subTest(route=route):
                        segment, _ = Segment.objects.get_or_create(
                            id=segment_id, defaults={"name": f"Segment {segment_id}"}
                        )
                        source = make_fake_source(published=True, segment=[segment])
                        url = reverse(route)
                        self.assertEqual(resolve(url).kwargs["segment_id"], segment_id)
                        response = self.client.get(url)
                        self.assertEqual(response.status_code, 200)
                        self.assertTemplateUsed(
                            response, f"source_lists/{template_name}"
                        )
                        self.assertIn(source, response.context["sources"])
        finally:
            # Restore startup kwargs after settings revert, even on failure.
            reload(urls)
            reload(project_urls)
            clear_url_caches()

    @override_settings(BOWER_SEGMENT_ID=9064)
    def test_source_search_and_csv_select_sequences_using_settings(self) -> None:
        bower = make_fake_segment(id=settings.BOWER_SEGMENT_ID)
        for segments in ([bower], []):
            with self.subTest(bower=bool(segments)):
                source = make_fake_source(published=True, segment=segments)
                chant = make_fake_chant(
                    source=source, manuscript_full_text_std_spelling="Ordinary chant"
                )
                sequence = make_fake_sequence(source=source)
                expected = sequence if segments else chant
                with self.subTest(endpoint="search"):
                    response = self.client.get(
                        reverse("chant-search-ms", args=[source.id]), {"keyword": ""}
                    )
                    self.assertEqual(response.status_code, 200)
                    self.assertQuerySetEqual(response.context["chants"], [expected])
                with self.subTest(endpoint="csv"):
                    response = self.client.get(reverse("csv-export", args=[source.id]))
                    self.assertEqual(response.status_code, 200)
                    rows = list(csv.DictReader(StringIO(response.content.decode())))
                    self.assertEqual(
                        [row["incipit"] for row in rows], [expected.incipit]
                    )

    @override_settings(CANTUS_SEGMENT_ID=9063)
    def test_proofreading_command_selects_configured_published_sources(self) -> None:
        cantus = make_fake_segment(id=settings.CANTUS_SEGMENT_ID)
        included = make_fake_source(published=True, segment=[cantus])
        excluded = (
            make_fake_source(published=False, segment=[cantus]),
            make_fake_source(published=True),
            make_fake_source(id=EXCLUDE[0], published=True, segment=[cantus]),
        )
        chant = make_fake_chant(source=included, other_fields_proofread=False)
        untouched = [
            make_fake_chant(source=source, other_fields_proofread=False)
            for source in excluded
        ]
        call_command("update_proofread_status", stdout=StringIO())
        chant.refresh_from_db()
        self.assertTrue(chant.other_fields_proofread)
        for other in untouched:
            other.refresh_from_db()
            self.assertFalse(other.other_fields_proofread)

    @override_settings(CCDB_SEGMENT_ID=9066)
    def test_populate_ccdb_uses_configured_id_after_segment_rename(self) -> None:
        ccdb = make_fake_segment(id=settings.CCDB_SEGMENT_ID, name="Renamed collection")
        make_fake_segment(name="Canadian Chant Database")
        retained = make_fake_segment(name="Another collection")
        canadian = make_fake_source(
            holding_institution=make_fake_institution(country="Canada"),
            segment=[retained],
        )
        other = make_fake_source(
            holding_institution=make_fake_institution(country="France"),
            segment=[retained],
        )
        call_command("populate_canadian_chant_db", stdout=StringIO())
        self.assertCountEqual(canadian.segment_m2m.all(), [retained, ccdb])
        self.assertQuerySetEqual(other.segment_m2m.all(), [retained])
