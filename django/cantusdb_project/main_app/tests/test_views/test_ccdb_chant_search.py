"""The Canadian Chant Database's chant search covers only its own sources (#2359)."""

from django.conf import settings
from django.test import TestCase
from django.urls import reverse

from main_app.models import Chant
from main_app.tests.make_fakes import (
    make_fake_chant,
    make_fake_segment,
    make_fake_source,
)


class CcdbChantSearchTest(TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        ccdb = make_fake_segment(
            id=settings.CCDB_SEGMENT_ID, name="Canadian Chant Database"
        )
        cantus = make_fake_segment(
            id=settings.CANTUS_SEGMENT_ID, name="Cantus Database"
        )
        for segment, incipit in ((ccdb, "Canadian chant"), (cantus, "Cantus chant")):
            chant = make_fake_chant(
                source=make_fake_source(published=True, segment=[segment])
            )
            Chant.objects.filter(pk=chant.pk).update(incipit=incipit)
        cls.cantus = cantus

    def incipits(self, params: dict) -> set[str]:
        response = self.client.get(reverse("ccdb-chant-search"), params)
        self.assertEqual(response.status_code, 200)
        return {row.incipit for row in response.context["chants"]}

    def test_searches_only_the_canadian_chant_database(self) -> None:
        self.assertEqual(self.incipits({"op": "contains"}), {"Canadian chant"})

    def test_ignores_the_database_choice_of_older_links(self) -> None:
        self.assertEqual(
            self.incipits({"op": "contains", "db": self.cantus.pk}), {"Canadian chant"}
        )

    def test_offers_no_database_selector(self) -> None:
        response = self.client.get(reverse("ccdb-chant-search"))
        self.assertNotContains(response, 'name="db"')
