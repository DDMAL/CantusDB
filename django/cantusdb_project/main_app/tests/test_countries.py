from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.management import CommandError, call_command
from django.db import connection
from django.db.models.deletion import ProtectedError
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from main_app.countries import (
    find_country,
    import_country,
    matching_countries,
)
from main_app.management.country_import import import_rism_country
from main_app.models import Country, Institution, Source
from main_app.tests.make_fakes import (
    make_fake_institution,
    make_fake_source,
    make_fake_user,
    make_fake_segment,
)


class CountryLoaderTests(TestCase):
    def test_loader_fills_only_missing_values(self):
        canada = Country.objects.create(
            pk=Country.CANADA,
            name="Dominion of Canada",
            aliases="Local spelling",
            rism_code="CDN",
            authorities={"Wikidata": "Q1234"},
        )
        with CaptureQueriesContext(connection) as queries:
            call_command("load_countries", stdout=StringIO())
        self.assertEqual(sum(q["sql"].startswith("SELECT") for q in queries), 2)
        canada.refresh_from_db()
        self.assertEqual(canada.name, "Dominion of Canada")
        self.assertSetEqual(
            set(canada.aliases.splitlines()), {"Canada", "Local spelling", "CA", "CAN"}
        )
        self.assertEqual(
            canada.authorities,
            {
                "Wikidata": "Q1234",
                "Getty TGN": "7005685",
            },
        )
        self.assertEqual(import_rism_country("RC").name, "Taiwan")
        with CaptureQueriesContext(connection) as again:
            call_command("load_countries", stdout=StringIO())
        self.assertFalse(
            any(q["sql"].startswith(("INSERT ", "UPDATE ")) for q in again)
        )
        highest = Country.objects.latest("pk").pk
        local = Country.objects.create(name="Local territory")
        self.assertGreater(local.pk, highest)
        issued = local.pk
        local.delete()
        call_command("load_countries", stdout=StringIO())
        self.assertGreater(
            Country.objects.create(name="Next local territory").pk, issued
        )

    def test_loader_skips_blank_authority_ids(self):
        with TemporaryDirectory() as directory, self.settings(BASE_DIR=directory):
            (Path(directory) / "countries.csv").write_text(
                "id,name,rism_code,aliases,getty_tgn,wikidata\n"
                "6,Canada,CDN,, ,Q16\n"
                "20,Japan,J,,1000120,\n"
            )
            call_command("load_countries", stdout=StringIO())
        canada = Country.objects.get(name="Canada")
        self.assertEqual(canada.authorities, {"Wikidata": "Q16"})
        self.assertEqual(
            Country.objects.get(pk=20).authorities,
            {"Getty TGN": "1000120"},
        )

    def test_loader_converts_known_draft_urls_and_preserves_unrecognized_ones_on_error(
        self,
    ):
        canada = Country.objects.create(pk=6, name="Canada")
        local = Country.objects.create(pk=1000, name="Local territory")
        Country.objects.filter(pk=canada.pk).update(
            authorities={"Wikidata": "http://www.wikidata.org/entity/Q16"},
            aliases="Dominion\n dominion ",
        )
        wrong_url = "https://example.org/wiki/Q100"
        Country.objects.filter(pk=local.pk).update(authorities={"Wikidata": wrong_url})
        with self.assertRaisesMessage(CommandError, wrong_url):
            call_command("load_countries")
        canada.refresh_from_db()
        self.assertEqual(
            canada.authorities["Wikidata"], "http://www.wikidata.org/entity/Q16"
        )
        self.assertEqual(Country.objects.count(), 2)
        Country.objects.filter(pk=local.pk).update(
            authorities={"GeoNames": "https://www.geonames.org/7005685/"}
        )
        call_command("load_countries", stdout=StringIO())
        canada.refresh_from_db()
        local.refresh_from_db()
        self.assertEqual(
            canada.authorities, {"Wikidata": "Q16", "Getty TGN": "7005685"}
        )
        self.assertEqual(local.authorities, {"GeoNames": "7005685"})
        self.assertEqual(canada.aliases.splitlines().count("Dominion"), 1)
        self.assertNotIn("dominion", canada.aliases.splitlines())

    def test_loader_rejects_id_match_from_a_different_authority(self):
        Country.objects.create(
            pk=6, name="Local territory", authorities={"GeoNames": "7005685"}
        )
        with self.assertRaisesMessage(CommandError, "is occupied by Local territory"):
            call_command("load_countries")
        self.assertEqual(Country.objects.count(), 1)

    def test_catalogue_can_grow_and_cannot_overwrite_a_local_country(self):
        with TemporaryDirectory() as directory, self.settings(BASE_DIR=directory):
            path = Path(directory) / "countries.csv"
            header = "id,name,rism_code,aliases,getty_tgn,wikidata\n"
            path.write_text(header + "400,Iceland,IS,,,\n")
            call_command("load_countries", stdout=StringIO())
            local = Country.objects.create(name="Local territory")
            self.assertGreater(local.pk, 400)
            path.write_text(header + f"{local.pk},Estonia,EE,,,\n")
            with self.assertRaisesMessage(
                CommandError, "is occupied by Local territory"
            ):
                call_command("load_countries")
            local.refresh_from_db()
            self.assertEqual(
                (local.name, local.rism_code, local.aliases),
                ("Local territory", None, ""),
            )

    def test_loader_rejects_duplicate_and_nonpositive_ids_atomically(self):
        with TemporaryDirectory() as directory, self.settings(BASE_DIR=directory):
            for invalid in (0, -1, 10):
                with self.subTest(invalid=invalid):
                    (Path(directory) / "countries.csv").write_text(
                        "id,name,rism_code,aliases,getty_tgn,wikidata\n"
                        f"10,Iceland,IS,,,\n{invalid},Estonia,EE,,,\n"
                    )
                    with self.assertRaisesMessage(CommandError, "positive and unique"):
                        call_command("load_countries")
                    self.assertFalse(Country.objects.exists())

    def test_loader_reports_existing_authority_claim_under_another_name(self):
        local = Country.objects.create(
            pk=1000,
            name="Nippon",
            authorities={"Wikidata": "Q17"},
        )
        with self.assertRaisesRegex(CommandError, r"Nippon.*Japan|Japan.*Nippon"):
            call_command("load_countries")
        self.assertFalse(Country.objects.filter(name="Japan").exists())
        self.assertEqual(Country.objects.count(), 1)
        self.assertEqual(Country.objects.get(pk=local.pk).name, "Nippon")


class CountryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.usa = Country.objects.create(
            name="United States of America",
            aliases="United States\nUSA",
            rism_code="US",
        )
        cls.canada = Country.objects.create(name="Canada", rism_code="CDN")

    def test_admin_validates_authority_ids_and_aliases(self):
        self.client.force_login(make_fake_user(is_superuser=True))
        data = {
            "name": "Dominion of Canada",
            "rism_code": "cdn",
            "aliases": "Canada\r\n  Nouvelle-France  \n CANADA \ncdn\nDominion of Canada",
            "authorities": '{" wikidata ":"Q16","GeoNames":6251999}',
        }
        response = self.client.post(
            reverse("admin:main_app_country_change", args=[self.canada.pk]), data
        )
        self.assertEqual(response.status_code, 302)
        self.canada.refresh_from_db()
        self.assertEqual(self.canada.rism_code, "CDN")
        self.assertEqual(self.canada.authorities["Wikidata"], "Q16")
        self.assertEqual(self.canada.aliases, "Canada\nNouvelle-France")
        self.assertEqual(self.canada.authorities["GeoNames"], "6251999")
        response = self.client.get(reverse("admin:main_app_country_changelist"))
        self.assertContains(response, 'href="https://www.wikidata.org/wiki/Q16"')
        self.assertContains(response, 'href="https://www.geonames.org/6251999/"')
        self.assertEqual(import_country("nouvelle-france"), self.canada)
        url = reverse("admin:main_app_country_add")
        for bad in (
            {"authorities": '["Q30"]'},
            {"authorities": '{"Wikidata":"https://www.wikidata.org/wiki/Q30"}'},
            {"authorities": '{"Wikidata":"Q30?lang=en"}'},
            {"authorities": '{"Wikidata":"1234"}'},
            {"authorities": '{"Wikidata":"Q16"}'},
            {"authorities": '{"Wikidata":"Q30","wikidata":"Q31"}'},
            {"authorities": '{"Getty TGN":"Q30"}'},
            {"authorities": '{"GeoNames":"6251999"}'},
            {"authorities": '{"GeoNames":"https://www.geonames.org/6251999/"}'},
            {"aliases": "nouvelle-france"},
            {"aliases": "CDN"},
            {"rism_code": "us"},
        ):
            with self.subTest(bad=bad):
                response = self.client.post(url, {"name": "Test country", **bad})
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.context["adminform"].form.errors)
        self.assertFalse(Country.objects.filter(name="Test country").exists())

    def test_source_factory_creates_only_the_requested_institutions(self):
        institution = make_fake_institution(country=self.canada)
        cases = (
            ({"holding_institution": institution}, institution.pk),
            ({"holding_institution_id": institution.pk}, institution.pk),
            ({"holding_institution": None}, None),
        )
        for supplied, expected in cases:
            with self.subTest(supplied=supplied):
                with CaptureQueriesContext(connection) as queries:
                    source = make_fake_source(**supplied)
                self.assertEqual(source.holding_institution_id, expected)
                inserts = [
                    q["sql"]
                    for q in queries
                    if 'INSERT INTO "main_app_institution"' in q["sql"]
                ]
                self.assertEqual(inserts, [])
        self.assertIsNotNone(make_fake_source().holding_institution_id)
        self.assertEqual(Institution.objects.count(), 2)

    def test_rism_codes_match_only_in_full(self):
        country = Country.objects.create(
            name="Germany", aliases="Bundesrepublik Deutſchland", rism_code="D"
        )
        self.assertEqual(import_country("Bundesrepublik Deutschland"), country)
        self.assertEqual(import_rism_country("d"), country)
        self.assertNotIn(self.canada, matching_countries("dn"))
        self.assertIn(self.canada, matching_countries("cdn"))
        self.assertIn(self.canada, matching_countries("can", prefix=True))
        with self.assertRaisesMessage(
            ValidationError, "Unrecognized RISM country code"
        ):
            import_rism_country("USA")

    def test_blank_country_on_public_pages_and_in_selector(self):
        institution = Institution.objects.create(
            name="Print (Multiple Copies)", siglum="XX-NN"
        )
        self.assertIsNone(institution.country)
        for empty in (None, "", "[No Country]"):
            self.assertIsNone(import_country(empty))
        self.assertEqual(import_country("[Unknown Country]").name, "Unknown")
        make_fake_source(holding_institution=institution, published=True)
        make_fake_segment(id=settings.CANTUS_SEGMENT_ID)
        make_fake_segment(id=settings.BOWER_SEGMENT_ID)
        for url in (
            reverse("source-list"),
            reverse("institution-list"),
            reverse("institution-detail", args=[institution.pk]),
        ):
            response = self.client.get(url)
            self.assertContains(response, institution.name)
            for forbidden in ("Not recorded", "[No Country]", ">None<"):
                self.assertNotContains(response, forbidden)
        response = self.client.get(reverse("source-list"), {"country": "[No Country]"})
        self.assertEqual(len(response.context["sources"]), 1)
        self.assertNotIn(None, response.context["countries"])

    def test_country_queries_stay_constant_as_lists_grow(self):
        def query_count(url, rows):
            with CaptureQueriesContext(connection) as queries:
                response = self.client.get(url)
                self.assertContains(response, "Canada")
                self.assertEqual(len(response.context["object_list"]), rows)
            return sum('"main_app_country"' in q["sql"] for q in queries)

        self.client.force_login(make_fake_user(is_superuser=True))
        make_fake_source(
            holding_institution=make_fake_institution(country=self.canada),
            source_status=Source.PROOFREAD_PENDING_STATUS,
        )
        urls = [
            reverse("institution-list"),
            reverse("source-list"),
            reverse("proofread-overview") + "?inactive=submitted",
        ]
        counts = [query_count(url, 1) for url in urls]
        for _ in range(4):
            make_fake_source(
                holding_institution=make_fake_institution(country=self.usa),
                source_status=Source.PROOFREAD_PENDING_STATUS,
            )
        self.assertEqual(counts, [query_count(url, 5) for url in urls])

    def test_ambiguous_alias_cannot_select_the_wrong_country(self):
        Country.objects.filter(pk=self.canada.pk).update(aliases="USA")
        self.assertIsNone(find_country("USA"))
        with self.assertRaisesMessage(ValidationError, "Ambiguous country"):
            import_country("USA")
        self.assertEqual(import_country("United States"), self.usa)

    def test_legacy_rebuilds_resolve_stored_codes_and_historical_prefixes(self):
        country = Country.objects.create(name="Local country", rism_code="XY")
        south_africa = Country.objects.create(name="South Africa", rism_code="ZA")
        taiwan = Country.objects.create(name="Taiwan", rism_code="RC")
        examples = [
            ("XY-Lib", country),
            ("XY", country),
            ("SA-Lib", south_africa),
            ("T-Lib", taiwan),
        ]
        sources = [
            make_fake_source(title="City, Library, Ms. 1", siglum=f"{siglum} Ms. 1")
            for siglum, _ in examples
        ]
        for command in ("migrate_records", "migrate_institution_source_records"):
            with self.subTest(command=command), redirect_stdout(StringIO()), patch(
                "main_app.management.commands.migrate_records.get_rism_id",
                return_value=None,
            ):
                call_command(command, empty=True)
                for source, (_, expected) in zip(sources, examples, strict=True):
                    source.refresh_from_db()
                    self.assertEqual(source.holding_institution.country, expected)

    def test_legacy_rebuild_rolls_back_when_a_country_is_missing(self):
        institution = make_fake_institution(country="canada")
        self.assertEqual(institution.country, self.canada)
        source = make_fake_source(
            holding_institution=institution,
            title="Quito, Library, Ms. 1",
            siglum="EC-Test Ms. 1",
        )
        for command in ("migrate_records", "migrate_institution_source_records"):
            with self.subTest(command=command), redirect_stdout(StringIO()):
                with self.assertRaisesMessage(
                    ValidationError, "Unrecognized RISM country code: 'EC'"
                ):
                    call_command(command, empty=True)
                source.refresh_from_db()
                self.assertEqual(source.holding_institution, institution)
                self.assertFalse(Institution.objects.filter(siglum="XX-NN").exists())

    def test_invalid_foreign_key_and_country_deletion_are_rejected(self):
        institution = make_fake_institution(country=self.usa)
        with self.assertRaises(ProtectedError):
            institution.country.delete()
        institution.country_id = 9999999
        with self.assertRaises(ValidationError):
            institution.save()

    def test_old_country_filter_redirects_preserving_other_filters(self):
        source = make_fake_source(
            holding_institution=make_fake_institution(country=self.usa), published=True
        )
        other = make_fake_source(
            holding_institution=make_fake_institution(country="Canada"), published=True
        )
        hidden = make_fake_source(
            holding_institution=source.holding_institution, published=False
        )
        response = self.client.get(
            reverse("source-list"),
            {
                "country": "USA",
                "order": "country",
                "sourceCompleteness": ["1", "2", "3", "4"],
            },
            follow=True,
        )
        self.assertEqual(len(response.redirect_chain), 1)
        self.assertIn("country=United+States+of+America", response.redirect_chain[0][0])
        self.assertIn("sourceCompleteness=4", response.redirect_chain[0][0])
        self.assertIn(source, response.context["sources"])
        self.assertNotIn(other, response.context["sources"])
        self.assertNotIn(hidden, response.context["sources"])
        self.assertEqual(
            list(response.context["countries"]).count("United States of America"), 1
        )

    def test_country_aliases_find_institutions_in_autocomplete(self):
        institution = make_fake_institution(
            name="Library Alpha", city="Town", siglum="AA", country=self.usa
        )
        other = make_fake_institution(
            name="Library Beta", city="Town", siglum="BB", country="Canada"
        )
        self.client.force_login(make_fake_user())
        response = self.client.get(reverse("holding-autocomplete"), {"q": "USA"})
        ids = [row["id"] for row in response.json()["results"]]
        self.assertIn(str(institution.pk), ids)
        self.assertNotIn(str(other.pk), ids)

    def test_country_aliases_find_sources_in_proofreading(self):
        source = make_fake_source(
            holding_institution=make_fake_institution(
                name="Library Alpha", city="Town", siglum="AA", country=self.usa
            ),
            shelfmark="Book One",
            title="",
            siglum="",
        )
        other = make_fake_source(
            holding_institution=make_fake_institution(
                name="Library Beta", city="Town", siglum="BB", country="Canada"
            ),
            shelfmark="Book Two",
            title="",
            siglum="",
        )
        Source.objects.filter(pk__in=[source.pk, other.pk]).update(
            source_status=Source.PROOFREAD_PENDING_STATUS
        )
        self.client.force_login(make_fake_user(is_superuser=True))
        response = self.client.get(
            reverse("proofread-overview"), {"q": "USA", "inactive": "submitted"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(source, response.context["sources"])
        self.assertNotIn(other, response.context["sources"])
