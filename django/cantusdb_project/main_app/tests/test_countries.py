import json
from contextlib import redirect_stdout
from io import StringIO

from django.conf import settings
from django.contrib import admin
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.test import RequestFactory, TestCase
from django.urls import reverse
import reversion
from reversion.models import Version

from main_app.countries import find_country, import_country
from main_app.models import Country, Institution, Source
from main_app.tests.make_fakes import (
    make_fake_institution,
    make_fake_source,
    make_fake_user,
    make_fake_segment,
)


class CountryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.usa = Country.objects.create(
            name="United States",
            authorities={"getty_tgn": "7012149", "wikidata": "Q30"},
            aliases="US\nUSA\nUnited States of America",
        )
        cls.canada = Country.objects.create(name="Canada", aliases="CA")
        cls.vatican = Country.objects.create(name="Holy See", aliases="Vatican City")

    def test_loader_is_repeatable_and_preserves_local_edits(self):
        self.assertEqual(self.canada.pk, Country.CANADA)
        self.canada.authorities = {
            "getty_tgn": "123456789",
            "Local register": "https://example.org/canada",
        }
        self.canada.aliases = "CA\nLocal spelling"
        self.canada.save()
        call_command("load_countries", stdout=StringIO())
        self.canada.refresh_from_db()
        self.assertEqual(
            self.canada.authorities,
            {
                "getty_tgn": "123456789",
                "Local register": "https://example.org/canada",
                "wikidata": "Q16",
            },
        )
        self.assertEqual(
            self.canada.aliases.splitlines(), ["CA", "Local spelling", "CDN", "CAN"]
        )
        japan = import_country("J")
        self.assertEqual(japan.authorities, {"getty_tgn": "1000120", "wikidata": "Q17"})
        original_count = Country.objects.count()
        japan.name = "Nippon"
        japan.aliases = ""
        japan.authorities = {"wikidata": "Q17"}
        japan.save()
        call_command("load_countries", stdout=StringIO())
        japan.refresh_from_db()
        self.assertEqual(Country.objects.count(), original_count)
        self.assertEqual(
            (japan.name, japan.aliases, japan.authorities),
            ("Nippon", "", {"wikidata": "Q17"}),
        )
        self.assertIsNone(find_country("J"))
        duplicate = Country(name="Japan")
        with self.assertRaises(ValidationError):
            duplicate.full_clean()
        for _ in range(2):
            with self.assertRaises(IntegrityError), transaction.atomic():
                duplicate.save()
        japan.refresh_from_db()
        self.assertEqual(
            (japan.name, japan.aliases, japan.authorities),
            ("Nippon", "", {"wikidata": "Q17"}),
        )

    def test_wikidata_only_country_uses_catalogue_id_before_loading(self):
        self.canada.delete()
        self.client.force_login(make_fake_user(is_superuser=True))
        url = reverse("admin:main_app_country_add")
        response = self.client.post(
            url,
            {
                "name": "Dominion of Canada",
                "aliases": "",
                "authorities": '{"wikidata":"Q16"}',
            },
        )
        self.assertEqual(response.status_code, 302)
        canada = Country.objects.get(pk=Country.CANADA)
        self.assertEqual(canada.name, "Dominion of Canada")
        call_command("load_countries", stdout=StringIO())
        self.assertFalse(Country.objects.filter(name="Canada").exists())
        response = self.client.post(
            url, {"name": "Canada", "aliases": "", "authorities": ""}
        )
        self.assertContains(
            response, "is already a name or alias for Dominion of Canada"
        )
        self.assertEqual(find_country("Canada"), canada)
        with self.assertRaises(ValidationError):
            Country(name="Japan", authorities={"wikidata": "Q16"}).save()

    def test_country_edit_opened_before_load_cannot_reset_import_state(self):
        stale = Country.objects.get(pk=self.canada.pk)
        call_command("load_countries", stdout=StringIO())
        stale.authorities = {}
        stale.aliases = ""
        stale.save()
        call_command("load_countries", stdout=StringIO())
        stale.refresh_from_db()
        self.assertTrue(stale.catalogue_loaded)
        self.assertEqual(stale.authorities, {})
        self.assertEqual(stale.aliases, "")

    def test_admin_validates_and_saves_multiple_authorities(self):
        self.client.force_login(make_fake_user(is_superuser=True))
        url = reverse("admin:main_app_country_change", args=[self.canada.pk])
        data = {"name": "Canada", "aliases": "CA"}
        for invalid in (
            '["Q16"]',
            '{"wikidata":"16"}',
            '{"getty_tgn":"Q16"}',
            '{"other":"16"}',
            '{"Local":"mailto:records@example.org"}',
            '{"Local":72}',
            '{" ":"https://example.org/canada"}',
            '{"A":"https://example.org/canada","B":"https://example.org/canada"}',
            '{"Wikidata":"https://vocab.getty.edu/tgn/7005685"}',
            '{"Another label":"https://www.wikidata.org/wiki/Q30"}',
            '{"Wikidata":"Q16","wikidata":"Q16"}',
            '{"getty_tgn":"7012149"}',
            '{"wikidata":"Q30"}',
        ):
            with self.subTest(authorities=invalid):
                response = self.client.post(url, {**data, "authorities": invalid})
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.context["adminform"].form.errors)
        response = self.client.post(
            url, {**data, "authorities": '{"getty_tgn":"7005685","wikidata":"Q16"}'}
        )
        self.assertEqual(response.status_code, 302)
        self.canada.refresh_from_db()
        self.assertEqual(
            self.canada.authorities, {"getty_tgn": "7005685", "wikidata": "Q16"}
        )
        for key, value in self.canada.authorities.items():
            with self.subTest(key=key), self.assertRaises(
                IntegrityError
            ), transaction.atomic():
                Country.objects.filter(pk=self.vatican.pk).update(
                    authorities={key: value}
                )

    def test_custom_authority_can_be_added_displayed_and_searched(self):
        self.client.force_login(make_fake_user(is_superuser=True))
        record_url = "https://www.geonames.org/6251999/"
        url = reverse("admin:main_app_country_change", args=[self.canada.pk])
        response = self.client.post(
            url,
            {
                "name": "Canada",
                "aliases": "CA",
                "authorities": json.dumps(
                    {
                        "GeoNames": record_url,
                        "Wikidata": "https://www.wikidata.org/wiki/Q16",
                    }
                ),
            },
        )
        self.assertRedirects(response, reverse("admin:main_app_country_changelist"))
        self.canada.refresh_from_db()
        self.assertEqual(
            self.canada.authorities, {"GeoNames": record_url, "wikidata": "Q16"}
        )
        with self.assertNumQueries(0):
            self.assertEqual(
                self.canada.authority_links,
                [
                    ("Wikidata", "https://www.wikidata.org/wiki/Q16"),
                    ("GeoNames", record_url),
                ],
            )
        for term in ("GeoNames", "6251999"):
            response = self.client.get(
                reverse("admin:main_app_country_changelist"), {"q": term}
            )
            self.assertEqual(list(response.context["cl"].result_list), [self.canada])
        make_fake_segment(id=settings.CANTUS_SEGMENT_ID)
        make_fake_segment(id=settings.BOWER_SEGMENT_ID)
        institution = make_fake_institution(country=self.canada)
        response = self.client.get(reverse("institution-detail", args=[institution.pk]))
        country_url = reverse("country-detail", args=[self.canada.pk])
        self.assertContains(response, f'<a href="{country_url}">Canada</a>', html=True)
        self.assertNotContains(response, record_url)
        response = self.client.get(country_url)
        self.assertContains(response, f'<a href="{record_url}">GeoNames</a>', html=True)
        call_command("load_countries", stdout=StringIO())
        self.canada.refresh_from_db()
        self.assertEqual(self.canada.authorities["GeoNames"], record_url)

    def test_custom_record_url_cannot_be_claimed_under_another_label(self):
        record_url = "https://example.org/countries/123"
        self.canada.authorities = {"Gazetteer": record_url}
        self.canada.save()
        self.usa.authorities = {"Another label": record_url}
        with self.assertRaisesMessage(ValidationError, "already belongs to Canada"):
            self.usa.full_clean()
        with self.assertRaises(IntegrityError), transaction.atomic():
            Country.objects.filter(pk=self.usa.pk).update(
                authorities=self.usa.authorities
            )

    def test_import_aliases_and_missing_values(self):
        for name in ("USA", "US", "United States of America", " united STATES "):
            with self.subTest(name=name):
                self.assertEqual(import_country(name), self.usa)
        self.assertEqual(import_country("Vatican City"), self.vatican)
        self.assertEqual(import_country("Unknown").pk, Country.UNKNOWN)
        for name in (None, "", "[No Country]", "Not recorded"):
            self.assertEqual(import_country(name).pk, Country.NOT_RECORDED)
        with self.assertRaisesMessage(ValidationError, "Add the country or its alias"):
            import_country("UAS")

    def test_ambiguous_alias_cannot_select_the_wrong_country(self):
        Country.objects.filter(pk=self.canada.pk).update(aliases="USA")
        self.assertIsNone(find_country("USA"))
        with self.assertRaisesMessage(ValidationError, "Ambiguous country"):
            import_country("USA")
        self.assertEqual(import_country("United States"), self.usa)

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
                    ValidationError, "Unrecognized country: 'Ecuador'"
                ):
                    call_command(command, empty=True)
                source.refresh_from_db()
                self.assertEqual(source.holding_institution, institution)
                self.assertFalse(Institution.objects.filter(siglum="XX-NN").exists())

    def test_institution_form_uses_validated_choices(self):
        request = RequestFactory().get("/")
        request.user = make_fake_user(is_superuser=True)
        model_admin = admin.site._registry[Institution]
        form_class = model_admin.get_form(request)
        institution = make_fake_institution(country=self.usa)
        data = {
            "name": institution.name,
            "siglum": institution.siglum,
            "country": self.usa.pk,
        }
        self.assertTrue(form_class(data, instance=institution).is_valid())
        data["country"] = "USA"
        form = form_class(data, instance=institution)
        self.assertFalse(form.is_valid())
        self.assertIn("country", form.errors)
        choices = dict(form.fields["country"].choices)
        self.assertIn("United States", list(choices.values()))
        self.assertIn("Unknown", list(choices.values()))
        self.assertIn("Not recorded", list(choices.values()))

    def test_invalid_foreign_key_and_country_deletion_are_rejected(self):
        institution = make_fake_institution(country=self.usa)
        with self.assertRaises(ProtectedError):
            institution.country.delete()
        institution.country_id = 9999999
        with self.assertRaises(ValidationError):
            institution.save()

    def test_default_is_not_recorded(self):
        institution = Institution.objects.create(
            name="Unlocated library", siglum="XX-Test"
        )
        self.assertEqual(str(institution.country), "Not recorded")

    def test_revision_can_restore_country(self):
        with reversion.create_revision():
            institution = make_fake_institution(country=self.usa)
        version = Version.objects.get_for_object(institution).first()
        institution.country = self.canada
        institution.save()
        version.revision.revert()
        institution.refresh_from_db()
        self.assertEqual(institution.country.name, "United States")

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
        self.assertIn("country=United+States", response.redirect_chain[0][0])
        self.assertIn("sourceCompleteness=4", response.redirect_chain[0][0])
        self.assertIn(source, response.context["sources"])
        self.assertNotIn(other, response.context["sources"])
        self.assertNotIn(hidden, response.context["sources"])
        self.assertEqual(list(response.context["countries"]).count("United States"), 1)

    def test_unknown_and_not_recorded_filter_separately(self):
        unknown = make_fake_source(
            holding_institution=make_fake_institution(country="Unknown"), published=True
        )
        absent = make_fake_source(
            holding_institution=make_fake_institution(
                country=import_country("[No Country]")
            ),
            published=True,
        )
        for name, included, excluded in (
            ("Unknown", unknown, absent),
            ("[No Country]", absent, unknown),
        ):
            with self.subTest(name=name):
                response = self.client.get(
                    reverse("source-list"), {"country": name}, follow=True
                )
                self.assertIn(included, response.context["sources"])
                self.assertNotIn(excluded, response.context["sources"])

    def test_institution_and_country_links_identify_different_records(self):
        from main_app.identifiers import ExternalIdentifiers
        from main_app.models import InstitutionIdentifier

        make_fake_segment(id=settings.CANTUS_SEGMENT_ID)
        make_fake_segment(id=settings.BOWER_SEGMENT_ID)
        institution = make_fake_institution(country=self.usa)
        InstitutionIdentifier.objects.create(
            institution=institution,
            identifier_type=ExternalIdentifiers.WIKIDATA,
            identifier="Q62535993",
        )
        response = self.client.get(reverse("institution-detail", args=[institution.pk]))
        self.assertContains(response, "https://www.wikidata.org/wiki/Q62535993")
        self.assertNotContains(response, "https://vocab.getty.edu/")
        self.assertNotContains(response, "https://www.wikidata.org/wiki/Q30")
        self.assertNotContains(response, "ODC Attribution License")
        response = self.client.get(reverse("country-detail", args=[self.usa.pk]))
        self.assertContains(response, "https://vocab.getty.edu/tgn/7012149")
        self.assertContains(response, "https://www.wikidata.org/wiki/Q30")
        self.assertContains(response, "ODC Attribution License")
        self.assertNotContains(response, "https://www.wikidata.org/wiki/Q62535993")

    def test_country_page_for_a_local_country_without_links(self):
        local = Country.objects.create(name="Local territory")
        self.assertContains(self.client.get(local.detail_url), "No external records")
        for pk in (Country.NOT_RECORDED, Country.UNKNOWN):
            self.assertEqual(
                self.client.get(reverse("country-detail", args=[pk])).status_code, 404
            )
            self.assertIsNone(Country.objects.get(pk=pk).detail_url)

    def test_admin_can_add_and_correct_a_country_and_its_aliases(self):
        self.client.force_login(make_fake_user(is_superuser=True))
        response = self.client.post(
            reverse("admin:main_app_country_add"),
            {"name": "Iceland", "aliases": "Islande", "authorities": ""},
        )
        self.assertEqual(response.status_code, 302)
        country = import_country("Islande")
        institution = make_fake_institution(country=country)
        response = self.client.post(
            reverse("admin:main_app_country_change", args=[country.pk]),
            {"name": "Ísland", "aliases": "Iceland\r\n  Islande  ", "authorities": ""},
        )
        self.assertEqual(response.status_code, 302)
        institution.refresh_from_db()
        self.assertEqual(institution.country.name, "Ísland")
        self.assertEqual(import_country("iceland"), institution.country)
        source = make_fake_source(holding_institution=institution, published=True)
        response = self.client.get(
            reverse("source-list"), {"country": "Islande"}, follow=True
        )
        self.assertEqual(response.request["QUERY_STRING"], "country=%C3%8Dsland")
        self.assertIn("Ísland", response.context["countries"])
        self.assertIn(source, response.context["sources"])

        response = self.client.post(
            reverse("admin:main_app_country_change", args=[country.pk]),
            {"name": "Ísland", "aliases": "UsA", "authorities": ""},
        )
        self.assertContains(response, "already a name or alias for United States")
        self.assertEqual(import_country("usa"), self.usa)
        self.assertEqual(import_country("Islande"), country)
        response = self.client.post(
            reverse("admin:main_app_country_change", args=[Country.NOT_RECORDED]),
            {"name": "Missing", "aliases": "", "authorities": ""},
        )
        self.assertEqual(response.status_code, 403)

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

    def test_short_country_search_keeps_partial_name_matches(self):
        canada = make_fake_source(
            holding_institution=make_fake_institution(
                name="Library Beta", city="Town", siglum="BB", country="Canada"
            ),
            shelfmark="Book Two",
            title="",
            siglum="",
        )
        vatican = make_fake_source(
            holding_institution=make_fake_institution(
                name="Library Gamma", city="Town", siglum="CC", country=self.vatican
            ),
            shelfmark="Book Three",
            title="",
            siglum="",
        )
        Source.objects.filter(pk__in=[canada.pk, vatican.pk]).update(
            source_status=Source.PROOFREAD_PENDING_STATUS
        )
        self.client.force_login(make_fake_user(is_superuser=True))
        response = self.client.get(
            reverse("proofread-overview"), {"q": "ca", "inactive": "submitted"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(canada, response.context["sources"])
        self.assertIn(vatican, response.context["sources"])
