"""Chant search filters by its results' source, as Browse Sources does (#2354)."""

from django.conf import settings
from django.test import TestCase
from django.urls import reverse

from main_app.models import Chant, Sequence, Source
from main_app.tests.make_fakes import (
    make_fake_century,
    make_fake_chant,
    make_fake_institution,
    make_fake_provenance,
    make_fake_segment,
    make_fake_sequence,
    make_fake_source,
    make_fake_user,
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

    def test_form_offers_the_source_filters(self) -> None:
        response = self.client.get(reverse("chant-search"))
        for name in (
            "country",
            "provenance",
            "prodMethod",
            "dateStart",
            "dateEnd",
            "sourceCompleteness",
        ):
            with self.subTest(name=name):
                self.assertContains(response, f'name="{name}"')
        self.assertContains(response, '<option value="Spain">Spain</option>', html=True)
        self.assertContains(response, "js/source_filters.js")
        self.assertContains(response, "css/source_filters.css")


class ChantSearchMatchesSourceSearchTest(TestCase):
    """With the same source filters, chant search finds chants from exactly the
    sources Browse Sources lists (#2354)."""

    @classmethod
    def setUpTestData(cls) -> None:
        def century(name: str, start: int, end: int):
            return make_fake_century(name=name, min_date=start, max_date=end)

        c9 = century("9th century", 801, 900)
        c12 = century("12th century", 1101, 1200)
        c15 = century("15th century", 1401, 1500)
        c16 = century("16th century", 1501, 1600)
        cls.p1, cls.p2 = make_fake_provenance(), make_fake_provenance()
        spain = make_fake_institution(siglum="E-A", country="Spain")
        france = make_fake_institution(siglum="F-B", country="France")
        usa = make_fake_institution(siglum="US-C", country="United States of America")
        uk = make_fake_institution(siglum="GB-D", country="United Kingdom")
        C = Source.SourceCompletenessChoices
        P = Source.ProductionMethodChoices
        specs = {
            # name: (institution, provenance, centuries, completeness, method, published)
            "spain_full": (spain, cls.p1, [c12], C.FULL_SOURCE, P.MANUSCRIPT, True),
            "spain_print": (spain, cls.p2, [c12, c15], C.FRAGMENT, P.PRINT, True),
            "france_early": (france, cls.p1, [c9], C.FRAGMENTED, P.MANUSCRIPT, True),
            "usa_undated": (usa, None, [], C.RECONSTRUCTION, P.MANUSCRIPT, True),
            "uk_late": (uk, cls.p2, [c16], C.UNKNOWN, P.PRINT, True),
            "no_institution": (None, cls.p1, [c15], C.FULL_SOURCE, P.MANUSCRIPT, True),
            "france_private": (
                france,
                cls.p1,
                [c12],
                C.FULL_SOURCE,
                P.MANUSCRIPT,
                False,
            ),
        }
        cls.sources = {}
        for name, (
            institution,
            provenance,
            centuries,
            completeness,
            method,
            published,
        ) in specs.items():
            source = make_fake_source(
                published=published,
                holding_institution=institution,
                provenance=provenance,
                source_completeness=completeness,
                production_method=method,
            )
            source.century.set(centuries)
            cls.sources[name] = source
            chant = make_fake_chant(source=source)
            Chant.objects.filter(pk=chant.pk).update(incipit=f"Ave {name}")
        for name in ("spain_print", "uk_late"):
            sequence = make_fake_sequence(source=cls.sources[name])
            Sequence.objects.filter(pk=sequence.pk).update(
                incipit=f"Ave {name} sequence"
            )
        cls.superuser = make_fake_user(is_superuser=True)

    def cases(self) -> list[dict]:
        C = Source.SourceCompletenessChoices
        everything = [value for value, _ in C.choices]
        return [
            {"country": "Spain"},
            {"country": "spain"},
            {"country": "United"},  # partial: both "United ..." countries
            {"country": "Nowhere"},
            {"provenance": self.p1.id},
            {"provenance": self.p2.id},
            {"provenance": "abc"},  # ignored, as on Browse Sources
            {"dateStart": 1100, "dateEnd": 1200},
            {"dateStart": 1200, "dateEnd": 1300},  # touches the 12th century
            {"dateStart": 1205, "dateEnd": 1400},  # between centuries: nothing
            {"dateStart": 1450},  # only a start
            {"dateEnd": 900},  # only an end
            {"dateStart": "abc", "dateEnd": 1300},  # bad start ignored
            {"dateStart": 800, "dateEnd": 1600},  # untouched slider: everything
            {"sourceCompleteness": [C.FULL_SOURCE]},
            {"sourceCompleteness": [C.FRAGMENT, C.FRAGMENTED]},
            {"sourceCompleteness": everything},  # untouched boxes: everything
            {"prodMethod": Source.ProductionMethodChoices.MANUSCRIPT},
            {"prodMethod": Source.ProductionMethodChoices.PRINT},
            {"country": "Spain", "prodMethod": Source.ProductionMethodChoices.PRINT},
            {"provenance": self.p1.id, "dateStart": 1100, "dateEnd": 1200},
            {"country": "France", "sourceCompleteness": [C.FULL_SOURCE]},
            {"country": "United", "dateStart": 1500, "sourceCompleteness": [C.UNKNOWN]},
        ]

    def source_search(self, params: dict) -> set[int]:
        response = self.client.get(reverse("source-list"), params)
        self.assertEqual(response.status_code, 200)
        return {source.id for source in response.context["sources"]}

    def chant_search(self, params: dict, **extra: str) -> set[int]:
        response = self.client.get(reverse("chant-search"), {**params, **extra})
        self.assertEqual(response.status_code, 200)
        return {row.source_id for row in response.context["chants"]}

    def assert_parity(self) -> None:
        for params in self.cases():
            with self.subTest(params=params):
                expected = self.source_search(params)
                self.assertEqual(self.chant_search(params), expected)
                # the search bar applies the same filters
                self.assertEqual(self.chant_search(params, search_bar="Ave"), expected)

    def test_matches_source_search_for_visitors(self) -> None:
        self.assert_parity()

    def test_matches_source_search_for_superusers(self) -> None:
        # superusers also see the unpublished source
        self.client.force_login(self.superuser)
        self.assertIn(
            self.sources["france_private"].id,
            self.chant_search({"country": "France"}),
        )
        self.assert_parity()

    def test_expected_sources_for_the_edge_cases(self) -> None:
        s = {name: source.id for name, source in self.sources.items()}
        for params, names in (
            ({"country": "United"}, {"usa_undated", "uk_late"}),
            ({"dateStart": 1200, "dateEnd": 1300}, {"spain_full", "spain_print"}),
            ({"dateStart": 1205, "dateEnd": 1400}, set()),
            ({"dateStart": 1450}, {"spain_print", "uk_late", "no_institution"}),
            ({"dateEnd": 900}, {"france_early"}),
            ({"provenance": "abc"}, set(s) - {"france_private"}),
            ({"dateStart": 800, "dateEnd": 1600}, set(s) - {"france_private"}),
        ):
            with self.subTest(params=params):
                self.assertEqual(self.chant_search(params), {s[n] for n in names})

    def test_a_source_in_several_matching_centuries_lists_its_chants_once(self) -> None:
        response = self.client.get(
            reverse("chant-search"), {"dateStart": 1100, "dateEnd": 1500}
        )
        incipits = [row.incipit for row in response.context["chants"]]
        self.assertEqual(incipits.count("Ave spain_print"), 1)
        self.assertEqual(incipits.count("Ave spain_print sequence"), 1)

    def test_filters_combine_with_chant_filters(self) -> None:
        response = self.client.get(
            reverse("chant-search"),
            {"keyword": "Ave spain", "op": "starts_with", "prodMethod": 2},
        )
        self.assertEqual(
            {row.incipit for row in response.context["chants"]},
            {"Ave spain_print", "Ave spain_print sequence"},
        )

    def test_page_links_keep_a_country_with_spaces(self) -> None:
        response = self.client.get(
            reverse("chant-search"), {"country": "United States of America"}
        )
        self.assertIn(
            "country=United+States+of+America",
            response.context["url_with_search_params"],
        )


class CcdbChantSearchSourceFiltersTest(TestCase):
    """The Canadian Chant Database's chant search offers the source filters that
    tell its sources apart: they are all Canadian, nearly all manuscripts."""

    @classmethod
    def setUpTestData(cls) -> None:
        ccdb = make_fake_segment(
            id=settings.CCDB_SEGMENT_ID, name="Canadian Chant Database"
        )
        canada = make_fake_institution(siglum="CDN-Tst", country="Canada")
        cls.italy = make_fake_provenance()
        # the year slider needs at least one dated source
        century = make_fake_century(name="15th century", min_date=1401, max_date=1500)
        for provenance, incipit in (
            (cls.italy, "Italian"),
            (make_fake_provenance(), "Other"),
        ):
            source = make_fake_source(
                published=True,
                segment=[ccdb],
                holding_institution=canada,
                provenance=provenance,
            )
            source.century.add(century)
            chant = make_fake_chant(source=source)
            Chant.objects.filter(pk=chant.pk).update(incipit=f"{incipit} chant")

    def test_form_offers_provenance_year_and_physical_status(self) -> None:
        response = self.client.get(reverse("ccdb-chant-search"))
        for name in ("provenance", "dateStart", "dateEnd", "sourceCompleteness"):
            with self.subTest(name=name):
                self.assertContains(response, f'name="{name}"')
        for name in ("country", "prodMethod"):
            with self.subTest(name=name):
                self.assertNotContains(response, f'name="{name}"')
        self.assertContains(response, "js/source_filters.js")

    def test_provenance_filters_the_ccdb_search(self) -> None:
        response = self.client.get(
            reverse("ccdb-chant-search"), {"provenance": self.italy.id}
        )
        self.assertEqual(
            {row.incipit for row in response.context["chants"]}, {"Italian chant"}
        )

    def test_provenance_filters_the_sources_tab_too(self) -> None:
        # the keyword matches both sources through their institution's siglum
        response = self.client.get(
            reverse("ccdb-chant-search"),
            {"keyword": "CDN-Tst", "provenance": self.italy.id},
        )
        self.assertEqual(
            [source.provenance for source in response.context["ccdb_sources"]],
            [self.italy],
        )
        self.assertEqual(response.context["ccdb_source_count"], 1)


class InvalidSourceFilterValuesTest(TestCase):
    """Made-up filter values are ignored rather than causing an error (#1484)."""

    def test_pages_with_source_filters_ignore_invalid_values(self) -> None:
        make_fake_segment(id=settings.CANTUS_SEGMENT_ID, name="CANTUS Database")
        make_fake_segment(id=settings.CCDB_SEGMENT_ID, name="Canadian Chant Database")
        params = {
            "sourceCompleteness": ["bogus", "²", "99"],
            "prodMethod": ["bogus", "²", "99"],
            "provenance": ["bogus", "²"],
            "dateStart": ["²"],
        }
        for name in ("chant-search", "ccdb-chant-search", "source-list"):
            for param, values in params.items():
                for value in values:
                    with self.subTest(page=name, param=param, value=value):
                        response = self.client.get(reverse(name), {param: value})
                        self.assertEqual(response.status_code, 200)
