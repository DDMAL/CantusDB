from django.conf import settings
from django.contrib import admin
from django.core.exceptions import ValidationError
from django.db.models.deletion import ProtectedError
from django.test import RequestFactory, TestCase
from django.urls import reverse
import reversion
from reversion.models import Version

from main_app.countries import country_code
from main_app.models import Country, Institution, Source
from main_app.tests.make_fakes import (
    make_fake_institution,
    make_fake_source,
    make_fake_user,
    make_fake_segment,
)


class CountryTests(TestCase):
    def test_import_aliases_and_missing_values(self):
        for name in ("USA", "US", "United States of America", " united STATES "):
            with self.subTest(name=name):
                self.assertEqual(country_code(name), "7012149")
        self.assertEqual(country_code("Czechia"), country_code("Czech Republic"))
        self.assertEqual(country_code("Vatican City"), country_code("Holy See"))
        self.assertEqual(country_code("Unknown"), "unknown")
        for name in (None, "", "[No Country]", "Not recorded"):
            self.assertEqual(country_code(name), "not-recorded")
        with self.assertRaises(ValidationError):
            country_code("UAS")

    def test_institution_form_uses_validated_choices(self):
        request = RequestFactory().get("/")
        request.user = make_fake_user(is_superuser=True)
        model_admin = admin.site._registry[Institution]
        form_class = model_admin.get_form(request)
        institution = make_fake_institution(country="USA")
        data = {
            "name": institution.name,
            "siglum": institution.siglum,
            "country": "7012149",
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
        institution = make_fake_institution(country="USA")
        with self.assertRaises(ProtectedError):
            institution.country.delete()
        institution.country_id = "USA"
        with self.assertRaises(ValidationError):
            institution.save()

    def test_default_is_not_recorded(self):
        institution = Institution.objects.create(
            name="Unlocated library", siglum="XX-Test"
        )
        self.assertEqual(str(institution.country), "Not recorded")

    def test_revision_can_restore_country(self):
        with reversion.create_revision():
            institution = make_fake_institution(country="USA")
        version = Version.objects.get_for_object(institution).first()
        institution.country_id = country_code("Canada")
        institution.save()
        version.revision.revert()
        institution.refresh_from_db()
        self.assertEqual(institution.country.name, "United States")

    def test_old_country_filter_redirects_preserving_other_filters(self):
        source = make_fake_source(
            holding_institution=make_fake_institution(country="USA"), published=True
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
            holding_institution=make_fake_institution(country="[No Country]"),
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
        institution = make_fake_institution(country="USA")
        response = self.client.get(reverse("institution-detail", args=[institution.pk]))
        self.assertContains(response, "https://vocab.getty.edu/tgn/7012149")
        self.assertContains(response, "United States")

    def test_catalogue_cannot_be_modified_in_admin(self):
        request = RequestFactory().get("/")
        request.user = make_fake_user(is_superuser=True)
        model_admin = admin.site._registry[Country]
        self.assertFalse(model_admin.has_add_permission(request))
        self.assertFalse(model_admin.has_change_permission(request))
        self.assertFalse(model_admin.has_delete_permission(request))

    def test_country_aliases_find_institutions_in_autocomplete(self):
        institution = make_fake_institution(
            name="Library Alpha", city="Town", siglum="AA", country="USA"
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
                name="Library Alpha", city="Town", siglum="AA", country="USA"
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
                name="Library Gamma", city="Town", siglum="CC", country="Vatican City"
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
