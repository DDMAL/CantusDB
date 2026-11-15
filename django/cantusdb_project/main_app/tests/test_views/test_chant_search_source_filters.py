"""Chant search filters by its results' source, as Browse Sources does (#2354)."""

from django.test import TestCase
from django.urls import reverse

from main_app.models import Chant, Sequence, Source
from main_app.tests.make_fakes import (
    make_fake_century,
    make_fake_chant,
    make_fake_institution,
    make_fake_provenance,
    make_fake_sequence,
    make_fake_source,
)

FULL = Source.SourceCompletenessChoices.FULL_SOURCE
FRAGMENT = Source.SourceCompletenessChoices.FRAGMENT
ALL_COMPLETENESS = [value for value, _ in Source.SourceCompletenessChoices.choices]


class ChantSearchSourceFiltersTest(TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        early = make_fake_century(name="12th century", min_date=1101, max_date=1200)
        late = make_fake_century(name="15th century", min_date=1401, max_date=1500)
        cls.provenance = make_fake_provenance()
        cls.spanish = make_fake_source(
            published=True,
            holding_institution=make_fake_institution(siglum="E-Tst", country="Spain"),
            provenance=cls.provenance,
            source_completeness=FULL,
            production_method=Source.ProductionMethodChoices.MANUSCRIPT,
        )
        cls.spanish.century.add(early)
        cls.french = make_fake_source(
            published=True,
            holding_institution=make_fake_institution(siglum="F-Tst", country="France"),
            source_completeness=FRAGMENT,
            production_method=Source.ProductionMethodChoices.PRINT,
        )
        cls.french.century.add(late)
        # the incipit is derived on save, so set it afterwards
        for model, source, incipit in (
            (Chant, cls.spanish, "Spanish chant"),
            (Chant, cls.french, "French chant"),
        ):
            Chant.objects.filter(pk=make_fake_chant(source=source).pk).update(
                incipit=incipit
            )
        Sequence.objects.filter(pk=make_fake_sequence(source=cls.spanish).pk).update(
            incipit="Spanish sequence"
        )

    def incipits(self, params: dict) -> set[str]:
        response = self.client.get(reverse("chant-search"), params)
        self.assertEqual(response.status_code, 200)
        return {row.incipit for row in response.context["chants"]}

    def test_each_source_filter_keeps_chants_and_sequences_of_matching_sources(
        self,
    ) -> None:
        for params in (
            {"country": "Spain"},
            {"country": "spa"},  # partial match, as on Browse Sources
            {"provenance": self.provenance.id},
            {"dateStart": 1100, "dateEnd": 1300},
            {"sourceCompleteness": [FULL]},
            {"prodMethod": Source.ProductionMethodChoices.MANUSCRIPT},
        ):
            with self.subTest(params=params):
                self.assertEqual(
                    self.incipits(params), {"Spanish chant", "Spanish sequence"}
                )

    def test_untouched_fields_filter_nothing(self) -> None:
        # The form submits the full year range and every box when unchanged.
        params = {
            "keyword": "",
            "dateStart": 1100,
            "dateEnd": 1500,
            "sourceCompleteness": ALL_COMPLETENESS,
        }
        self.assertEqual(
            self.incipits(params),
            {"Spanish chant", "Spanish sequence", "French chant"},
        )

    def test_filters_combine_with_the_search_bar(self) -> None:
        self.assertEqual(
            self.incipits({"search_bar": "French", "country": "Spain"}), set()
        )
        self.assertEqual(
            self.incipits({"search_bar": "French", "country": "France"}),
            {"French chant"},
        )

    def test_filters_open_advanced_search_and_stay_in_page_links(self) -> None:
        response = self.client.get(
            reverse("chant-search"),
            {"country": "Spain", "sourceCompleteness": [FULL, FRAGMENT]},
        )
        self.assertTrue(response.context["advanced_search_active"])
        self.assertIn("Spain", response.context["countries"])
        self.assertIn(
            "country=Spain&sourceCompleteness=1&sourceCompleteness=2",
            response.context["url_with_search_params"],
        )
        response = self.client.get(reverse("chant-search"), {"keyword": "x"})
        self.assertFalse(response.context["advanced_search_active"])
