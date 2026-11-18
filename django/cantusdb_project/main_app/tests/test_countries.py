from contextlib import redirect_stdout
from io import StringIO

from django.conf import settings
from django.contrib import admin
from django.core.exceptions import ValidationError
from django.core.management import call_command
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
            getty_id="7012149",
            aliases="US\nUSA\nUnited States of America",
        )
        cls.canada = Country.objects.create(name="Canada", aliases="CA")
        cls.vatican = Country.objects.create(name="Holy See", aliases="Vatican City")

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

    def test_institution_detail_links_to_getty(self):
        make_fake_segment(id=settings.CANTUS_SEGMENT_ID)
        make_fake_segment(id=settings.BOWER_SEGMENT_ID)
        institution = make_fake_institution(country=self.usa)
        response = self.client.get(reverse("institution-detail", args=[institution.pk]))
        self.assertContains(response, "https://vocab.getty.edu/tgn/7012149")
        self.assertContains(response, "United States")

    def test_admin_can_add_and_correct_a_country_and_its_aliases(self):
        self.client.force_login(make_fake_user(is_superuser=True))
        response = self.client.post(
            reverse("admin:main_app_country_add"),
            {"name": "Iceland", "aliases": "Islande", "getty_id": ""},
        )
        self.assertEqual(response.status_code, 302)
        country = import_country("Islande")
        institution = make_fake_institution(country=country)
        response = self.client.post(
            reverse("admin:main_app_country_change", args=[country.pk]),
            {"name": "Ísland", "aliases": "Iceland\r\n  Islande  ", "getty_id": ""},
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
            {"name": "Ísland", "aliases": "UsA", "getty_id": ""},
        )
        self.assertContains(response, "already a name or alias for United States")
        self.assertEqual(import_country("usa"), self.usa)
        self.assertEqual(import_country("Islande"), country)
        response = self.client.post(
            reverse("admin:main_app_country_change", args=[Country.NOT_RECORDED]),
            {"name": "Missing", "aliases": "", "getty_id": ""},
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
