from django.test import TestCase
from django.urls import reverse

from main_app.tests.make_fakes import (
    make_fake_chant,
    make_fake_institution,
    make_fake_source,
)


class MelodyExportQueriesTest(TestCase):
    def test_headings_are_exported_in_one_query(self):
        expected = {}
        for siglum in ("A-Test", "B-Test", None):
            institution = make_fake_institution(siglum=siglum) if siglum else None
            source = make_fake_source(published=True)
            source.holding_institution = institution
            source.save()
            for _ in range(3):
                chant = make_fake_chant(source=source, cantus_id="export-test")
                expected[chant.id] = source.short_heading
        make_fake_chant(
            source=make_fake_source(published=False), cantus_id="export-test"
        )

        with self.assertNumQueries(1):
            response = self.client.get(
                reverse("json-melody-export", args=["export-test"])
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            {row["nid"]: row["siglum"] for row in response.json()}, expected
        )
