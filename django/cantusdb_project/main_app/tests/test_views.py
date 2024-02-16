import random
from django.urls import reverse
from django.test import TestCase
from articles.tests.test_articles import make_fake_article
from main_app.views.feast import FeastListView
from django.http.response import JsonResponse
import json
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import Client
from django.db.models import Q
from django.db.models.functions import Lower
import csv

from faker import Faker

from users.models import User
from .make_fakes import (
    make_fake_century,
    make_fake_chant,
    make_fake_feast,
    make_fake_genre,
    make_fake_notation,
    make_fake_office,
    make_fake_provenance,
    make_fake_rism_siglum,
    make_fake_segment,
    make_fake_sequence,
    make_fake_source,
    make_fake_volpiano,
    make_random_string,
    add_accents_to_string,
)

from main_app.models import (
    Century,
    Chant,
    Differentia,
    Feast,
    Genre,
    Notation,
    Office,
    Provenance,
    Segment,
    Sequence,
    Source,
)

# run with `python -Wa manage.py test main_app.tests.test_views`
# the -Wa flag tells Python to display deprecation warnings


# Create a Faker instance with locale set to Latin
faker = Faker("la")


def get_random_search_term(target):
    """Helper function for generating a random slice of a string.

    Args:
        target (str): The content of the field to search.

    Returns:
        str: A random slice of `target`
    """
    if len(target) <= 2:
        search_term = target
    else:
        slice_start = random.randint(0, len(target) - 2)
        slice_end = random.randint(slice_start + 2, len(target))
        search_term = target[slice_start:slice_end]
    return search_term


class PermissionsTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        Group.objects.create(name="project manager")
        Group.objects.create(name="contributor")
        Group.objects.create(name="editor")

        for i in range(5):
            source = make_fake_source()
            for i in range(5):
                Chant.objects.create(source=source)
                Sequence.objects.create(source=source)

    def setUp(self):
        self.user = get_user_model().objects.create(email="test@test.com")
        self.user.set_password("pass")
        self.user.save()
        self.client = Client()

    def test_login(self):
        source = make_fake_source()
        chant = make_fake_chant()
        sequence = make_fake_sequence()

        # currently not logged in, should redirect

        # ChantCreateView
        response = self.client.get(
            reverse(
                "chant-create",
                args=[source.id],
            )
        )
        self.assertRedirects(response, f"/login/?next=/chant-create/{source.id}")

        # ChantDeleteView
        response = self.client.get(
            reverse(
                "chant-delete",
                args=[chant.id],
            )
        )
        self.assertRedirects(response, f"/login/?next=/chant/{chant.id}/delete")

        # SourceEditChantsView
        response = self.client.get(
            reverse(
                "source-edit-chants",
                args=[source.id],
            )
        )
        self.assertRedirects(response, f"/login/?next=/edit-chants/{source.id}")

        # SequenceEditView
        response = self.client.get(
            reverse(
                "sequence-edit",
                args=[sequence.id],
            )
        )
        self.assertRedirects(response, f"/login/?next=/edit-sequence/{sequence.id}")

        # SourceCreateView
        response = self.client.get(reverse("source-create"))
        self.assertRedirects(response, "/login/?next=/source-create/")

        # SourceEditView
        response = self.client.get(
            reverse(
                "source-edit",
                args=[source.id],
            )
        )
        self.assertRedirects(response, f"/login/?next=/edit-source/{source.id}")

        # SourceDeleteView
        response = self.client.get(
            reverse(
                "source-delete",
                args=[source.id],
            )
        )
        self.assertRedirects(response, f"/login/?next=/source/{source.id}/delete")

        # UserSourceListView
        response = self.client.get(reverse("my-sources"))
        self.assertRedirects(response, "/login/?next=/my-sources/")

        # UserListView
        response = self.client.get(reverse("user-list"))
        self.assertRedirects(response, "/login/?next=/users/")

    def test_permissions_project_manager(self):
        project_manager = Group.objects.get(name="project manager")
        project_manager.user_set.add(self.user)
        self.client.login(email="test@test.com", password="pass")

        # get random source, chant and sequence
        source = Source.objects.order_by("?").first()
        chant = Chant.objects.order_by("?").first()
        sequence = Sequence.objects.order_by("?").first()

        # ChantCreateView
        response = self.client.get(
            reverse(
                "chant-create",
                args=[source.id],
            )
        )
        self.assertEqual(response.status_code, 200)

        # ChantDeleteView
        response = self.client.get(
            reverse(
                "chant-delete",
                args=[chant.id],
            )
        )
        self.assertEqual(response.status_code, 200)

        # SourceEditChantsView
        response = self.client.get(
            reverse(
                "source-edit-chants",
                args=[source.id],
            )
        )
        self.assertEqual(response.status_code, 200)

        # SequenceEditView
        response = self.client.get(
            reverse(
                "sequence-edit",
                args=[sequence.id],
            )
        )
        self.assertEqual(response.status_code, 200)

        # SourceCreateView
        response = self.client.get(
            reverse(
                "source-create",
            )
        )
        self.assertEqual(response.status_code, 200)

        # SourceEditView
        response = self.client.get(
            reverse(
                "source-edit",
                args=[source.id],
            )
        )
        self.assertEqual(response.status_code, 200)

        # SourceDeleteView
        response = self.client.get(
            reverse(
                "source-delete",
                args=[source.id],
            )
        )
        self.assertEqual(response.status_code, 200)

        # ContentOverview
        response = self.client.get(reverse("content-overview"))
        self.assertEqual(response.status_code, 200)

    def test_permissions_contributor(self):
        contributor = Group.objects.get(name="contributor")
        contributor.user_set.add(self.user)
        self.client.login(email="test@test.com", password="pass")

        # a source assigned to the current user
        assigned_source = make_fake_source()
        self.user.sources_user_can_edit.add(assigned_source)
        for i in range(5):
            Chant.objects.create(source=assigned_source)
        chant_in_assigned_source = (
            Chant.objects.filter(source=assigned_source).order_by("?").first()
        )

        # a source created by the current user
        source_created_by_contributor = make_fake_source()
        source_created_by_contributor.created_by = self.user
        source_created_by_contributor.save()
        for i in range(5):
            Chant.objects.create(source=source_created_by_contributor)
        chant_in_source_created_by_contributor = (
            Chant.objects.filter(source=source_created_by_contributor)
            .order_by("?")
            .first()
        )

        # did not create the source, was not assigned the source
        restricted_source = (
            Source.objects.filter(~Q(created_by=self.user) & ~Q(id=assigned_source.id))
            .order_by("?")
            .first()
        )
        restricted_chant = (
            Chant.objects.filter(source=restricted_source).order_by("?").first()
        )

        # a random sequence
        sequence = Sequence.objects.order_by("?").first()

        # ChantCreateView
        # response = self.client.get(f"/chant-create/{restricted_source.id}")
        response = self.client.get(
            reverse(
                "chant-create",
                args=[restricted_source.id],
            )
        )
        self.assertEqual(response.status_code, 403)

        response = self.client.get(f"/chant-create/{source_created_by_contributor.id}")
        self.assertEqual(response.status_code, 200)

        response = self.client.get(f"/chant-create/{assigned_source.id}")
        self.assertEqual(response.status_code, 200)

        # ChantDeleteView
        response = self.client.get(f"/chant/{restricted_chant.id}/delete")
        self.assertEqual(response.status_code, 403)

        response = self.client.get(
            f"/chant/{chant_in_source_created_by_contributor.id}/delete"
        )
        self.assertEqual(response.status_code, 200)

        response = self.client.get(f"/chant/{chant_in_assigned_source.id}/delete")
        self.assertEqual(response.status_code, 200)

        # SourceEditChantsView
        response = self.client.get(f"/edit-chants/{restricted_source.id}")
        self.assertEqual(response.status_code, 403)

        response = self.client.get(f"/edit-chants/{source_created_by_contributor.id}")
        self.assertEqual(response.status_code, 200)

        response = self.client.get(f"/edit-chants/{assigned_source.id}")
        self.assertEqual(response.status_code, 200)

        # SequenceEditView
        response = self.client.get(f"/edit-sequence/{sequence.id}")
        self.assertEqual(response.status_code, 403)

        # SourceCreateView
        response = self.client.get("/source-create/")
        self.assertEqual(response.status_code, 200)

        # SourceEditView
        response = self.client.get(f"/edit-source/{restricted_source.id}")
        self.assertEqual(response.status_code, 403)

        response = self.client.get(f"/edit-source/{source_created_by_contributor.id}")
        self.assertEqual(response.status_code, 200)

        response = self.client.get(f"/edit-source/{assigned_source.id}")
        self.assertEqual(response.status_code, 403)

        # SourceDeleteView
        response = self.client.get(f"/source/{restricted_source.id}/delete")
        self.assertEqual(response.status_code, 403)

        response = self.client.get(f"/source/{source_created_by_contributor.id}/delete")
        self.assertEqual(response.status_code, 200)

        response = self.client.get(f"/source/{assigned_source.id}/delete")
        self.assertEqual(response.status_code, 403)

        # Content Overview
        response = self.client.get(reverse("content-overview"))
        self.assertEqual(response.status_code, 403)

    def test_permissions_editor(self):
        editor = Group.objects.get(name="editor")
        editor.user_set.add(self.user)
        self.client.login(email="test@test.com", password="pass")

        # a source assigned to the current user
        assigned_source = make_fake_source()
        self.user.sources_user_can_edit.add(assigned_source)
        for i in range(5):
            Chant.objects.create(source=assigned_source)
        chant_in_assigned_source = (
            Chant.objects.filter(source=assigned_source).order_by("?").first()
        )

        # a source created by the current user
        source_created_by_contributor = make_fake_source()
        source_created_by_contributor.created_by = self.user
        source_created_by_contributor.save()
        for i in range(5):
            Chant.objects.create(source=source_created_by_contributor)
        chant_in_source_created_by_contributor = (
            Chant.objects.filter(source=source_created_by_contributor)
            .order_by("?")
            .first()
        )

        # did not create the source, was not assigned the source
        restricted_source = (
            Source.objects.filter(~Q(created_by=self.user) & ~Q(id=assigned_source.id))
            .order_by("?")
            .first()
        )
        restricted_chant = (
            Chant.objects.filter(source=restricted_source).order_by("?").first()
        )

        # a random sequence
        sequence = Sequence.objects.order_by("?").first()

        # ChantCreateView
        response = self.client.get(f"/chant-create/{restricted_source.id}")
        self.assertEqual(response.status_code, 403)

        response = self.client.get(f"/chant-create/{source_created_by_contributor.id}")
        self.assertEqual(response.status_code, 200)

        response = self.client.get(f"/chant-create/{assigned_source.id}")
        self.assertEqual(response.status_code, 200)

        # ChantDeleteView
        response = self.client.get(f"/chant/{restricted_chant.id}/delete")
        self.assertEqual(response.status_code, 403)

        response = self.client.get(
            f"/chant/{chant_in_source_created_by_contributor.id}/delete"
        )
        self.assertEqual(response.status_code, 200)

        response = self.client.get(f"/chant/{chant_in_assigned_source.id}/delete")
        self.assertEqual(response.status_code, 200)

        # SourceEditChantsView
        response = self.client.get(f"/edit-chants/{restricted_source.id}")
        self.assertEqual(response.status_code, 403)

        response = self.client.get(f"/edit-chants/{source_created_by_contributor.id}")
        self.assertEqual(response.status_code, 200)

        response = self.client.get(f"/edit-chants/{assigned_source.id}")
        self.assertEqual(response.status_code, 200)

        # SequenceEditView
        response = self.client.get(f"/edit-sequence/{sequence.id}")
        self.assertEqual(response.status_code, 403)

        # SourceCreateView
        response = self.client.get("/source-create/")
        self.assertEqual(response.status_code, 200)

        # SourceEditView
        response = self.client.get(f"/edit-source/{restricted_source.id}")
        self.assertEqual(response.status_code, 403)

        response = self.client.get(f"/edit-source/{source_created_by_contributor.id}")
        self.assertEqual(response.status_code, 200)

        response = self.client.get(f"/edit-source/{assigned_source.id}")
        self.assertEqual(response.status_code, 200)

        # SourceDeleteView
        response = self.client.get(f"/source/{restricted_source.id}/delete")
        self.assertEqual(response.status_code, 403)

        response = self.client.get(f"/source/{source_created_by_contributor.id}/delete")
        self.assertEqual(response.status_code, 200)

        response = self.client.get(f"/source/{assigned_source.id}/delete")
        self.assertEqual(response.status_code, 200)

        # Content Overview
        response = self.client.get(reverse("content-overview"))
        self.assertEqual(response.status_code, 403)

    def test_permissions_default(self):
        self.client.login(email="test@test.com", password="pass")

        # get random source, chant and sequence
        source = Source.objects.order_by("?").first()
        chant = Chant.objects.order_by("?").first()
        sequence = Sequence.objects.order_by("?").first()

        # ChantCreateView
        response = self.client.get(f"/chant-create/{source.id}")
        self.assertEqual(response.status_code, 403)

        # ChantDeleteView
        response = self.client.get(f"/chant/{chant.id}/delete")
        self.assertEqual(response.status_code, 403)

        # SourceEditChantsView
        response = self.client.get(f"/edit-chants/{source.id}")
        self.assertEqual(response.status_code, 403)

        # SequenceEditView
        response = self.client.get(f"/edit-sequence/{sequence.id}")
        self.assertEqual(response.status_code, 403)

        # SourceCreateView
        response = self.client.get("/source-create/")
        self.assertEqual(response.status_code, 403)

        # SourceEditView
        response = self.client.get(f"/edit-source/{source.id}")
        self.assertEqual(response.status_code, 403)

        # SourceDeleteView
        response = self.client.get(f"/source/{source.id}/delete")
        self.assertEqual(response.status_code, 403)

        # Content Overview
        response = self.client.get(reverse("content-overview"))
        self.assertEqual(response.status_code, 403)


class CenturyDetailViewTest(TestCase):
    def test_view_url_path(self):
        century = make_fake_century()
        response = self.client.get(f"/century/{century.id}")
        self.assertEqual(response.status_code, 200)

    def test_view_url_reverse_name(self):
        century = make_fake_century()
        response = self.client.get(reverse("century-detail", args=[century.id]))
        self.assertEqual(response.status_code, 200)

    def test_url_and_templates(self):
        century = make_fake_century()
        response = self.client.get(reverse("century-detail", args=[century.id]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "base.html")
        self.assertTemplateUsed(response, "century_detail.html")

    def test_listed_sources(self):
        century = make_fake_century()
        century_sources = [
            make_fake_source(century=century, published=True) for _ in range(5)
        ]
        response = self.client.get(reverse("century-detail", args=[century.id]))
        returned_sources = response.context["sources"]
        for source in century_sources:
            self.assertIn(source, returned_sources)

    def test_unpublished_sources_not_listed(self):
        century = make_fake_century()
        published_sources = [
            make_fake_source(century=century, published=True) for _ in range(5)
        ]
        unpublished_sources = [
            make_fake_source(century=century, published=False) for _ in range(5)
        ]
        response = self.client.get(reverse("century-detail", args=[century.id]))
        returned_sources = response.context["sources"]
        for source in published_sources:
            self.assertIn(source, returned_sources)
        for source in unpublished_sources:
            self.assertNotIn(source, returned_sources)


class ChantListViewTest(TestCase):
    def test_url_and_templates(self):
        cantus_segment = make_fake_segment(id=4063)
        source = make_fake_source(segment=cantus_segment)
        response = self.client.get(reverse("chant-list", args=[source.id]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "base.html")
        self.assertTemplateUsed(response, "chant_list.html")

    def test_published_vs_unpublished(self):
        cantus_segment = make_fake_segment(id=4063)

        published_source = make_fake_source(segment=cantus_segment, published=True)
        response_1 = self.client.get(reverse("chant-list", args=[published_source.id]))
        self.assertEqual(response_1.status_code, 200)

        unpublished_source = make_fake_source(segment=cantus_segment, published=False)
        response_2 = self.client.get(
            reverse("chant-list", args=[unpublished_source.id])
        )
        self.assertEqual(response_2.status_code, 403)

    def test_visibility_by_segment(self):
        cantus_segment = make_fake_segment(id=4063)
        cantus_source = make_fake_source(segment=cantus_segment, published=True)
        response_1 = self.client.get(reverse("chant-list", args=[cantus_source.id]))
        self.assertEqual(response_1.status_code, 200)

        # The chant list ("Browse Chants") page should only be visitable
        # for sources in the CANTUS Database segment, as sources in the Bower
        # segment contain no chants
        bower_segment = make_fake_segment(id=4064)
        bower_source = make_fake_source(segment=bower_segment, published=True)
        response_1 = self.client.get(reverse("chant-list", args=[bower_source.id]))
        self.assertEqual(response_1.status_code, 404)

    def test_filter_by_source(self):
        cantus_segment = make_fake_segment(id=4063)
        source = make_fake_source(segment=cantus_segment)
        another_source = make_fake_source(segment=cantus_segment)
        chant_in_source = Chant.objects.create(source=source)
        chant_in_another_source = Chant.objects.create(source=another_source)
        response = self.client.get(reverse("chant-list", args=[source.id]))
        chants = response.context["chants"]
        self.assertIn(chant_in_source, chants)
        self.assertNotIn(chant_in_another_source, chants)

    def test_filter_by_feast(self):
        cantus_segment = make_fake_segment(id=4063)
        source = make_fake_source(segment=cantus_segment)
        feast = make_fake_feast()
        another_feast = make_fake_feast()
        chant_in_feast = Chant.objects.create(source=source, feast=feast)
        chant_in_another_feast = Chant.objects.create(
            source=source, feast=another_feast
        )
        response = self.client.get(
            reverse("chant-list", args=[source.id]), {"feast": feast.id}
        )
        chants = response.context["chants"]
        self.assertIn(chant_in_feast, chants)
        self.assertNotIn(chant_in_another_feast, chants)

    def test_filter_by_genre(self):
        cantus_segment = make_fake_segment(id=4063)
        source = make_fake_source(segment=cantus_segment)
        genre = make_fake_genre()
        another_genre = make_fake_genre()
        chant_in_genre = Chant.objects.create(source=source, genre=genre)
        chant_in_another_genre = Chant.objects.create(
            source=source, genre=another_genre
        )
        response = self.client.get(
            reverse("chant-list", args=[source.id]), {"genre": genre.id}
        )
        chants = response.context["chants"]
        self.assertIn(chant_in_genre, chants)
        self.assertNotIn(chant_in_another_genre, chants)

    def test_filter_by_folio(self):
        cantus_segment = make_fake_segment(id=4063)
        source = make_fake_source(segment=cantus_segment)
        chant_on_folio = Chant.objects.create(source=source, folio="001r")
        chant_on_another_folio = Chant.objects.create(source=source, folio="002r")
        response = self.client.get(
            reverse("chant-list", args=[source.id]), {"folio": "001r"}
        )
        chants = response.context["chants"]
        self.assertIn(chant_on_folio, chants)
        self.assertNotIn(chant_on_another_folio, chants)

    def test_search_full_text(self):
        cantus_segment = make_fake_segment(id=4063)
        source = make_fake_source(segment=cantus_segment)
        chant = Chant.objects.create(
            source=source, manuscript_full_text=faker.sentence()
        )
        search_term = get_random_search_term(chant.manuscript_full_text)
        response = self.client.get(
            reverse("chant-list", args=[source.id]), {"search_text": search_term}
        )
        self.assertIn(chant, response.context["chants"])

    def test_search_incipit(self):
        cantus_segment = make_fake_segment(id=4063)
        source = make_fake_source(segment=cantus_segment)
        chant = Chant.objects.create(
            source=source,
            incipit=faker.sentence(),
        )
        search_term = get_random_search_term(chant.incipit)
        response = self.client.get(
            reverse("chant-list", args=[source.id]), {"search_text": search_term}
        )
        self.assertIn(chant, response.context["chants"])

    def test_search_full_text_std_spelling(self):
        cantus_segment = make_fake_segment(id=4063)
        source = make_fake_source(segment=cantus_segment)
        chant = Chant.objects.create(
            source=source,
            manuscript_full_text_std_spelling=faker.sentence(),
        )
        search_term = get_random_search_term(chant.manuscript_full_text_std_spelling)
        response = self.client.get(
            reverse("chant-list", args=[source.id]), {"search_text": search_term}
        )
        self.assertIn(chant, response.context["chants"])

    def test_context_source(self):
        cantus_segment = make_fake_segment(id=4063)
        source = make_fake_source(segment=cantus_segment)
        response = self.client.get(reverse("chant-list", args=[source.id]))
        self.assertEqual(source, response.context["source"])

    def test_context_folios(self):
        cantus_segment = make_fake_segment(id=4063)
        source = make_fake_source(segment=cantus_segment)
        Chant.objects.create(source=source, folio="001r")
        Chant.objects.create(source=source, folio="001r")
        Chant.objects.create(source=source, folio="001v")
        Chant.objects.create(source=source, folio="001v")
        Chant.objects.create(source=source, folio="002r")
        Chant.objects.create(source=source, folio="002v")
        response = self.client.get(reverse("chant-list", args=[source.id]))
        # the element in "folios" should be unique and ordered in this way
        folios = response.context["folios"]
        self.assertEqual(list(folios), ["001r", "001v", "002r", "002v"])

    def test_context_feasts_with_folios(self):
        cantus_segment = make_fake_segment(id=4063)
        source = make_fake_source(segment=cantus_segment)
        feast_1 = make_fake_feast()
        feast_2 = make_fake_feast()
        Chant.objects.create(source=source, folio="001r", feast=feast_1)
        Chant.objects.create(source=source, folio="001r", feast=feast_1)
        Chant.objects.create(source=source, folio="001v", feast=feast_2)
        Chant.objects.create(source=source, folio="001v")
        Chant.objects.create(source=source, folio="001v", feast=feast_2)
        Chant.objects.create(source=source, folio="002r", feast=feast_1)
        response = self.client.get(reverse("chant-list", args=[source.id]))
        # context "feasts_with_folios" is a list of tuples
        # it records the folios where the feast changes
        expected_result = [("001r", feast_1), ("001v", feast_2), ("002r", feast_1)]
        self.assertEqual(response.context["feasts_with_folios"], expected_result)

    def test_redirect_with_source_parameter(self):
        cantus_segment = make_fake_segment(id=4063)
        source = make_fake_source(segment=cantus_segment)
        source_id = source.id

        url = reverse("redirect-chant-list")
        response = self.client.get(f"{url}?source={source_id}")
        self.assertRedirects(
            response, reverse("chant-list", args=[source_id]), status_code=301
        )

    def test_redirect_without_source_parameter(self):
        url = reverse("redirect-chant-list")

        # Omitting the source parameter to simulate a bad request
        response = self.client.get(url)
        self.assertEqual(response.status_code, 400)
        self.assertTemplateUsed(response, "400.html")


class ChantDetailViewTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        Group.objects.create(name="project manager")

    def test_url_and_templates(self):
        chant = make_fake_chant()
        response = self.client.get(reverse("chant-detail", args=[chant.id]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "base.html")
        self.assertTemplateUsed(response, "chant_detail.html")

    def test_context_folios(self):
        # create a source and several chants in it
        source = make_fake_source()
        chant = Chant.objects.create(source=source, folio="001r")
        Chant.objects.create(source=source, folio="001r")
        Chant.objects.create(source=source, folio="001v")
        Chant.objects.create(source=source, folio="001v")
        Chant.objects.create(source=source, folio="002r")
        Chant.objects.create(source=source, folio="002v")
        # request the page
        response = self.client.get(reverse("chant-detail", args=[chant.id]))
        # the element in "folios" should be unique and ordered in this way
        folios = response.context["folios"]
        self.assertEqual(list(folios), ["001r", "001v", "002r", "002v"])

    def test_context_previous_and_next_folio(self):
        # create a source and several chants in it
        source = make_fake_source()
        # three folios: 001r, 001v, 002r
        chant_without_previous_folio = Chant.objects.create(source=source, folio="001r")
        chant_with_previous_and_next_folio = Chant.objects.create(
            source=source, folio="001v"
        )
        chant_without_next_folio = Chant.objects.create(source=source, folio="002v")
        # request the page and check the context variables
        # for the chant on 001r, there is no previous folio, and the next folio should be 001v
        response = self.client.get(
            reverse("chant-detail", args=[chant_without_previous_folio.id])
        )
        self.assertIsNone(response.context["previous_folio"])
        self.assertEqual(response.context["next_folio"], "001v")

        # for the chant on 001v, previous folio should be 001r, and next folio should be 002v
        response = self.client.get(
            reverse("chant-detail", args=[chant_with_previous_and_next_folio.id])
        )
        self.assertEqual(response.context["previous_folio"], "001r")
        self.assertEqual(response.context["next_folio"], "002v")

        # for the chant on 002v, there is no next folio, and the previous folio should be 001v
        response = self.client.get(
            reverse("chant-detail", args=[chant_without_next_folio.id])
        )
        self.assertEqual(response.context["previous_folio"], "001v")
        self.assertIsNone(response.context["next_folio"])

    def test_published_vs_unpublished(self):
        source = make_fake_source()
        chant = make_fake_chant(source=source)

        source.published = True
        source.save()
        response = self.client.get(reverse("chant-detail", args=[chant.id]))
        self.assertEqual(response.status_code, 200)

        source.published = False
        source.save()
        response = self.client.get(reverse("chant-detail", args=[chant.id]))
        self.assertEqual(response.status_code, 403)

    def test_chant_edit_link(self):
        source = make_fake_source()
        chant = make_fake_chant(
            source=source,
            folio="001r",
            manuscript_full_text_std_spelling="manuscript_full_text_std_spelling",
        )

        # have to create project manager user - "View | Edit" toggle only visible for those with edit access for a chant's source
        self.user = get_user_model().objects.create(email="test@test.com")
        self.user.set_password("pass")
        self.user.save()
        self.client = Client()
        project_manager = Group.objects.get(name="project manager")
        project_manager.user_set.add(self.user)
        self.client.login(email="test@test.com", password="pass")

        response = self.client.get(reverse("chant-detail", args=[chant.id]))
        expected_url_fragment = (
            f"edit-chants/{source.id}?pk={chant.id}&folio={chant.folio}"
        )

        self.assertIn(expected_url_fragment, str(response.content))

    def test_chant_with_volpiano_with_no_fulltext(self):
        # in the past, a Chant Detail page will error rather than loading properly when the chant has volpiano but no fulltext
        source = make_fake_source()
        chant = make_fake_chant(
            source=source,
            volpiano="1---c--g--e---e---d---c---c---f---e---e--d---d---c",
            incipit="somebody",
        )
        chant.manuscript_full_text = None
        chant.manuscript_full_text_std_spelling = None
        chant.save()
        response = self.client.get(reverse("chant-detail", args=[chant.id]))
        self.assertEqual(response.status_code, 200)

    def test_chant_with_volpiano_with_no_incipit(self):
        # in the past, a Chant Detail page will error rather than loading properly when the chant has volpiano but no fulltext/incipit
        source = make_fake_source()
        chant = make_fake_chant(
            source=source,
            volpiano="1---g---a---g--a---g---e---c--e---|---f---g--f--g---f--d---9--d",
        )
        chant.manuscript_full_text = None
        chant.manuscript_full_text_std_spelling = None
        chant.incipit = None
        chant.save()
        response = self.client.get(reverse("chant-detail", args=[chant.id]))
        self.assertEqual(response.status_code, 200)


class ChantByCantusIDViewTest(TestCase):
    def test_url_and_templates(self):
        chant = make_fake_chant()
        response = self.client.get(
            reverse("chant-by-cantus-id", args=[chant.cantus_id])
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "base.html")
        self.assertTemplateUsed(response, "chant_seq_by_cantus_id.html")

    def test_queryset(self):
        chant = make_fake_chant()
        response = self.client.get(
            reverse("chant-by-cantus-id", args=[chant.cantus_id])
        )
        self.assertIn(chant, response.context["chants"])

    def test_published_vs_unpublished(self):
        source = make_fake_source()
        chant = make_fake_chant(source=source)

        source.published = True
        source.save()
        response_1 = self.client.get(
            reverse("chant-by-cantus-id", args=[chant.cantus_id])
        )
        self.assertIn(chant, response_1.context["chants"])

        source.published = False
        source.save()
        response_2 = self.client.get(
            reverse("chant-by-cantus-id", args=[chant.cantus_id])
        )
        self.assertNotIn(chant, response_2.context["chants"])


class ChantSearchViewTest(TestCase):
    def setUp(self):
        # unless a segment is specified when a source is created, the source is automatically assigned
        # to the segment with the name "CANTUS Database" - to prevent errors, we must make sure that
        # such a segment exists
        Segment.objects.create(name="CANTUS Database")

    def test_view_url_path(self):
        response = self.client.get("/chant-search/")
        self.assertEqual(response.status_code, 200)

    def test_url_and_templates(self):
        response = self.client.get(reverse("chant-search"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "base.html")
        self.assertTemplateUsed(response, "chant_search.html")

    def test_published_vs_unpublished(self):
        source = make_fake_source()
        chant = make_fake_chant(
            source=source, manuscript_full_text_std_spelling="lorem ipsum"
        )

        source.published = True
        source.save()
        response = self.client.get(
            reverse("chant-search"), {"keyword": "lorem", "op": "contains"}
        )
        context_chant_id = response.context["chants"][0]["id"]
        self.assertEqual(chant.id, context_chant_id)

        source.published = False
        source.save()
        response = self.client.get(
            reverse("chant-search"), {"keyword": "lorem", "op": "contains"}
        )
        self.assertEqual(len(response.context["chants"]), 0)

    def test_search_by_office(self):
        source = make_fake_source(published=True)
        office = make_fake_office()
        chant = Chant.objects.create(source=source, office=office)
        search_term = office.id
        response = self.client.get(reverse("chant-search"), {"office": search_term})
        context_chant_id = response.context["chants"][0]["id"]
        self.assertEqual(chant.id, context_chant_id)

    def test_filter_by_genre(self):
        source = make_fake_source(published=True)
        genre = make_fake_genre()
        chant = Chant.objects.create(source=source, genre=genre)
        response = self.client.get(reverse("chant-search"), {"genre": genre.id})
        context_chant_id = response.context["chants"][0]["id"]
        self.assertEqual(chant.id, context_chant_id)

    def test_search_by_cantus_id(self):
        source = make_fake_source(published=True)
        chant = Chant.objects.create(source=source, cantus_id=faker.numerify("######"))
        search_term = get_random_search_term(chant.cantus_id)
        response = self.client.get(reverse("chant-search"), {"cantus_id": search_term})
        context_chant_id = response.context["chants"][0]["id"]
        self.assertEqual(chant.id, context_chant_id)

    def test_search_by_mode(self):
        source = make_fake_source(published=True)
        chant = Chant.objects.create(source=source, mode=faker.numerify("#"))
        search_term = get_random_search_term(chant.mode)
        response = self.client.get(reverse("chant-search"), {"mode": search_term})
        context_chant_id = response.context["chants"][0]["id"]
        self.assertEqual(chant.id, context_chant_id)

    def test_search_by_feast(self):
        source = make_fake_source(published=True)
        feast = make_fake_feast()
        chant = Chant.objects.create(source=source, feast=feast)
        search_term = get_random_search_term(feast.name)
        response = self.client.get(reverse("chant-search"), {"feast": search_term})
        context_chant_id = response.context["chants"][0]["id"]
        self.assertEqual(chant.id, context_chant_id)

    def test_search_by_position(self):
        source = make_fake_source(published=True)
        position = 1
        chant = Chant.objects.create(source=source, position=position)
        search_term = "1"
        response = self.client.get(reverse("chant-search"), {"position": search_term})
        context_chant_id = response.context["chants"][0]["id"]
        self.assertEqual(chant.id, context_chant_id)

    def test_filter_by_melody(self):
        source = make_fake_source(published=True)
        chant_with_melody = Chant.objects.create(
            source=source,
            volpiano=make_fake_volpiano(),
        )
        chant_without_melody = Chant.objects.create(source=source)
        response = self.client.get(reverse("chant-search"), {"melodies": "true"})
        # only chants with melodies should be in the result
        self.assertEqual(len(response.context["chants"]), 1)
        context_chant_id = response.context["chants"][0]["id"]
        self.assertEqual(context_chant_id, chant_with_melody.id)

    def test_keyword_search_starts_with(self):
        source = make_fake_source(published=True)
        chant = Chant.objects.create(
            source=source,
            manuscript_full_text_std_spelling=faker.sentence(),
        )
        # use the beginning part of the full text as the search term
        search_term = chant.manuscript_full_text_std_spelling[
            0 : random.randint(1, len(chant.manuscript_full_text_std_spelling))
        ]
        response = self.client.get(
            reverse("chant-search"), {"keyword": search_term, "op": "starts_with"}
        )
        context_chant_id = response.context["chants"][0]["id"]
        self.assertEqual(chant.id, context_chant_id)

    def test_keyword_search_contains(self):
        source = make_fake_source(published=True)
        chant = Chant.objects.create(
            source=source,
            manuscript_full_text="hoc tantum possum dicere",
        )
        search_term = "tantum possum"
        response = self.client.get(
            reverse("chant-search"), {"keyword": search_term, "op": "contains"}
        )
        context_chant_id = response.context["chants"][0]["id"]
        self.assertEqual(chant.id, context_chant_id)

    def test_search_bar_search(self):
        # note to developers: if you are changing the behavior of search_bar
        # searches, be sure to check static/js/chant_search.js to see if it needs
        # updating (among other things, this script populates the search fields on
        # the Chant Search page if a user arrives via the Global Search Bar)
        chant_with_incipit_only = make_fake_chant(
            manuscript_full_text="The first three*", cantus_id="987654"
        )
        chant_with_full_text = make_fake_chant(
            manuscript_full_text="The entire text is present for this one",
            cantus_id="098765",
        )
        chant_with_ascending_cantus_id = make_fake_chant(
            manuscript_full_text="Full text contains, but does not start with 'the'",
            cantus_id="123456",
        )
        chant_starting_with_a_number = make_fake_chant(
            manuscript_full_text=(
                "1 is a number. " "How unusual, to find an arabic numeral in a chant!"
            ),
            cantus_id="234567",
        )

        # if the search term contains no numerals, we should be doing an incipit
        # search. Non-letter, non-numeral characters like "*" should not cause
        # a switch to searching by Cantus ID
        full_incipit_search_term = "the first three*"
        response_1 = self.client.get(
            reverse("chant-search"), {"search_bar": full_incipit_search_term}
        )
        context_chants_1 = response_1.context["chants"]
        self.assertEqual(len(context_chants_1), 1)
        context_chant_1_id = context_chants_1[0]["id"]
        self.assertEqual(context_chant_1_id, chant_with_incipit_only.id)

        short_incipit_search_term = "the"
        response_2 = self.client.get(
            reverse("chant-search"), {"search_bar": short_incipit_search_term}
        )
        context_chants_2 = response_2.context["chants"]
        self.assertEqual(len(context_chants_2), 2)
        context_chants_2_ids = context_chants_2[0]["id"], context_chants_2[1]["id"]
        self.assertIn(chant_with_incipit_only.id, context_chants_2_ids)
        self.assertIn(chant_with_full_text.id, context_chants_2_ids)
        self.assertNotIn(chant_with_ascending_cantus_id.id, context_chants_2_ids)

        # if the search term contains even a single numeral, we should be doing
        # a Cantus ID search
        numeric_search_term = "1"
        response_3 = self.client.get(
            reverse("chant-search"), {"search_bar": numeric_search_term}
        )
        context_chants_3 = response_3.context["chants"]
        self.assertEqual(len(context_chants_3), 1)
        context_chant_3_id = context_chants_3[0]["id"]
        self.assertEqual(context_chant_3_id, chant_with_ascending_cantus_id.id)

        letters_and_numbers_search_term = "1 is"
        response_4 = self.client.get(
            reverse("chant-search"), {"search_bar": letters_and_numbers_search_term}
        )
        context_chants_4 = response_4.context["chants"]
        self.assertEqual(len(context_chants_4), 0)

    def test_order_by_siglum(self):
        source_1 = make_fake_source(published=True, siglum="sigl-1")
        chant_1 = make_fake_chant(
            manuscript_full_text_std_spelling="thing 1", source=source_1
        )
        source_2 = make_fake_source(published=True, siglum="sigl-2")
        chant_2 = make_fake_chant(
            manuscript_full_text_std_spelling="thing 2", source=source_2
        )
        chant_1.refresh_from_db()
        chant_2.refresh_from_db()  # incipit is automatically calculated from fulltext
        # on chant save; refreshing from DB allows us to compare the value to what we see in
        # the results.

        search_term = "thing"

        response_ascending = self.client.get(
            reverse("chant-search"),
            {
                "keyword": search_term,
                "op": "contains",
                "order": "siglum",
                "sort": "asc",
            },
        )
        ascending_results = response_ascending.context["chants"]
        first_result_incipit = ascending_results[0]["incipit"]
        self.assertEqual(first_result_incipit, chant_1.incipit)
        last_result_incipit = ascending_results[1]["incipit"]
        self.assertEqual(last_result_incipit, chant_2.incipit)

        response_descending = self.client.get(
            reverse("chant-search"),
            {
                "keyword": search_term,
                "op": "contains",
                "order": "siglum",
                "sort": "desc",
            },
        )
        descending_results = response_descending.context["chants"]
        first_result_incipit = descending_results[0]["incipit"]
        self.assertEqual(first_result_incipit, chant_2.incipit)
        last_result_incipit = descending_results[1]["incipit"]
        self.assertEqual(last_result_incipit, chant_1.incipit)

    def test_order_by_incipit(self):
        source = make_fake_source(published=True)
        chant_1 = make_fake_chant(
            source=source, manuscript_full_text_std_spelling="higgledy"
        )
        chant_2 = make_fake_chant(
            source=source, manuscript_full_text_std_spelling="piggledy"
        )
        chant_1.refresh_from_db()
        chant_2.refresh_from_db()  # incipit is automatically calculated from fulltext
        # on chant save; refreshing from DB allows us to compare the value to what we see in
        # the results.

        search_term = "iggl"

        response_ascending = self.client.get(
            reverse("chant-search"),
            {
                "keyword": search_term,
                "op": "contains",
                "order": "incipit",
                "sort": "asc",
            },
        )
        ascending_results = response_ascending.context["chants"]
        first_result_incipit = ascending_results[0]["incipit"]
        self.assertEqual(first_result_incipit, chant_1.incipit)
        last_result_incipit = ascending_results[1]["incipit"]
        self.assertEqual(last_result_incipit, chant_2.incipit)

        response_descending = self.client.get(
            reverse("chant-search"),
            {
                "keyword": search_term,
                "op": "contains",
                "order": "incipit",
                "sort": "desc",
            },
        )
        descending_results = response_descending.context["chants"]
        first_result_incipit = descending_results[0]["incipit"]
        self.assertEqual(first_result_incipit, chant_2.incipit)
        last_result_incipit = descending_results[1]["incipit"]
        self.assertEqual(last_result_incipit, chant_1.incipit)

    def test_order_by_office(self):
        # currently, office sort works by ID rather than by name
        office_1 = make_fake_office()
        office_2 = make_fake_office()
        assert office_1.id < office_2.id
        chant_1 = make_fake_chant(
            office=office_1, manuscript_full_text_std_spelling="hocus"
        )
        chant_2 = make_fake_chant(
            office=office_2, manuscript_full_text_std_spelling="pocus"
        )
        chant_1.refresh_from_db()
        chant_2.refresh_from_db()  # incipit is automatically calculated from fulltext
        # on chant save; refreshing from DB allows us to compare the value to what we see in
        # the results.

        search_term = "ocu"

        response_ascending = self.client.get(
            reverse("chant-search"),
            {
                "keyword": search_term,
                "op": "contains",
                "order": "office",
                "sort": "asc",
            },
        )
        ascending_results = response_ascending.context["chants"]
        first_result_incipit = ascending_results[0]["incipit"]
        self.assertEqual(first_result_incipit, chant_1.incipit)
        last_result_incipit = ascending_results[1]["incipit"]
        self.assertEqual(last_result_incipit, chant_2.incipit)

        response_descending = self.client.get(
            reverse("chant-search"),
            {
                "keyword": search_term,
                "op": "contains",
                "order": "office",
                "sort": "desc",
            },
        )
        descending_results = response_descending.context["chants"]
        first_result_incipit = descending_results[0]["incipit"]
        self.assertEqual(first_result_incipit, chant_2.incipit)
        last_result_incipit = descending_results[1]["incipit"]
        self.assertEqual(last_result_incipit, chant_1.incipit)

    def test_order_by_genre(self):
        # currently, genre sort works by ID rather than by name
        genre_1 = make_fake_genre()
        genre_2 = make_fake_genre()
        assert genre_1.id < genre_2.id
        chant_1 = make_fake_chant(genre=genre_1, incipit="hocus")
        chant_2 = make_fake_chant(genre=genre_2, incipit="pocus")

        search_term = "ocu"

        response_ascending = self.client.get(
            reverse("chant-search"),
            {
                "keyword": search_term,
                "op": "contains",
                "order": "genre",
                "sort": "asc",
            },
        )
        ascending_results = response_ascending.context["chants"]
        first_result_incipit = ascending_results[0]["incipit"]
        self.assertEqual(first_result_incipit, chant_1.incipit)
        last_result_incipit = ascending_results[1]["incipit"]
        self.assertEqual(last_result_incipit, chant_2.incipit)

        response_descending = self.client.get(
            reverse("chant-search"),
            {
                "keyword": search_term,
                "op": "contains",
                "order": "genre",
                "sort": "desc",
            },
        )
        descending_results = response_descending.context["chants"]
        first_result_incipit = descending_results[0]["incipit"]
        self.assertEqual(first_result_incipit, chant_2.incipit)
        last_result_incipit = descending_results[1]["incipit"]
        self.assertEqual(last_result_incipit, chant_1.incipit)

    def test_order_by_cantus_id(self):
        chant_1 = make_fake_chant(incipit="isaac", cantus_id="121393")
        chant_2 = make_fake_chant(incipit="baal", cantus_id="196418")

        search_term = "aa"

        response_ascending = self.client.get(
            reverse("chant-search"),
            {
                "keyword": search_term,
                "op": "contains",
                "order": "cantus_id",
                "sort": "asc",
            },
        )
        ascending_results = response_ascending.context["chants"]
        first_result_incipit = ascending_results[0]["incipit"]
        self.assertEqual(first_result_incipit, chant_1.incipit)
        last_result_incipit = ascending_results[1]["incipit"]
        self.assertEqual(last_result_incipit, chant_2.incipit)

        response_descending = self.client.get(
            reverse("chant-search"),
            {
                "keyword": search_term,
                "op": "contains",
                "order": "cantus_id",
                "sort": "desc",
            },
        )
        descending_results = response_descending.context["chants"]
        first_result_incipit = descending_results[0]["incipit"]
        self.assertEqual(first_result_incipit, chant_2.incipit)
        last_result_incipit = descending_results[1]["incipit"]
        self.assertEqual(last_result_incipit, chant_1.incipit)

    def test_order_by_mode(self):
        chant_1 = make_fake_chant(
            manuscript_full_text_std_spelling="For first he looks upon his forepaws to see if they are clean",
            mode="1",
        )
        chant_2 = make_fake_chant(
            manuscript_full_text_std_spelling="For secondly he kicks up behind to clear away there",
            mode="2",
        )
        chant_1.refresh_from_db()
        chant_2.refresh_from_db()  # incipit is automatically calculated from fulltext
        # on chant save; refreshing from DB allows us to compare the value to what we see in
        # the results.

        search_term = "for"

        response_ascending = self.client.get(
            reverse("chant-search"),
            {
                "keyword": search_term,
                "op": "contains",
                "order": "mode",
                "sort": "asc",
            },
        )
        ascending_results = response_ascending.context["chants"]
        first_result_incipit = ascending_results[0]["incipit"]
        self.assertEqual(first_result_incipit, chant_1.incipit)
        last_result_incipit = ascending_results[1]["incipit"]
        self.assertEqual(last_result_incipit, chant_2.incipit)

        response_descending = self.client.get(
            reverse("chant-search"),
            {
                "keyword": search_term,
                "op": "contains",
                "order": "mode",
                "sort": "desc",
            },
        )
        descending_results = response_descending.context["chants"]
        first_result_incipit = descending_results[0]["incipit"]
        self.assertEqual(first_result_incipit, chant_2.incipit)
        last_result_incipit = descending_results[1]["incipit"]
        self.assertEqual(last_result_incipit, chant_1.incipit)

    def test_order_by_ms_fulltext(self):
        chant_1 = make_fake_chant(
            manuscript_full_text="this is a chant with a MS spelling fylltexte",
            manuscript_full_text_std_spelling="this is a chant with a MS spelling fulltext",
        )
        chant_2 = make_fake_chant(
            manuscript_full_text_std_spelling="this is a chant without a MS spelling fulltext",
        )
        chant_2.manuscript_full_text = None
        chant_2.save()
        chant_1.refresh_from_db()
        chant_2.refresh_from_db()  # incipit is automatically calculated from fulltext
        # on chant save; refreshing from DB allows us to compare the value to what we see in
        # the results.

        search_term = "s is a ch"

        response_ascending = self.client.get(
            reverse("chant-search"),
            {
                "keyword": search_term,
                "op": "contains",
                "order": "has_fulltext",
                "sort": "asc",
            },
        )
        ascending_results = response_ascending.context["chants"]
        first_result_incipit = ascending_results[0]["incipit"]
        self.assertEqual(first_result_incipit, chant_1.incipit)
        last_result_incipit = ascending_results[1]["incipit"]
        self.assertEqual(last_result_incipit, chant_2.incipit)

        response_descending = self.client.get(
            reverse("chant-search"),
            {
                "keyword": search_term,
                "op": "contains",
                "order": "has_fulltext",
                "sort": "desc",
            },
        )
        descending_results = response_descending.context["chants"]
        first_result_incipit = descending_results[0]["incipit"]
        self.assertEqual(first_result_incipit, chant_2.incipit)
        last_result_incipit = descending_results[1]["incipit"]
        self.assertEqual(last_result_incipit, chant_1.incipit)

    def test_order_by_volpiano(self):
        chant_1 = make_fake_chant(
            manuscript_full_text_std_spelling="this is a chant with volpiano",
            volpiano="1---d---d---a--a---a---e--f--e---d---4",
        )
        chant_2 = make_fake_chant(
            manuscript_full_text_std_spelling="this is a chant about parsley",
        )
        chant_2.volpiano = None
        chant_2.save()
        chant_1.refresh_from_db()
        chant_2.refresh_from_db()  # incipit is automatically calculated from fulltext
        # on chant save; refreshing from DB allows us to compare the value to what we see in
        # the results.

        search_term = "s is a ch"

        response_ascending = self.client.get(
            reverse("chant-search"),
            {
                "keyword": search_term,
                "op": "contains",
                "order": "has_melody",
                "sort": "asc",
            },
        )
        ascending_results = response_ascending.context["chants"]
        first_result_incipit = ascending_results[0]["incipit"]
        self.assertEqual(first_result_incipit, chant_1.incipit)
        last_result_incipit = ascending_results[1]["incipit"]
        self.assertEqual(last_result_incipit, chant_2.incipit)

        response_descending = self.client.get(
            reverse("chant-search"),
            {
                "keyword": search_term,
                "op": "contains",
                "order": "has_melody",
                "sort": "desc",
            },
        )
        descending_results = response_descending.context["chants"]
        first_result_incipit = descending_results[0]["incipit"]
        self.assertEqual(first_result_incipit, chant_2.incipit)
        last_result_incipit = descending_results[1]["incipit"]
        self.assertEqual(last_result_incipit, chant_1.incipit)

    def test_order_by_image_link(self):
        chant_1 = make_fake_chant(
            incipit="this is a chant with a link",
            image_link="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        )
        chant_2 = make_fake_chant(
            incipit="this is a chant without",
        )
        chant_2.image_link = None
        chant_2.save()

        search_term = "a chant with"

        response_ascending = self.client.get(
            reverse("chant-search"),
            {
                "keyword": search_term,
                "op": "contains",
                "order": "has_image",
                "sort": "asc",
            },
        )
        ascending_results = response_ascending.context["chants"]
        first_result_incipit = ascending_results[0]["incipit"]
        self.assertEqual(first_result_incipit, chant_1.incipit)
        last_result_incipit = ascending_results[1]["incipit"]
        self.assertEqual(last_result_incipit, chant_2.incipit)

        response_descending = self.client.get(
            reverse("chant-search"),
            {
                "keyword": search_term,
                "op": "contains",
                "order": "has_image",
                "sort": "desc",
            },
        )
        descending_results = response_descending.context["chants"]
        first_result_incipit = descending_results[0]["incipit"]
        self.assertEqual(first_result_incipit, chant_2.incipit)
        last_result_incipit = descending_results[1]["incipit"]
        self.assertEqual(last_result_incipit, chant_1.incipit)

    def test_column_header_links(self):
        # these are the 9 column headers users can order by:
        siglum = "glum-01"
        incipit = "so it begins"
        office = make_fake_office()
        genre = make_fake_genre()
        cantus_id = make_random_string(6, "0123456789")
        mode = make_random_string(1, "0123456789*?")
        ms_ft = faker.sentence()
        mel = make_fake_volpiano()
        image = faker.image_url()

        source = make_fake_source(siglum=siglum, published=True)

        # additional properties for which there are search fields
        feast = make_fake_feast()
        position = make_random_string(1)
        chant = make_fake_chant(
            incipit=incipit,
            office=office,
            genre=genre,
            cantus_id=cantus_id,
            mode=mode,
            manuscript_full_text_std_spelling=ms_ft,
            volpiano=mel,
            image_link=image,
            source=source,
            feast=feast,
            position=position,
        )
        search_term = "so it be"

        response_1 = self.client.get(
            reverse("chant-search"),
            {
                "keyword": search_term,
            },
        )
        html_1 = str(response_1.content)
        # if no ordering specified, all 9 links should include "&sort=asc"
        self.assertEqual(html_1.count("&sort=asc"), 9)

        # test that all query parameters are present in all 9 links
        query_keys_and_values = {
            "op": "contains",
            "keyword": search_term,
            "office": office.id,
            "genre": genre.id,
            "cantus_id": cantus_id,
            "mode": mode,
            "feast": feast.name,
            "position": position,
            "melodies": "true",
        }
        response_2 = self.client.get(
            reverse("chant-search"),
            query_keys_and_values,
        )
        html_2 = str(response_2.content)
        for k, v in query_keys_and_values.items():
            expected_query_param = f"{k}={v}"
            self.assertEqual(html_2.count(expected_query_param), 9)
        self.assertEqual(html_2.count("sort=asc"), 9)

        # test links maintain search_bar
        response_3 = self.client.get(
            reverse("chant-search"),
            {
                "search_bar": search_term,
            },
        )
        html_3 = str(response_3.content)
        self.assertEqual(html_3.count(f"search_bar={search_term}"), 9)

        # for each orderable column, check that 'asc' flips to 'desc', and vice versa
        orderings = (
            "siglum",
            "incipit",
            "office",
            "genre",
            "cantus_id",
            "mode",
            "has_fulltext",
            "has_melody",
            "has_image",
        )
        for ordering in orderings:
            response_asc = self.client.get(
                reverse("chant-search"),
                {
                    "search_bar": search_term,
                    "order": ordering,
                    "sort": "asc",
                },
            )
            html_asc = str(response_asc.content)
            # the expected substring should be found in the `href` attribute of the `a` tag
            # in the column header in question. Since the results are currently being ordered
            # by that column, sorted ascending, this link should switch the results to being
            # sorted descending.
            expected_substring = f"&order={ordering}&sort=desc"
            self.assertIn(expected_substring, html_asc)
            # when no `sort=` is specified, all 9 columns should contain a `sort=asc` in
            # their column header link. Since an ascending sorting _is_ specified for one
            # of the columns, that column should have switched from `sort=asc` to `sort=desc`
            self.assertEqual(html_asc.count("sort=asc"), 8)
            response_desc = self.client.get(
                reverse("chant-search"),
                {
                    "search_bar": search_term,
                    "order": ordering,
                    "sort": "desc",
                },
            )
            response_desc = self.client.get(
                reverse("chant-search"),
                {
                    "search_bar": search_term,
                    "order": ordering,
                    "sort": "desc",
                },
            )
            html_desc = str(response_desc.content)
            # the expected substring should be found in the `href` attribute of the `a` tag
            # in the column header in question. Since the results are currently being ordered
            # by that column, sorted descending, this link should switch the results to being
            # sorted ascending.
            expected_substring = f"&order={ordering}&sort=asc"
            self.assertIn(expected_substring, html_desc)

    def test_source_link_column(self):
        siglum = "Sigl-01"
        source = make_fake_source(published=True, siglum=siglum)
        source_title = source.title
        url = source.get_absolute_url()
        fulltext = "manuscript full text"
        search_term = "full"
        chant = make_fake_chant(
            source=source, manuscript_full_text_std_spelling=fulltext
        )
        response = self.client.get(
            reverse("chant-search"), {"keyword": search_term, "op": "contains"}
        )
        html = str(response.content)
        self.assertIn(siglum, html)
        self.assertIn(source_title, html)
        self.assertIn(url, html)
        self.assertIn(f'<a href="{url}" title="{source_title}">{siglum}</a>', html)

    def test_folio_column(self):
        source = make_fake_source(published=True)
        fulltext = "manuscript full text"
        search_term = "full"
        chant = make_fake_chant(
            source=source, manuscript_full_text_std_spelling=fulltext
        )
        folio = chant.folio
        response = self.client.get(
            reverse("chant-search"), {"keyword": search_term, "op": "contains"}
        )
        html = str(response.content)
        self.assertIn(folio, html)

    def test_feast_column(self):
        source = make_fake_source(published=True)
        feast = make_fake_feast()
        feast_name = feast.name
        feast_description = feast.description
        url = feast.get_absolute_url()
        fulltext = "manuscript full text"
        search_term = "full"
        chant = make_fake_chant(
            source=source,
            manuscript_full_text_std_spelling=fulltext,
            feast=feast,
        )
        response = self.client.get(
            reverse("chant-search"), {"keyword": search_term, "op": "contains"}
        )
        html = str(response.content)
        self.assertIn(feast_name, html)
        self.assertIn(feast_description, html)
        self.assertIn(url, html)
        self.assertIn(
            f'<a href="{url}" title="{feast_description}">{feast_name}</a>', html
        )

    def test_office_column(self):
        source = make_fake_source(published=True)
        office = make_fake_office()
        office_name = office.name
        office_description = office.description
        url = office.get_absolute_url()
        fulltext = "manuscript full text"
        search_term = "full"
        chant = make_fake_chant(
            source=source,
            manuscript_full_text_std_spelling=fulltext,
            office=office,
        )
        response = self.client.get(
            reverse("chant-search"), {"keyword": search_term, "op": "contains"}
        )
        html = str(response.content)
        self.assertIn(office_name, html)
        self.assertIn(office_description, html)
        self.assertIn(url, html)
        self.assertIn(
            f'<a href="{url}" title="{office_description}">{office_name}</a>', html
        )

    def test_genre_column(self):
        source = make_fake_source(published=True)
        genre = make_fake_genre()
        genre_name = genre.name
        genre_description = genre.description
        url = genre.get_absolute_url()
        fulltext = "manuscript full text"
        search_term = "full"
        chant = make_fake_chant(
            source=source,
            manuscript_full_text_std_spelling=fulltext,
            genre=genre,
        )
        response = self.client.get(
            reverse("chant-search"), {"keyword": search_term, "op": "contains"}
        )
        html = str(response.content)
        self.assertIn(genre_name, html)
        self.assertIn(genre_description, html)
        self.assertIn(url, html)
        self.assertIn(
            f'<a href="{url}" title="{genre_description}">{genre_name}</a>', html
        )

    def test_position_column(self):
        source = make_fake_source(published=True)
        fulltext = "manuscript full text"
        search_term = "full"
        chant = make_fake_chant(
            source=source,
            manuscript_full_text_std_spelling=fulltext,
        )
        position = chant.position
        response = self.client.get(
            reverse("chant-search"), {"keyword": search_term, "op": "contains"}
        )
        html = str(response.content)
        self.assertIn(position, html)

    def test_cantus_id_column(self):
        source = make_fake_source(published=True)
        fulltext = "manuscript full text"
        search_term = "full"
        chant = make_fake_chant(
            source=source,
            manuscript_full_text_std_spelling=fulltext,
        )
        cantus_id = chant.cantus_id
        url = chant.get_ci_url()
        response = self.client.get(
            reverse("chant-search"), {"keyword": search_term, "op": "contains"}
        )
        html = str(response.content)
        self.assertIn(cantus_id, html)
        self.assertIn(url, html)
        self.assertIn(f'<a href="{url}" target="_blank">{cantus_id}</a>', html)

    def test_mode_column(self):
        source = make_fake_source(published=True)
        fulltext = "manuscript full text"
        search_term = "full"
        chant = make_fake_chant(
            source=source,
            manuscript_full_text_std_spelling=fulltext,
        )
        mode = "this is the mode"  # not a representative value, but
        # single numerals are found elsewhere in the template
        chant.mode = mode
        chant.save()
        response = self.client.get(
            reverse("chant-search"), {"keyword": search_term, "op": "contains"}
        )
        html = str(response.content)
        self.assertIn(mode, html)

    def test_manuscript_full_text_column(self):
        source = make_fake_source(published=True)
        std_fulltext = "standard full text"
        ms_fulltext = "manuscript full text"
        search_term = "full"
        chant = make_fake_chant(
            source=source,
            manuscript_full_text_std_spelling=std_fulltext,
            manuscript_full_text=ms_fulltext,
        )
        response = self.client.get(
            reverse("chant-search"), {"keyword": search_term, "op": "contains"}
        )
        html = str(response.content)
        self.assertIn(
            "\\xe2\\x9c\\x94",  # checkmark character
            html,
        )
        self.assertIn(
            '<span title="Chant record includes Manuscript Full Text">\\xe2\\x9c\\x94</span>',
            html,
        )

        chant.manuscript_full_text = None
        chant.save()
        response = self.client.get(
            reverse("chant-search"), {"keyword": search_term, "op": "contains"}
        )
        html = str(response.content)
        self.assertNotIn(
            "\\xe2\\x9c\\x94",  # checkmark character
            html,
        )

    def test_volpiano_column(self):
        source = make_fake_source(published=True)
        full_text = "standard full text"
        search_term = "full"
        volpiano = "1---h--j---k--h---m---m---l"
        chant = make_fake_chant(
            source=source,
            manuscript_full_text_std_spelling=full_text,
            volpiano=volpiano,
        )
        response = self.client.get(
            reverse("chant-search"), {"keyword": search_term, "op": "contains"}
        )
        html = str(response.content)
        self.assertIn(
            "\\xe2\\x99\\xab",  # beamed eighth notes character
            html,
        )
        self.assertIn(
            '<span title="Chant record has Volpiano melody">\\xe2\\x99\\xab</span>',
            html,
        )
        chant.volpiano = None
        chant.save()
        response = self.client.get(
            reverse("chant-search"), {"keyword": search_term, "op": "contains"}
        )
        html = str(response.content)
        self.assertNotIn(
            "\\xe2\\x99\\xab",  # beamed eighth notes character
            html,
        )

    def test_image_link_column(self):
        source = make_fake_source(published=True)
        fulltext = "standard full text"
        search_term = "full"
        chant = make_fake_chant(
            source=source,
            manuscript_full_text_std_spelling=fulltext,
        )
        image_link = "http://www.example.com/image_link"
        chant.image_link = image_link
        chant.save()
        response = self.client.get(
            reverse("chant-search"), {"keyword": search_term, "op": "contains"}
        )
        html = str(response.content)
        self.assertIn(image_link, html)
        self.assertIn(f'<a href="{image_link}" target="_blank">Image</a>', html)


class ChantSearchMSViewTest(TestCase):
    def test_url_and_templates(self):
        source = make_fake_source()
        response = self.client.get(reverse("chant-search-ms", args=[source.id]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "base.html")
        self.assertTemplateUsed(response, "chant_search.html")

    def test_published_vs_unpublished(self):
        source = make_fake_source()

        source.published = True
        source.save()
        response = self.client.get(reverse("chant-search-ms", args=[source.id]))
        self.assertEqual(response.status_code, 200)

        source.published = False
        source.save()
        response = self.client.get(reverse("chant-search-ms", args=[source.id]))
        self.assertEqual(response.status_code, 403)

    def test_search_by_office(self):
        source = make_fake_source()
        office = make_fake_office()
        chant = Chant.objects.create(source=source, office=office)
        search_term = office.id
        response = self.client.get(
            reverse("chant-search-ms", args=[source.id]), {"office": search_term}
        )
        context_chant_id = response.context["chants"][0]["id"]
        self.assertEqual(chant.id, context_chant_id)

    def test_filter_by_genre(self):
        source = make_fake_source()
        genre = make_fake_genre()
        chant = Chant.objects.create(source=source, genre=genre)
        response = self.client.get(
            reverse("chant-search-ms", args=[source.id]), {"genre": genre.id}
        )
        context_chant_id = response.context["chants"][0]["id"]
        self.assertEqual(chant.id, context_chant_id)

    def test_search_by_cantus_id(self):
        source = make_fake_source()
        chant = Chant.objects.create(source=source, cantus_id=faker.numerify("######"))
        search_term = get_random_search_term(chant.cantus_id)
        response = self.client.get(
            reverse("chant-search-ms", args=[source.id]), {"cantus_id": search_term}
        )
        context_chant_id = response.context["chants"][0]["id"]
        self.assertEqual(chant.id, context_chant_id)

    def test_search_by_mode(self):
        source = make_fake_source()
        chant = Chant.objects.create(source=source, mode=faker.numerify("#"))
        search_term = get_random_search_term(chant.mode)
        response = self.client.get(
            reverse("chant-search-ms", args=[source.id]), {"mode": search_term}
        )
        context_chant_id = response.context["chants"][0]["id"]
        self.assertEqual(chant.id, context_chant_id)

    def test_search_by_feast(self):
        source = make_fake_source()
        feast = make_fake_feast()
        chant = Chant.objects.create(source=source, feast=feast)
        search_term = get_random_search_term(feast.name)
        response = self.client.get(
            reverse("chant-search-ms", args=[source.id]), {"feast": search_term}
        )
        context_chant_id = response.context["chants"][0]["id"]
        self.assertEqual(chant.id, context_chant_id)

    def test_search_by_position(self):
        source = make_fake_source(published=True)
        position = 1
        chant = Chant.objects.create(source=source, position=position)
        search_term = "1"
        response = self.client.get(
            reverse("chant-search-ms", args=[source.id]), {"position": search_term}
        )
        context_chant_id = response.context["chants"][0]["id"]
        self.assertEqual(chant.id, context_chant_id)

    def test_filter_by_melody(self):
        source = make_fake_source()
        chant_with_melody = Chant.objects.create(
            source=source,
            volpiano=make_fake_volpiano,
        )
        chant_without_melody = Chant.objects.create(source=source)
        response = self.client.get(
            reverse("chant-search-ms", args=[source.id]), {"melodies": "true"}
        )
        # only chants with melodies should be in the result
        self.assertEqual(len(response.context["chants"]), 1)
        context_chant_id = response.context["chants"][0]["id"]
        self.assertEqual(context_chant_id, chant_with_melody.id)

    def test_keyword_search_starts_with(self):
        source = make_fake_source()
        search_term = "quick"

        # We have three chants to make sure the result is only chant 1 where quick is the first word
        chant_1 = make_fake_chant(
            source=source,
            manuscript_full_text_std_spelling="quick brown fox jumps over the lazy dog",
        )
        chant_2 = make_fake_chant(
            source=source,
            manuscript_full_text_std_spelling="brown fox jumps over the lazy dog",
        )
        chant_3 = make_fake_chant(
            source=source,
            manuscript_full_text_std_spelling="lazy brown fox jumps quick over the dog",
        )
        response = self.client.get(
            reverse("chant-search-ms", args=[source.id]),
            {"keyword": search_term, "op": "starts_with"},
        )
        self.assertEqual(len(response.context["chants"]), 1)
        context_chant_id = response.context["chants"][0]["id"]
        self.assertEqual(chant_1.id, context_chant_id)

    def test_keyword_search_contains(self):
        source = make_fake_source()
        search_term = "quick"
        chant_1 = make_fake_chant(
            source=source,
            manuscript_full_text_std_spelling="Quick brown fox jumps over the lazy dog",
        )
        chant_2 = make_fake_chant(
            source=source,
            manuscript_full_text_std_spelling="brown fox jumps over the lazy dog",
        )
        chant_3 = make_fake_chant(
            source=source,
            manuscript_full_text_std_spelling="lazy brown fox jumps quickly over the dog",
        )
        response = self.client.get(
            reverse("chant-search-ms", args=[source.id]),
            {"keyword": search_term, "op": "contains"},
        )
        first_context_chant_id = response.context["chants"][0]["id"]
        self.assertEqual(chant_1.id, first_context_chant_id)
        second_context_chant_id = response.context["chants"][1]["id"]
        self.assertEqual(chant_3.id, second_context_chant_id)

    def test_keyword_search_searching_all_fields(self):
        search_term = "brevity"
        includes_search_term = "brevity is the soul of wit"
        doesnt_include_search_term = "longevity is the soul of wit"
        source = make_fake_source()
        chant_incipit = make_fake_chant(
            source=source,
            incipit=includes_search_term,  # <==
            manuscript_full_text=doesnt_include_search_term,
            manuscript_full_text_std_spelling=doesnt_include_search_term,
        )
        chant_ms_spelling = make_fake_chant(
            source=source,
            incipit=doesnt_include_search_term,
            manuscript_full_text=includes_search_term,  # <==
            manuscript_full_text_std_spelling=doesnt_include_search_term,
        )
        chant_std_spelling = make_fake_chant(
            source=source,
            incipit=doesnt_include_search_term,
            manuscript_full_text=doesnt_include_search_term,
            manuscript_full_text_std_spelling=includes_search_term,  # <==
        )
        chant_without_search_term = make_fake_chant(
            source=source,
            incipit=doesnt_include_search_term,
            manuscript_full_text=doesnt_include_search_term,
            manuscript_full_text_std_spelling=doesnt_include_search_term,
        )
        response_starts_with = self.client.get(
            reverse("chant-search-ms", args=[source.id]),
            {"keyword": search_term, "op": "starts_with"},
        )
        self.assertEqual(len(response_starts_with.context["chants"]), 3)
        response_contains = self.client.get(
            reverse("chant-search-ms", args=[source.id]),
            {"keyword": search_term, "op": "contains"},
        )
        self.assertEqual(len(response_contains.context["chants"]), 3)

    def test_order_by_incipit(self):
        source = make_fake_source(published=True)
        chant_1 = make_fake_chant(source=source, incipit="higgledy")
        chant_2 = make_fake_chant(source=source, incipit="piggledy")

        search_term = "iggl"

        response_ascending = self.client.get(
            reverse("chant-search-ms", args=[source.id]),
            {
                "keyword": search_term,
                "op": "contains",
                "order": "incipit",
                "sort": "asc",
            },
        )
        ascending_results = response_ascending.context["chants"]
        first_result_incipit = ascending_results[0]["incipit"]
        self.assertEqual(first_result_incipit, chant_1.incipit)
        last_result_incipit = ascending_results[1]["incipit"]
        self.assertEqual(last_result_incipit, chant_2.incipit)

        response_descending = self.client.get(
            reverse("chant-search-ms", args=[source.id]),
            {
                "keyword": search_term,
                "op": "contains",
                "order": "incipit",
                "sort": "desc",
            },
        )
        descending_results = response_descending.context["chants"]
        first_result_incipit = descending_results[0]["incipit"]
        self.assertEqual(first_result_incipit, chant_2.incipit)
        last_result_incipit = descending_results[1]["incipit"]
        self.assertEqual(last_result_incipit, chant_1.incipit)

    def test_order_by_office(self):
        source = make_fake_source()
        # currently, office sort works by ID rather than by name
        office_1 = make_fake_office()
        office_2 = make_fake_office()
        assert office_1.id < office_2.id
        chant_1 = make_fake_chant(office=office_1, incipit="hocus", source=source)
        chant_2 = make_fake_chant(office=office_2, incipit="pocus", source=source)

        search_term = "ocu"

        response_ascending = self.client.get(
            reverse("chant-search-ms", args=[source.id]),
            {
                "keyword": search_term,
                "op": "contains",
                "order": "office",
                "sort": "asc",
            },
        )
        ascending_results = response_ascending.context["chants"]
        first_result_incipit = ascending_results[0]["incipit"]
        self.assertEqual(first_result_incipit, chant_1.incipit)
        last_result_incipit = ascending_results[1]["incipit"]
        self.assertEqual(last_result_incipit, chant_2.incipit)

        response_descending = self.client.get(
            reverse("chant-search-ms", args=[source.id]),
            {
                "keyword": search_term,
                "op": "contains",
                "order": "office",
                "sort": "desc",
            },
        )
        descending_results = response_descending.context["chants"]
        first_result_incipit = descending_results[0]["incipit"]
        self.assertEqual(first_result_incipit, chant_2.incipit)
        last_result_incipit = descending_results[1]["incipit"]
        self.assertEqual(last_result_incipit, chant_1.incipit)

    def test_order_by_genre(self):
        source = make_fake_source()
        # currently, genre sort works by ID rather than by name
        genre_1 = make_fake_genre()
        genre_2 = make_fake_genre()
        assert genre_1.id < genre_2.id
        chant_1 = make_fake_chant(genre=genre_1, incipit="hocus", source=source)
        chant_2 = make_fake_chant(genre=genre_2, incipit="pocus", source=source)

        search_term = "ocu"

        response_ascending = self.client.get(
            reverse("chant-search-ms", args=[source.id]),
            {
                "keyword": search_term,
                "op": "contains",
                "order": "genre",
                "sort": "asc",
            },
        )
        ascending_results = response_ascending.context["chants"]
        first_result_incipit = ascending_results[0]["incipit"]
        self.assertEqual(first_result_incipit, chant_1.incipit)
        last_result_incipit = ascending_results[1]["incipit"]
        self.assertEqual(last_result_incipit, chant_2.incipit)

        response_descending = self.client.get(
            reverse("chant-search-ms", args=[source.id]),
            {
                "keyword": search_term,
                "op": "contains",
                "order": "genre",
                "sort": "desc",
            },
        )
        descending_results = response_descending.context["chants"]
        first_result_incipit = descending_results[0]["incipit"]
        self.assertEqual(first_result_incipit, chant_2.incipit)
        last_result_incipit = descending_results[1]["incipit"]
        self.assertEqual(last_result_incipit, chant_1.incipit)

    def test_order_by_cantus_id(self):
        source = make_fake_source()
        chant_1 = make_fake_chant(incipit="isaac", cantus_id="121393", source=source)
        chant_2 = make_fake_chant(incipit="baal", cantus_id="196418", source=source)

        search_term = "aa"

        response_ascending = self.client.get(
            reverse("chant-search-ms", args=[source.id]),
            {
                "keyword": search_term,
                "op": "contains",
                "order": "cantus_id",
                "sort": "asc",
            },
        )
        ascending_results = response_ascending.context["chants"]
        first_result_incipit = ascending_results[0]["incipit"]
        self.assertEqual(first_result_incipit, chant_1.incipit)
        last_result_incipit = ascending_results[1]["incipit"]
        self.assertEqual(last_result_incipit, chant_2.incipit)

        response_descending = self.client.get(
            reverse("chant-search-ms", args=[source.id]),
            {
                "keyword": search_term,
                "op": "contains",
                "order": "cantus_id",
                "sort": "desc",
            },
        )
        descending_results = response_descending.context["chants"]
        first_result_incipit = descending_results[0]["incipit"]
        self.assertEqual(first_result_incipit, chant_2.incipit)
        last_result_incipit = descending_results[1]["incipit"]
        self.assertEqual(last_result_incipit, chant_1.incipit)

    def test_order_by_mode(self):
        source = make_fake_source()
        chant_1 = make_fake_chant(
            incipit="For thirdly he works it upon stretch with the forepaws extended",
            mode="1",
            source=source,
        )
        chant_2 = make_fake_chant(
            incipit="For fourthly he sharpens his paws by wood",
            mode="2",
            source=source,
        )

        search_term = "for"

        response_ascending = self.client.get(
            reverse("chant-search-ms", args=[source.id]),
            {
                "keyword": search_term,
                "op": "contains",
                "order": "mode",
                "sort": "asc",
            },
        )
        ascending_results = response_ascending.context["chants"]
        first_result_incipit = ascending_results[0]["incipit"]
        self.assertEqual(first_result_incipit, chant_1.incipit)
        last_result_incipit = ascending_results[1]["incipit"]
        self.assertEqual(last_result_incipit, chant_2.incipit)

        response_descending = self.client.get(
            reverse("chant-search-ms", args=[source.id]),
            {
                "keyword": search_term,
                "op": "contains",
                "order": "mode",
                "sort": "desc",
            },
        )
        descending_results = response_descending.context["chants"]
        first_result_incipit = descending_results[0]["incipit"]
        self.assertEqual(first_result_incipit, chant_2.incipit)
        last_result_incipit = descending_results[1]["incipit"]
        self.assertEqual(last_result_incipit, chant_1.incipit)

    def test_order_by_ms_fulltext(self):
        source = make_fake_source()
        chant_1 = make_fake_chant(
            incipit="this is a chant with a MS spelling fulltext",
            manuscript_full_text="this is a chant with a MS spelling fylltexte",
            source=source,
        )
        chant_2 = make_fake_chant(
            incipit="this is a chant without",
            source=source,
        )
        chant_2.manuscript_full_text = None
        chant_2.save()

        search_term = "s is a ch"

        response_ascending = self.client.get(
            reverse("chant-search-ms", args=[source.id]),
            {
                "keyword": search_term,
                "op": "contains",
                "order": "has_fulltext",
                "sort": "asc",
            },
        )
        ascending_results = response_ascending.context["chants"]
        first_result_incipit = ascending_results[0]["incipit"]
        self.assertEqual(first_result_incipit, chant_1.incipit)
        last_result_incipit = ascending_results[1]["incipit"]
        self.assertEqual(last_result_incipit, chant_2.incipit)

        response_descending = self.client.get(
            reverse("chant-search-ms", args=[source.id]),
            {
                "keyword": search_term,
                "op": "contains",
                "order": "has_fulltext",
                "sort": "desc",
            },
        )
        descending_results = response_descending.context["chants"]
        first_result_incipit = descending_results[0]["incipit"]
        self.assertEqual(first_result_incipit, chant_2.incipit)
        last_result_incipit = descending_results[1]["incipit"]
        self.assertEqual(last_result_incipit, chant_1.incipit)

    def test_order_by_volpiano(self):
        source = make_fake_source()
        chant_1 = make_fake_chant(
            source=source,
            incipit="this is a chant with volpiano",
            volpiano="1---d---d---a--a---a---e--f--e---d---4",
        )
        chant_2 = make_fake_chant(
            source=source,
            incipit="this is a chant about parsley",
        )
        chant_2.volpiano = None
        chant_2.save()

        search_term = "s is a ch"

        response_ascending = self.client.get(
            reverse("chant-search-ms", args=[source.id]),
            {
                "keyword": search_term,
                "op": "contains",
                "order": "has_melody",
                "sort": "asc",
            },
        )
        ascending_results = response_ascending.context["chants"]
        first_result_incipit = ascending_results[0]["incipit"]
        self.assertEqual(first_result_incipit, chant_1.incipit)
        last_result_incipit = ascending_results[1]["incipit"]
        self.assertEqual(last_result_incipit, chant_2.incipit)

        response_descending = self.client.get(
            reverse("chant-search-ms", args=[source.id]),
            {
                "keyword": search_term,
                "op": "contains",
                "order": "has_melody",
                "sort": "desc",
            },
        )
        descending_results = response_descending.context["chants"]
        first_result_incipit = descending_results[0]["incipit"]
        self.assertEqual(first_result_incipit, chant_2.incipit)
        last_result_incipit = descending_results[1]["incipit"]
        self.assertEqual(last_result_incipit, chant_1.incipit)

    def test_order_by_image_link(self):
        source = make_fake_source()
        chant_1 = make_fake_chant(
            source=source,
            incipit="this is a chant with a link",
            image_link="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        )
        chant_2 = make_fake_chant(
            source=source,
            incipit="this is a chant without",
        )
        chant_2.image_link = None
        chant_2.save()

        search_term = "a chant with"

        response_ascending = self.client.get(
            reverse("chant-search"),
            {
                "keyword": search_term,
                "op": "contains",
                "order": "has_image",
                "sort": "asc",
            },
        )
        ascending_results = response_ascending.context["chants"]
        first_result_incipit = ascending_results[0]["incipit"]
        self.assertEqual(first_result_incipit, chant_1.incipit)
        last_result_incipit = ascending_results[1]["incipit"]
        self.assertEqual(last_result_incipit, chant_2.incipit)

        response_descending = self.client.get(
            reverse("chant-search"),
            {
                "keyword": search_term,
                "op": "contains",
                "order": "has_image",
                "sort": "desc",
            },
        )
        descending_results = response_descending.context["chants"]
        first_result_incipit = descending_results[0]["incipit"]
        self.assertEqual(first_result_incipit, chant_2.incipit)
        last_result_incipit = descending_results[1]["incipit"]
        self.assertEqual(last_result_incipit, chant_1.incipit)

    def test_column_header_links(self):
        # these are the 9 column headers users can order by:
        siglum = "glum-01"
        incipit = "so it begins"
        office = make_fake_office()
        genre = make_fake_genre()
        cantus_id = make_random_string(6, "0123456789")
        mode = make_random_string(1, "0123456789*?")
        ms_ft = faker.sentence()
        mel = make_fake_volpiano()
        image = faker.image_url()

        source = make_fake_source(siglum=siglum, published=True)

        # additional properties for which there are search fields
        feast = make_fake_feast()
        position = make_random_string(1)
        chant = make_fake_chant(
            incipit=incipit,
            office=office,
            genre=genre,
            cantus_id=cantus_id,
            mode=mode,
            manuscript_full_text_std_spelling=ms_ft,
            volpiano=mel,
            image_link=image,
            source=source,
            feast=feast,
            position=position,
        )
        search_term = "so it be"

        response_1 = self.client.get(
            reverse("chant-search-ms", args=[source.id]),
            {
                "keyword": search_term,
            },
        )
        html_1 = str(response_1.content)
        # if no ordering specified, all 9 links should include "&sort=asc"
        self.assertEqual(html_1.count("&sort=asc"), 9)

        # test that all query parameters are present in all 9 links
        query_keys_and_values = {
            "op": "contains",
            "keyword": search_term,
            "office": office.id,
            "genre": genre.id,
            "cantus_id": cantus_id,
            "mode": mode,
            "feast": feast.name,
            "position": position,
            "melodies": "true",
        }
        response_2 = self.client.get(
            reverse("chant-search-ms", args=[source.id]),
            query_keys_and_values,
        )
        html_2 = str(response_2.content)
        for k, v in query_keys_and_values.items():
            expected_query_param = f"{k}={v}"
            self.assertEqual(html_2.count(expected_query_param), 9)
            self.assertEqual(html_2.count("sort=asc"), 9)

        # for each orderable column, check that 'asc' flips to 'desc', and vice versa
        orderings = (
            "siglum",
            "incipit",
            "office",
            "genre",
            "cantus_id",
            "mode",
            "has_fulltext",
            "has_melody",
            "has_image",
        )
        for ordering in orderings:
            response_asc = self.client.get(
                reverse("chant-search-ms", args=[source.id]),
                {
                    "search_bar": search_term,
                    "order": ordering,
                    "sort": "asc",
                },
            )
            html_asc = str(response_asc.content)
            # the expected substring should be found in the `href` attribute of the `a` tag
            # in the column header in question. Since the results are currently being ordered
            # by that column, sorted ascending, this link should switch the results to being
            # sorted descending.
            expected_substring = f"&order={ordering}&sort=desc"
            self.assertIn(expected_substring, html_asc)
            # when no `sort=` is specified, all 9 columns should contain a `sort=asc` in
            # their column header link. Since an ascending sorting _is_ specified for one
            # of the columns, that column should have switched from `sort=asc` to `sort=desc`
            self.assertEqual(html_asc.count("sort=asc"), 8)
            response_desc = self.client.get(
                reverse("chant-search-ms", args=[source.id]),
                {
                    "search_bar": search_term,
                    "order": ordering,
                    "sort": "desc",
                },
            )
            response_desc = self.client.get(
                reverse("chant-search-ms", args=[source.id]),
                {
                    "search_bar": search_term,
                    "order": ordering,
                    "sort": "desc",
                },
            )
            html_desc = str(response_desc.content)
            # the expected substring should be found in the `href` attribute of the `a` tag
            # in the column header in question. Since the results are currently being ordered
            # by that column, sorted descending, this link should switch the results to being
            # sorted ascending.
            expected_substring = f"&order={ordering}&sort=asc"
            self.assertIn(expected_substring, html_desc)

    def test_source_link_column(self):
        siglum = "Sigl-01"
        source = make_fake_source(published=True, siglum=siglum)
        source_title = source.title
        url = source.get_absolute_url()
        fulltext = "manuscript full text"
        search_term = "full"
        chant = make_fake_chant(
            source=source, manuscript_full_text_std_spelling=fulltext
        )
        response = self.client.get(
            reverse("chant-search-ms", args=[source.id]),
            {"keyword": search_term, "op": "contains"},
        )
        html = str(response.content)
        self.assertIn(siglum, html)
        self.assertIn(source_title, html)
        self.assertIn(url, html)
        self.assertIn(f'<a href="{url}" title="{source_title}">{siglum}</a>', html)

    def test_folio_column(self):
        source = make_fake_source(published=True)
        fulltext = "manuscript full text"
        search_term = "full"
        chant = make_fake_chant(
            source=source, manuscript_full_text_std_spelling=fulltext
        )
        folio = chant.folio
        response = self.client.get(
            reverse("chant-search-ms", args=[source.id]),
            {"keyword": search_term, "op": "contains"},
        )
        html = str(response.content)
        self.assertIn(folio, html)

    def test_feast_column(self):
        source = make_fake_source(published=True)
        feast = make_fake_feast()
        feast_name = feast.name
        feast_description = feast.description
        url = feast.get_absolute_url()
        fulltext = "manuscript full text"
        search_term = "full"
        chant = make_fake_chant(
            source=source,
            manuscript_full_text_std_spelling=fulltext,
            feast=feast,
        )
        response = self.client.get(
            reverse("chant-search-ms", args=[source.id]),
            {"keyword": search_term, "op": "contains"},
        )
        html = str(response.content)
        self.assertIn(feast_name, html)
        self.assertIn(feast_description, html)
        self.assertIn(url, html)
        self.assertIn(
            f'<a href="{url}" title="{feast_description}">{feast_name}</a>', html
        )

    def test_office_column(self):
        source = make_fake_source(published=True)
        office = make_fake_office()
        office_name = office.name
        office_description = office.description
        url = office.get_absolute_url()
        fulltext = "manuscript full text"
        search_term = "full"
        chant = make_fake_chant(
            source=source,
            manuscript_full_text_std_spelling=fulltext,
            office=office,
        )
        response = self.client.get(
            reverse("chant-search-ms", args=[source.id]),
            {"keyword": search_term, "op": "contains"},
        )
        html = str(response.content)
        self.assertIn(office_name, html)
        self.assertIn(office_description, html)
        self.assertIn(url, html)
        self.assertIn(
            f'<a href="{url}" title="{office_description}">{office_name}</a>', html
        )

    def test_genre_column(self):
        source = make_fake_source(published=True)
        genre = make_fake_genre()
        genre_name = genre.name
        genre_description = genre.description
        url = genre.get_absolute_url()
        fulltext = "manuscript full text"
        search_term = "full"
        chant = make_fake_chant(
            source=source,
            manuscript_full_text_std_spelling=fulltext,
            genre=genre,
        )
        response = self.client.get(
            reverse("chant-search-ms", args=[source.id]),
            {"keyword": search_term, "op": "contains"},
        )
        html = str(response.content)
        self.assertIn(genre_name, html)
        self.assertIn(genre_description, html)
        self.assertIn(url, html)
        self.assertIn(
            f'<a href="{url}" title="{genre_description}">{genre_name}</a>', html
        )

    def test_position_column(self):
        source = make_fake_source(published=True)
        fulltext = "manuscript full text"
        search_term = "full"
        chant = make_fake_chant(
            source=source,
            manuscript_full_text_std_spelling=fulltext,
        )
        position = chant.position
        response = self.client.get(
            reverse("chant-search-ms", args=[source.id]),
            {"keyword": search_term, "op": "contains"},
        )
        html = str(response.content)
        self.assertIn(position, html)

    def test_cantus_id_column(self):
        source = make_fake_source(published=True)
        fulltext = "manuscript full text"
        search_term = "full"
        chant = make_fake_chant(
            source=source,
            manuscript_full_text_std_spelling=fulltext,
        )
        cantus_id = chant.cantus_id
        url = chant.get_ci_url()
        response = self.client.get(
            reverse("chant-search-ms", args=[source.id]),
            {"keyword": search_term, "op": "contains"},
        )
        html = str(response.content)
        self.assertIn(cantus_id, html)
        self.assertIn(url, html)
        self.assertIn(f'<a href="{url}" target="_blank">{cantus_id}</a>', html)

    def test_mode_column(self):
        source = make_fake_source(published=True)
        fulltext = "manuscript full text"
        search_term = "full"
        chant = make_fake_chant(
            source=source,
            manuscript_full_text_std_spelling=fulltext,
        )
        mode = "this is the mode"  # not a representative value, but
        # single numerals are found elsewhere in the template
        chant.mode = mode
        chant.save()
        response = self.client.get(
            reverse("chant-search-ms", args=[source.id]),
            {"keyword": search_term, "op": "contains"},
        )
        html = str(response.content)
        self.assertIn(mode, html)

    def test_manuscript_full_text_column(self):
        source = make_fake_source(published=True)
        std_fulltext = "standard full text"
        ms_fulltext = "manuscript full text"
        search_term = "full"
        chant = make_fake_chant(
            source=source,
            manuscript_full_text_std_spelling=std_fulltext,
            manuscript_full_text=ms_fulltext,
        )
        response = self.client.get(
            reverse("chant-search-ms", args=[source.id]),
            {"keyword": search_term, "op": "contains"},
        )
        html = str(response.content)
        self.assertIn(
            "\\xe2\\x9c\\x94",  # checkmark character
            html,
        )
        self.assertIn(
            '<span title="Chant record includes Manuscript Full Text">\\xe2\\x9c\\x94</span>',
            html,
        )

        chant.manuscript_full_text = None
        chant.save()
        response = self.client.get(
            reverse("chant-search-ms", args=[source.id]),
            {"keyword": search_term, "op": "contains"},
        )
        html = str(response.content)
        self.assertNotIn(
            "\\xe2\\x9c\\x94",  # checkmark character
            html,
        )

    def test_volpiano_column(self):
        source = make_fake_source(published=True)
        full_text = "standard full text"
        search_term = "full"
        volpiano = "1---defg-e-cd"
        chant = make_fake_chant(
            source=source,
            manuscript_full_text_std_spelling=full_text,
            volpiano=volpiano,
        )
        response = self.client.get(
            reverse("chant-search-ms", args=[source.id]),
            {"keyword": search_term, "op": "contains"},
        )
        html = str(response.content)
        self.assertIn(
            "\\xe2\\x99\\xab",  # beamed eighth notes character
            html,
        )
        self.assertIn(
            '<span title="Chant record has Volpiano melody">\\xe2\\x99\\xab</span>',
            html,
        )
        chant.volpiano = None
        chant.save()
        response = self.client.get(
            reverse("chant-search-ms", args=[source.id]),
            {"keyword": search_term, "op": "contains"},
        )
        html = str(response.content)
        self.assertNotIn(
            "\\xe2\\x99\\xab",  # beamed eighth notes character
            html,
        )

    def test_image_link_column(self):
        source = make_fake_source(published=True)
        fulltext = "standard full text"
        search_term = "full"
        chant = make_fake_chant(
            source=source,
            manuscript_full_text_std_spelling=fulltext,
        )
        image_link = "http://www.example.com/image_link"
        chant.image_link = image_link
        chant.save()
        response = self.client.get(
            reverse("chant-search-ms", args=[source.id]),
            {"keyword": search_term, "op": "contains"},
        )
        html = str(response.content)
        self.assertIn(image_link, html)
        self.assertIn(f'<a href="{image_link}" target="_blank">Image</a>', html)


class ChantCreateViewTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        Group.objects.create(name="project manager")

    def setUp(self):
        self.user = get_user_model().objects.create(email="test@test.com")
        self.user.set_password("pass")
        self.user.save()
        self.client = Client()
        project_manager = Group.objects.get(name="project manager")
        project_manager.user_set.add(self.user)
        self.client.login(email="test@test.com", password="pass")

    def test_url_and_templates(self):
        source = make_fake_source()

        response = self.client.get(reverse("chant-create", args=[source.id]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "chant_create.html")

        response = self.client.get(reverse("chant-create", args=[source.id + 100]))
        self.assertEqual(response.status_code, 404)
        self.assertTemplateUsed(response, "404.html")

    def test_create_chant(self):
        source = make_fake_source()
        response = self.client.post(
            reverse("chant-create", args=[source.id]),
            {
                "manuscript_full_text_std_spelling": "initial",
                "folio": "001r",
                "c_sequence": "1",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse("chant-create", args=[source.id]))
        chant = Chant.objects.first()
        self.assertEqual(chant.manuscript_full_text_std_spelling, "initial")

    def test_view_url_path(self):
        source = make_fake_source()
        response = self.client.get(f"/chant-create/{source.id}")
        self.assertEqual(response.status_code, 200)

    def test_context(self):
        """some context variable passed to templates"""
        source = make_fake_source()
        url = reverse("chant-create", args=[source.id])
        response = self.client.get(url)
        self.assertEqual(response.context["source"].title, source.title)

    def test_post_error(self):
        """post with correct source and empty full-text"""
        source = make_fake_source()
        url = reverse("chant-create", args=[source.id])
        response = self.client.post(url, data={"manuscript_full_text_std_spelling": ""})
        self.assertFormError(
            response,
            "form",
            "manuscript_full_text_std_spelling",
            "This field is required.",
        )

    def test_nonexistent_source(self):
        """
        users should not be able to access Chant Create page for a source that doesn't exist
        """
        nonexistent_source_id: str = faker.numerify(
            "#####"
        )  # there's not supposed to be 5-digits source id
        response = self.client.get(
            reverse("chant-create", args=[nonexistent_source_id])
        )
        self.assertEqual(response.status_code, 404)

    def test_repeated_seq(self):
        """post with a folio and seq that already exists in the source"""
        TEST_FOLIO = "001r"
        # create some chants in the test source
        source = make_fake_source()
        for i in range(1, 5):
            Chant.objects.create(
                source=source,
                manuscript_full_text=faker.text(10),
                folio=TEST_FOLIO,
                c_sequence=i,
            )
        # post a chant with the same folio and seq
        url = reverse("chant-create", args=[source.id])
        fake_text = faker.text(10)
        response = self.client.post(
            url,
            data={
                "manuscript_full_text_std_spelling": fake_text,
                "folio": TEST_FOLIO,
                "c_sequence": random.randint(1, 4),
            },
            follow=True,
        )
        self.assertFormError(
            response,
            "form",
            None,
            errors="Chant with the same sequence and folio already exists in this source.",
        )

    def test_view_url_reverse_name(self):
        fake_sources = [make_fake_source() for _ in range(10)]
        for source in fake_sources:
            response = self.client.get(reverse("chant-create", args=[source.id]))
            self.assertEqual(response.status_code, 200)

    def test_template_used(self):
        fake_sources = [make_fake_source() for _ in range(10)]
        for source in fake_sources:
            response = self.client.get(reverse("chant-create", args=[source.id]))
            self.assertEqual(response.status_code, 200)
            self.assertTemplateUsed(response, "base.html")
            self.assertTemplateUsed(response, "chant_create.html")

    def test_volpiano_signal(self):
        source = make_fake_source()
        self.client.post(
            reverse("chant-create", args=[source.id]),
            {
                "manuscript_full_text_std_spelling": "ut queant lactose",
                "folio": "001r",
                "c_sequence": "1",
                # liquescents, to be converted to lowercase
                #                    vv v v v v v v
                "volpiano": "9abcdefg)A-B1C2D3E4F5G67?. yiz"
                #                      ^ ^ ^ ^ ^ ^ ^^^^^^^^
                # clefs, accidentals, etc., to be deleted
            },
        )
        chant_1 = Chant.objects.get(
            manuscript_full_text_std_spelling="ut queant lactose"
        )
        self.assertEqual(chant_1.volpiano, "9abcdefg)A-B1C2D3E4F5G67?. yiz")
        self.assertEqual(chant_1.volpiano_notes, "9abcdefg9abcdefg")
        self.client.post(
            reverse("chant-create", args=[source.id]),
            {
                "manuscript_full_text_std_spelling": "resonare foobaz",
                "folio": "001r",
                "c_sequence": "2",
                "volpiano": "abacadaeafagahaja",
            },
        )
        chant_2 = Chant.objects.get(manuscript_full_text_std_spelling="resonare foobaz")
        self.assertEqual(chant_2.volpiano, "abacadaeafagahaja")
        self.assertEqual(chant_2.volpiano_intervals, "1-12-23-34-45-56-67-78-8")


class ChantDeleteViewTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        Group.objects.create(name="project manager")

    def setUp(self):
        self.user = get_user_model().objects.create(email="test@test.com")
        self.user.set_password("pass")
        self.user.save()
        self.client = Client()
        project_manager = Group.objects.get(name="project manager")
        project_manager.user_set.add(self.user)
        self.client.login(email="test@test.com", password="pass")

    def test_context(self):
        chant = make_fake_chant()
        response = self.client.get(reverse("chant-delete", args=[chant.id]))
        self.assertEqual(chant, response.context["object"])

    def test_url_and_templates(self):
        chant = make_fake_chant()

        response = self.client.get(reverse("chant-delete", args=[chant.id]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "chant_confirm_delete.html")

        response = self.client.get(reverse("chant-delete", args=[chant.id + 100]))
        self.assertEqual(response.status_code, 404)
        self.assertTemplateUsed(response, "404.html")

    def test_existing_chant(self):
        chant = make_fake_chant()
        response = self.client.post(reverse("chant-delete", args=[chant.id]))
        self.assertEqual(response.status_code, 302)

    def test_non_existing_chant(self):
        chant = make_fake_chant()
        response = self.client.post(reverse("chant-delete", args=[chant.id + 100]))
        self.assertEqual(response.status_code, 404)


class SourceEditChantsViewTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        Group.objects.create(name="project manager")

    def setUp(self):
        self.user = get_user_model().objects.create(email="test@test.com")
        self.user.set_password("pass")
        self.user.save()
        self.client = Client()
        project_manager = Group.objects.get(name="project manager")
        project_manager.user_set.add(self.user)
        self.client.login(email="test@test.com", password="pass")

    def test_url_and_templates(self):
        source1 = make_fake_source()

        # must specify folio, or SourceEditChantsView.get_queryset will fail when it tries to default to displaying the first folio
        Chant.objects.create(source=source1, folio="001r")

        response = self.client.get(reverse("source-edit-chants", args=[source1.id]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "chant_edit.html")

        response = self.client.get(
            reverse("source-edit-chants", args=[source1.id + 100])
        )
        self.assertEqual(response.status_code, 404)
        self.assertTemplateUsed(response, "404.html")

        # trying to access chant-edit with a source that has no chant should return 200
        source2 = make_fake_source()

        response = self.client.get(reverse("source-edit-chants", args=[source2.id]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "chant_edit.html")

    def test_update_chant(self):
        source = make_fake_source()
        chant = make_fake_chant(
            source=source, manuscript_full_text_std_spelling="initial"
        )

        response = self.client.get(
            reverse("source-edit-chants", args=[source.id]), {"pk": chant.id}
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "chant_edit.html")

        folio = chant.folio
        c_sequence = chant.c_sequence
        response = self.client.post(
            reverse("source-edit-chants", args=[source.id]),
            {
                "manuscript_full_text_std_spelling": "test",
                "pk": chant.id,
                "folio": folio,
                "c_sequence": c_sequence,
            },
        )
        self.assertEqual(response.status_code, 302)
        # Check that after the edit, the user is redirected to the source-edit-chants page
        self.assertRedirects(response, reverse("source-edit-chants", args=[source.id]))
        chant.refresh_from_db()
        self.assertEqual(chant.manuscript_full_text_std_spelling, "test")

    def test_volpiano_signal(self):
        source = make_fake_source()
        chant_1 = make_fake_chant(
            manuscript_full_text_std_spelling="ut queant lactose",
            source=source,
            folio="001r",
            c_sequence=1,
        )
        self.client.post(
            reverse("source-edit-chants", args=[source.id]),
            {
                "manuscript_full_text_std_spelling": "ut queant lactose",
                "folio": "001r",
                "c_sequence": "1",
                # liquescents, to be converted to lowercase
                #                    vv v v v v v v
                "volpiano": "9abcdefg)A-B1C2D3E4F5G67?. yiz"
                #                      ^ ^ ^ ^ ^ ^ ^^^^^^^^
                # clefs, accidentals, etc., to be deleted
            },
        )
        chant_1 = Chant.objects.get(
            manuscript_full_text_std_spelling="ut queant lactose"
        )
        self.assertEqual(chant_1.volpiano, "9abcdefg)A-B1C2D3E4F5G67?. yiz")
        self.assertEqual(chant_1.volpiano_notes, "9abcdefg9abcdefg")

        make_fake_chant(
            manuscript_full_text_std_spelling="resonare foobaz",
            source=source,
            folio="001r",
            c_sequence=2,
        )
        self.client.post(
            reverse("source-edit-chants", args=[source.id]),
            {
                "manuscript_full_text_std_spelling": "resonare foobaz",
                "folio": "001r",
                "c_sequence": "2",
                "volpiano": "abacadaeafagahaja",
            },
        )
        chant_2 = Chant.objects.get(manuscript_full_text_std_spelling="resonare foobaz")
        self.assertEqual(chant_2.volpiano, "abacadaeafagahaja")
        self.assertEqual(chant_2.volpiano_intervals, "1-12-23-34-45-56-67-78-8")

    def test_chant_with_volpiano_with_no_fulltext(self):
        # in the past, a Chant Edit page will error rather than loading properly when the chant has volpiano but no fulltext
        source = make_fake_source()
        chant = make_fake_chant(source=source, volpiano="1---f--e---f--d---e--c---d--d")
        chant.manuscript_full_text = None
        chant.manuscript_full_text_std_spelling = None
        chant.save()
        response = self.client.get(
            reverse("source-edit-chants", args=[source.id]), {"pk": chant.id}
        )
        self.assertEqual(response.status_code, 200)

    def test_chant_with_volpiano_with_no_incipit(self):
        # in the past, a Chant Edit page will error rather than loading properly when the chant has volpiano but no fulltext/incipit
        source = make_fake_source()
        chant = make_fake_chant(
            source=source,
            volpiano="1---d---da--g--f--e---e-eg--fed---d-nmn-mn---d",
        )
        chant.manuscript_full_text = None
        chant.manuscript_full_text_std_spelling = None
        chant.incipit = None
        chant.save()
        response = self.client.get(
            reverse("source-edit-chants", args=[source.id]), {"pk": chant.id}
        )
        self.assertEqual(response.status_code, 200)

    def test_proofread_chant(self):
        chant = make_fake_chant(
            manuscript_full_text_std_spelling="lorem ipsum", folio="001r"
        )
        folio = chant.folio
        c_sequence = chant.c_sequence
        ms_std = chant.manuscript_full_text_std_spelling
        self.assertIs(chant.manuscript_full_text_std_proofread, False)
        source = chant.source
        response = self.client.post(
            reverse("source-edit-chants", args=[source.id]),
            {
                "manuscript_full_text_std_proofread": "True",
                "folio": folio,
                "c_sequence": c_sequence,
                "manuscript_full_text_std_spelling": ms_std,
            },
        )
        self.assertEqual(response.status_code, 302)  # 302 Found
        chant.refresh_from_db()
        self.assertIs(chant.manuscript_full_text_std_proofread, True)


class ChantEditSyllabificationViewTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        Group.objects.create(name="project manager")

    def setUp(self):
        self.user = get_user_model().objects.create(email="test@test.com")
        self.user.set_password("pass")
        self.user.save()
        self.client = Client()
        project_manager = Group.objects.get(name="project manager")
        project_manager.user_set.add(self.user)
        self.client.login(email="test@test.com", password="pass")

    def test_view_url_and_templates(self):
        chant = make_fake_chant()
        chant_id = chant.id

        response_1 = self.client.get(f"/edit-syllabification/{chant_id}")
        self.assertEqual(response_1.status_code, 200)
        self.assertTemplateUsed(response_1, "base.html")
        self.assertTemplateUsed(response_1, "chant_syllabification_edit.html")

        response_2 = self.client.get(
            reverse("source-edit-syllabification", args=[chant_id])
        )
        self.assertEqual(response_2.status_code, 200)

        self.client.logout()
        response_3 = self.client.get(
            reverse("source-edit-syllabification", args=[chant_id])
        )
        self.assertEqual(response_3.status_code, 302)  # 302: redirect to login page

    def test_edit_syllabification(self):
        chant = make_fake_chant(manuscript_syllabized_full_text="lorem ipsum")
        self.assertIs(chant.manuscript_syllabized_full_text, "lorem ipsum")
        response = self.client.post(
            f"/edit-syllabification/{chant.id}",
            {"manuscript_syllabized_full_text": "lo-rem ip-sum"},
        )
        self.assertEqual(response.status_code, 302)  # 302 Found
        chant.refresh_from_db()
        self.assertEqual(chant.manuscript_syllabized_full_text, "lo-rem ip-sum")


class FeastListViewTest(TestCase):
    def test_view_url_path(self):
        response = self.client.get("/feasts/")
        self.assertEqual(response.status_code, 200)

    def test_view_url_reverse_name(self):
        response = self.client.get(reverse("feast-list"))
        self.assertEqual(response.status_code, 200)

    def test_url_and_templates(self):
        """Test the url and templates used"""
        response = self.client.get(reverse("feast-list"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "base.html")
        self.assertTemplateUsed(response, "feast_list.html")

    def test_filter_by_month(self):
        for i in range(1, 13):
            Feast.objects.create(name=f"test_feast{i}", month=i)
        for i in range(1, 13):
            month = str(i)
            response = self.client.get(reverse("feast-list"), {"month": month})
            self.assertEqual(response.status_code, 200)
            feasts = response.context["feasts"]
            self.assertTrue(all(feast.month == i for feast in feasts))

    def test_ordering(self):
        """Feast can be ordered by name or feast_code"""
        # Order by feast_code
        response = self.client.get(reverse("feast-list"), {"sort_by": "feast_code"})
        self.assertEqual(response.status_code, 200)
        feasts = response.context["feasts"]
        self.assertEqual(feasts.query.order_by[0], "feast_code")

        # Order by name
        response = self.client.get(reverse("feast-list"), {"sort_by": "name"})
        self.assertEqual(response.status_code, 200)
        feasts = response.context["feasts"]
        self.assertEqual(feasts.query.order_by[0], Lower("name"))

        # Empty ordering parameters in GET request should default to ordering by name
        response = self.client.get(reverse("feast-list"), {"sort_by": ""})
        self.assertEqual(response.status_code, 200)
        feasts = response.context["feasts"]
        self.assertEqual(feasts.query.order_by[0], Lower("name"))

        # Anything other than name and feast_code should default to ordering by name
        response = self.client.get(
            reverse("feast-list"), {"sort_by": make_random_string(4)}
        )
        self.assertEqual(response.status_code, 200)
        feasts = response.context["feasts"]
        self.assertEqual(feasts.query.order_by[0], Lower("name"))

    def test_search_name(self):
        """Feast can be searched by any part of its name, description, or feast_code"""
        feast = make_fake_feast()
        target = feast.name
        search_term = get_random_search_term(target)
        response = self.client.get(reverse("feast-list"), {"q": search_term})
        self.assertEqual(response.status_code, 200)
        self.assertIn(feast, response.context["feasts"])

    def test_search_description(self):
        feast = make_fake_feast()
        target = feast.description
        search_term = get_random_search_term(target)
        response = self.client.get(reverse("feast-list"), {"q": search_term})
        self.assertEqual(response.status_code, 200)
        self.assertIn(feast, response.context["feasts"])

    def test_search_feast_code(self):
        feast = make_fake_feast()
        target = feast.feast_code
        search_term = get_random_search_term(target)
        response = self.client.get(reverse("feast-list"), {"q": search_term})
        self.assertEqual(response.status_code, 200)
        self.assertIn(feast, response.context["feasts"])

    def test_pagination(self):
        PAGINATE_BY = FeastListView.paginate_by
        # test 2 full pages of feasts
        feast_count = PAGINATE_BY * 2
        for i in range(feast_count):
            make_fake_feast()
        page_count = int(feast_count / PAGINATE_BY)
        assert page_count == 2
        for page_num in range(1, page_count + 1):
            response = self.client.get(reverse("feast-list"), {"page": page_num})
            self.assertEqual(response.status_code, 200)
            self.assertTrue("is_paginated" in response.context)
            self.assertTrue(response.context["is_paginated"])
            self.assertEqual(len(response.context["feasts"]), PAGINATE_BY)

        # test a little more than 2 full pages of feasts
        new_feast_count = feast_count + random.randint(1, PAGINATE_BY - 1)
        for i in range(new_feast_count - feast_count):
            make_fake_feast()
        new_page_count = page_count + 1
        # The last page should have the same number of feasts as we added
        response = self.client.get(reverse("feast-list"), {"page": new_page_count})
        self.assertEqual(response.status_code, 200)
        self.assertTrue("is_paginated" in response.context)
        self.assertTrue(response.context["is_paginated"])
        self.assertEqual(len(response.context["feasts"]), new_feast_count - feast_count)

        # test the "last" syntax
        response = self.client.get(reverse("feast-list"), {"page": "last"})
        self.assertEqual(response.status_code, 200)

        # Test some invalid values for pages
        response = self.client.get(reverse("feast-list"), {"page": -1})
        self.assertEqual(response.status_code, 404)
        response = self.client.get(reverse("feast-list"), {"page": 0})
        self.assertEqual(response.status_code, 404)
        response = self.client.get(reverse("feast-list"), {"page": "lst"})
        self.assertEqual(response.status_code, 404)
        response = self.client.get(reverse("feast-list"), {"page": new_page_count + 1})
        self.assertEqual(response.status_code, 404)


class FeastDetailViewTest(TestCase):
    def setUp(self):
        # unless a segment is specified when a source is created, the source is automatically assigned
        # to the segment with the name "CANTUS Database" - to prevent errors, we must make sure that
        # such a segment exists
        Segment.objects.create(name="CANTUS Database")

    def test_url_and_templates(self):
        """Test the url and templates used"""
        feast = make_fake_feast()
        response = self.client.get(reverse("feast-detail", args=[feast.id]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "base.html")
        self.assertTemplateUsed(response, "feast_detail.html")

    def test_context(self):
        feast = make_fake_feast()
        response = self.client.get(reverse("feast-detail", args=[feast.id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(feast, response.context["feast"])

    def test_most_frequent_chants(self):
        source = make_fake_source(published=True, title="published_source")
        feast = make_fake_feast()
        # 3 chants with cantus id: 300000
        for i in range(3):
            Chant.objects.create(feast=feast, cantus_id="300000", source=source)
        # 2 chants with cantus id: 200000
        for i in range(2):
            Chant.objects.create(feast=feast, cantus_id="200000", source=source)
        # 1 chant with cantus id: 100000
        Chant.objects.create(feast=feast, cantus_id="100000", source=source)

        response = self.client.get(reverse("feast-detail", args=[feast.id]))
        frequent_chants_zip = response.context["frequent_chants_zip"]
        # the items in zip should be ordered by chant count
        # the first field is cantus id
        self.assertEqual(frequent_chants_zip[0][0], "300000")
        self.assertEqual(frequent_chants_zip[1][0], "200000")
        self.assertEqual(frequent_chants_zip[2][0], "100000")
        # the last field is cantus count
        self.assertEqual(frequent_chants_zip[0][-1], 3)
        self.assertEqual(frequent_chants_zip[1][-1], 2)
        self.assertEqual(frequent_chants_zip[2][-1], 1)

    def test_chants_in_feast_published_vs_unpublished(self):
        feast = make_fake_feast()
        source = make_fake_source()
        chant = make_fake_chant(source=source, feast=feast)

        source.published = True
        source.save()
        response_1 = self.client.get(reverse("feast-detail", args=[feast.id]))
        frequent_chants_zip = response_1.context["frequent_chants_zip"]
        cantus_ids = [x[0] for x in frequent_chants_zip]
        self.assertIn(chant.cantus_id, cantus_ids)

        source.published = False
        source.save()
        response_1 = self.client.get(reverse("feast-detail", args=[feast.id]))
        frequent_chants_zip = response_1.context["frequent_chants_zip"]
        cantus_ids = [x[0] for x in frequent_chants_zip]
        self.assertNotIn(chant.cantus_id, cantus_ids)

    def test_sources_containing_this_feast(self):
        big_source = make_fake_source(published=True, title="big_source", siglum="big")
        small_source = make_fake_source(
            published=True, title="small_source", siglum="small"
        )
        feast = make_fake_feast()
        # 3 chants in the big source
        for i in range(3):
            Chant.objects.create(feast=feast, source=big_source)
        # 1 chant in the small source
        Chant.objects.create(feast=feast, source=small_source)

        response = self.client.get(reverse("feast-detail", args=[feast.id]))
        sources_zip = response.context["sources_zip"]
        # the items in zip should be ordered by chant count
        # the first field is siglum
        self.assertEqual(sources_zip[0][0].siglum, "big")
        self.assertEqual(sources_zip[1][0].siglum, "small")
        # the second field is chant_count
        self.assertEqual(sources_zip[0][1], 3)
        self.assertEqual(sources_zip[1][1], 1)

    def test_sources_containing_feast_published_vs_unpublished(self):
        published_source = make_fake_source(
            published=True,
            title="published source",
        )
        unpublished_source = make_fake_source(published=False)
        feast = make_fake_feast()
        for _ in range(2):
            make_fake_chant(source=published_source, feast=feast)
        make_fake_chant(source=unpublished_source, feast=feast)

        response = self.client.get(reverse("feast-detail", args=[feast.id]))
        sources_zip = response.context["sources_zip"]
        self.assertEqual(
            len(sources_zip), 1
        )  # only item should be a duple corresponding to published_source
        self.assertEqual(sources_zip[0][0].title, "published source")
        self.assertEqual(sources_zip[0][1], 2)


class GenreListViewTest(TestCase):
    def test_view_url_path(self):
        response = self.client.get("/genres/")
        self.assertEqual(response.status_code, 200)

    def test_view_url_reverse_name(self):
        response = self.client.get(reverse("genre-list"))
        self.assertEqual(response.status_code, 200)

    def test_url_and_templates(self):
        """Test the url and templates used"""
        response = self.client.get(reverse("genre-list"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "base.html")
        self.assertTemplateUsed(response, "genre_list.html")

    def test_filter_by_mass(self):
        mass_office_genre = Genre.objects.create(
            name="genre1",
            description="test",
            mass_office="Mass, Office",
        )
        mass_genre = Genre.objects.create(
            name="genre2", description="test", mass_office="Mass"
        )
        office_genre = Genre.objects.create(
            name="genre3", description="test", mass_office="Office"
        )
        old_hispanic_genre = Genre.objects.create(
            name="genre4",
            description="test",
            mass_office="Old Hispanic",
        )
        # filter by Mass
        response = self.client.get(reverse("genre-list"), {"mass_office": "Mass"})
        genres = response.context["genres"]
        # Mass, Office and Mass should be in the list, while the others should not
        self.assertIn(mass_genre, genres)
        self.assertIn(mass_office_genre, genres)
        self.assertNotIn(office_genre, genres)
        self.assertNotIn(old_hispanic_genre, genres)

    def test_filter_by_office(self):
        mass_office_genre = Genre.objects.create(
            name="genre1",
            description="test",
            mass_office="Mass, Office",
        )
        mass_genre = Genre.objects.create(
            name="genre2", description="test", mass_office="Mass"
        )
        office_genre = Genre.objects.create(
            name="genre3", description="test", mass_office="Office"
        )
        old_hispanic_genre = Genre.objects.create(
            name="genre4",
            description="test",
            mass_office="Old Hispanic",
        )
        # filter by Office
        response = self.client.get(reverse("genre-list"), {"mass_office": "Office"})
        genres = response.context["genres"]
        # Office, Office and Mass should be in the list, while the others should not
        self.assertNotIn(mass_genre, genres)
        self.assertIn(mass_office_genre, genres)
        self.assertIn(office_genre, genres)
        self.assertNotIn(old_hispanic_genre, genres)

    def test_no_filtering(self):
        mass_office_genre = Genre.objects.create(
            name="genre1",
            description="test",
            mass_office="Mass, Office",
        )
        mass_genre = Genre.objects.create(
            name="genre2", description="test", mass_office="Mass"
        )
        office_genre = Genre.objects.create(
            name="genre3", description="test", mass_office="Office"
        )
        old_hispanic_genre = Genre.objects.create(
            name="genre4",
            description="test",
            mass_office="Old Hispanic",
        )
        # default is no filtering
        response = self.client.get(reverse("genre-list"))
        genres = response.context["genres"]
        # all genres should be in the list
        self.assertIn(mass_genre, genres)
        self.assertIn(mass_office_genre, genres)
        self.assertIn(office_genre, genres)
        self.assertIn(old_hispanic_genre, genres)

    def test_invalid_filtering(self):
        mass_office_genre = Genre.objects.create(
            name="genre1",
            description="test",
            mass_office="Mass, Office",
        )
        mass_genre = Genre.objects.create(
            name="genre2", description="test", mass_office="Mass"
        )
        office_genre = Genre.objects.create(
            name="genre3", description="test", mass_office="Office"
        )
        old_hispanic_genre = Genre.objects.create(
            name="genre4",
            description="test",
            mass_office="Old Hispanic",
        )
        # invalid filtering parameter should default to no filtering
        response = self.client.get(
            reverse("genre-list"), {"mass_office": "invalid param"}
        )
        genres = response.context["genres"]
        # all genres should be in the list
        self.assertIn(mass_genre, genres)
        self.assertIn(mass_office_genre, genres)
        self.assertIn(office_genre, genres)
        self.assertIn(old_hispanic_genre, genres)


class GenreDetailViewTest(TestCase):
    def setUp(self):
        for _ in range(10):
            make_fake_genre()

    def test_view_url_path(self):
        for genre in Genre.objects.all():
            response = self.client.get(f"/genre/{genre.id}")
            self.assertEqual(response.status_code, 200)

    def test_view_url_reverse_name(self):
        for genre in Genre.objects.all():
            response = self.client.get(reverse("genre-detail", args=[genre.id]))
            self.assertEqual(response.status_code, 200)

    def test_view_context_data(self):
        for genre in Genre.objects.all():
            response = self.client.get(reverse("genre-detail", args=[genre.id]))
            self.assertTrue("genre" in response.context)
            self.assertEqual(genre, response.context["genre"])

    def test_url_and_templates(self):
        """Test the url and templates used"""
        genre = make_fake_genre()
        response = self.client.get(reverse("genre-detail", args=[genre.id]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "base.html")
        self.assertTemplateUsed(response, "genre_detail.html")

    def test_context(self):
        genre = make_fake_genre()
        response = self.client.get(reverse("genre-detail", args=[genre.id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(genre, response.context["genre"])


class OfficeListViewTest(TestCase):
    OFFICE_COUNT = 10

    def setUp(self):
        for _ in range(self.OFFICE_COUNT):
            make_fake_office()

    def test_view_url_path(self):
        response = self.client.get("/offices/")
        self.assertEqual(response.status_code, 200)

    def test_view_url_reverse_name(self):
        response = self.client.get(reverse("office-list"))
        self.assertEqual(response.status_code, 200)

    def test_url_and_templates(self):
        response = self.client.get(reverse("office-list"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "base.html")
        self.assertTemplateUsed(response, "office_list.html")

    def test_context(self):
        response = self.client.get(reverse("office-list"))
        offices = response.context["offices"]
        # the list view should contain all offices
        self.assertEqual(offices.count(), self.OFFICE_COUNT)


class OfficeDetailViewTest(TestCase):
    def setUp(self):
        for _ in range(10):
            make_fake_office()

    def test_view_url_path(self):
        for office in Office.objects.all():
            response = self.client.get(f"/office/{office.id}")
            self.assertEqual(response.status_code, 200)

    def test_view_url_reverse_name(self):
        for office in Office.objects.all():
            response = self.client.get(reverse("office-detail", args=[office.id]))
            self.assertEqual(response.status_code, 200)

    def test_view_context_data(self):
        for office in Office.objects.all():
            response = self.client.get(reverse("office-detail", args=[office.id]))
            self.assertTrue("office" in response.context)
            self.assertEqual(office, response.context["office"])

    def test_url_and_templates(self):
        office = make_fake_office()
        response = self.client.get(reverse("office-detail", args=[office.id]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "base.html")
        self.assertTemplateUsed(response, "office_detail.html")

    def test_context(self):
        office = make_fake_office()
        response = self.client.get(reverse("office-detail", args=[office.id]))
        self.assertEqual(office, response.context["office"])


class ProvenanceDetailViewTest(TestCase):
    def test_view_url_path(self):
        provenance = make_fake_provenance()
        response = self.client.get(f"/provenance/{provenance.id}")
        self.assertEqual(response.status_code, 200)

    def test_view_url_reverse_name(self):
        provenance = make_fake_provenance()
        response = self.client.get(reverse("provenance-detail", args=[provenance.id]))
        self.assertEqual(response.status_code, 200)

    def test_url_and_templates(self):
        provenance = make_fake_provenance()
        response = self.client.get(reverse("provenance-detail", args=[provenance.id]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "base.html")
        self.assertTemplateUsed(response, "provenance_detail.html")

    def test_listed_sources(self):
        provenance = make_fake_provenance()
        provenance_sources = [
            make_fake_source(provenance=provenance, published=True) for _ in range(5)
        ]
        response = self.client.get(reverse("provenance-detail", args=[provenance.id]))
        returned_sources = response.context["sources"]
        for source in provenance_sources:
            self.assertIn(source, returned_sources)

    def test_unpublished_sources_not_listed(self):
        provenance = make_fake_provenance()
        published_sources = [
            make_fake_source(provenance=provenance, published=True) for _ in range(5)
        ]
        unpublished_sources = [
            make_fake_source(provenance=provenance, published=False) for _ in range(5)
        ]
        response = self.client.get(reverse("provenance-detail", args=[provenance.id]))
        returned_sources = response.context["sources"]
        for source in published_sources:
            self.assertIn(source, returned_sources)
        for source in unpublished_sources:
            self.assertNotIn(source, returned_sources)


class SequenceListViewTest(TestCase):
    def setUp(self):
        # unless a segment is specified when a source is created, the source is automatically assigned
        # to the segment with the name "CANTUS Database" - to prevent errors, we must make sure that
        # such a segment exists
        Segment.objects.create(name="CANTUS Database")

    def test_url_and_templates(self):
        response = self.client.get(reverse("sequence-list"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "base.html")
        self.assertTemplateUsed(response, "sequence_list.html")

    def test_ordering(self):
        # the sequences in the list should be ordered by the "siglum" and "sequence" fields
        response = self.client.get(reverse("sequence-list"))
        sequences = response.context["sequences"]
        self.assertEqual(sequences.query.order_by, ("siglum", "s_sequence"))

    def test_search_incipit(self):
        # create a published sequence source and some sequence in it
        source = make_fake_source(
            published=True,
            title="a sequence source",
        )
        sequence = Sequence.objects.create(
            incipit=faker.sentence(),
            source=source,
        )
        search_term = get_random_search_term(sequence.incipit)
        # request the page, search for the incipit
        response = self.client.get(reverse("sequence-list"), {"incipit": search_term})
        # the sequence should be present in the results
        self.assertIn(sequence, response.context["sequences"])

    def test_search_siglum(self):
        # create a published sequence source and some sequence in it
        source = make_fake_source(
            published=True,
            title="a sequence source",
        )
        sequence = Sequence.objects.create(siglum=make_random_string(6), source=source)
        search_term = get_random_search_term(sequence.siglum)
        # request the page, search for the siglum
        response = self.client.get(reverse("sequence-list"), {"siglum": search_term})
        # the sequence should be present in the results
        self.assertIn(sequence, response.context["sequences"])

    def test_search_cantus_id(self):
        # create a published sequence source and some sequence in it
        source = make_fake_source(published=True, title="a sequence source")
        # faker generates a fake cantus id, in the form of two letters followed by five digits
        sequence = Sequence.objects.create(
            cantus_id=faker.bothify("??#####"), source=source
        )
        search_term = get_random_search_term(sequence.cantus_id)
        # request the page, search for the incipit
        response = self.client.get(reverse("sequence-list"), {"cantus_id": search_term})
        # the sequence should be present in the results
        self.assertIn(sequence, response.context["sequences"])


class SequenceDetailViewTest(TestCase):
    def test_url_and_templates(self):
        sequence = make_fake_sequence()
        response = self.client.get(reverse("sequence-detail", args=[sequence.id]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "base.html")
        self.assertTemplateUsed(response, "sequence_detail.html")

    def test_concordances(self):
        sequence = make_fake_sequence()
        sequence_with_same_cantus_id = make_fake_sequence(cantus_id=sequence.cantus_id)
        response = self.client.get(reverse("sequence-detail", args=[sequence.id]))
        concordances = response.context["concordances"]
        self.assertIn(sequence_with_same_cantus_id, concordances)

    def test_sequence_without_cantus_id(self):
        sequence = make_fake_sequence()
        sequence.cantus_id = None
        sequence.save()
        response = self.client.get(reverse("sequence-detail", args=[sequence.id]))
        html = str(response.content)
        # Since sequence's cantus_id is None, there should be no table of
        # concordances displayed, and we shouldn't display "None" anywhere
        self.assertNotIn("Concordances", html)
        self.assertNotIn("None", html)
        # This is just to ensure that `html`, `response`, etc. are working
        # correctly, i.e. that the `self.assertNotIn`s above are not passing
        # for an unrelated reason
        self.assertIn("Siglum", html)


class SequenceEditViewTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        Group.objects.create(name="project manager")

    def setUp(self):
        self.user = get_user_model().objects.create(email="test@test.com")
        self.user.set_password("pass")
        self.user.save()
        self.client = Client()
        project_manager = Group.objects.get(name="project manager")
        project_manager.user_set.add(self.user)
        self.client.login(email="test@test.com", password="pass")

    def test_context(self):
        sequence = make_fake_sequence()
        response = self.client.get(reverse("sequence-edit", args=[sequence.id]))
        self.assertEqual(sequence, response.context["object"])

    def test_url_and_templates(self):
        sequence = make_fake_sequence()

        response = self.client.get(reverse("sequence-edit", args=[sequence.id]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "sequence_edit.html")

        response = self.client.get(reverse("sequence-edit", args=[sequence.id + 100]))
        self.assertEqual(response.status_code, 404)
        self.assertTemplateUsed(response, "404.html")

    def test_update_sequence(self):
        sequence = make_fake_sequence()
        sequence_id = str(sequence.id)
        response = self.client.post(
            reverse("sequence-edit", args=[sequence_id]),
            {"title": "test", "source": sequence.source.id},
        )
        self.assertEqual(response.status_code, 302)
        sequence.refresh_from_db()
        self.assertEqual(sequence.title, "test")


class SourceListViewTest(TestCase):
    def setUp(self):
        # unless a segment is specified when a source is created, the source is automatically assigned
        # to the segment with the name "CANTUS Database" - to prevent errors, we must make sure that
        # such a segment exists
        Segment.objects.create(name="CANTUS Database")

    def test_url_and_templates(self):
        response = self.client.get(reverse("source-list"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "base.html")
        self.assertTemplateUsed(response, "source_list.html")

    def test_provenances_and_centuries_in_context(self):
        """Test the `provenances` and `centuries` in the context. They are displayed as options in the selectors"""
        provenance = make_fake_provenance()
        century = make_fake_century()
        response = self.client.get(reverse("source-list"))
        provenances = response.context["provenances"]
        self.assertIn({"id": provenance.id, "name": provenance.name}, provenances)
        centuries = response.context["centuries"]
        self.assertIn({"id": century.id, "name": century.name}, centuries)

    def test_only_published_sources_visible(self):
        """For a source to be displayed in the list, its `published` field must be `True`"""
        published_source = make_fake_source(published=True, title="published source")
        private_source = make_fake_source(published=False, title="private source")
        response = self.client.get(reverse("source-list"))
        sources = response.context["sources"]
        self.assertIn(published_source, sources)
        self.assertNotIn(private_source, sources)

    def test_filter_by_segment(self):
        """The source list can be filtered by `segment`, `provenance`, `century`, and `full_source`"""
        cantus_segment = make_fake_segment(name="cantus")
        clavis_segment = make_fake_segment(name="clavis")
        chant_source = make_fake_source(
            segment=cantus_segment, title="chant source", published=True
        )
        seq_source = make_fake_source(
            segment=clavis_segment, title="sequence source", published=True
        )

        # display chant sources only
        response = self.client.get(
            reverse("source-list"), {"segment": cantus_segment.id}
        )
        sources = response.context["sources"]
        self.assertIn(chant_source, sources)
        self.assertNotIn(seq_source, sources)

        # display sequence sources only
        response = self.client.get(
            reverse("source-list"), {"segment": clavis_segment.id}
        )
        sources = response.context["sources"]
        self.assertIn(seq_source, sources)
        self.assertNotIn(chant_source, sources)

    def test_filter_by_provenance(self):
        aachen = make_fake_provenance()
        albi = make_fake_provenance()
        aachen_source = make_fake_source(
            provenance=aachen,
            published=True,
            title="source originated in Aachen",
        )
        albi_source = make_fake_source(
            provenance=albi,
            published=True,
            title="source originated in Albi",
        )
        no_provenance_source = make_fake_source(
            published=True,
            provenance=None,
            title="source with empty provenance",
        )

        # display sources in Aachen
        response = self.client.get(reverse("source-list"), {"provenance": aachen.id})
        sources = response.context["sources"]
        # only aachen_source should be in the list
        self.assertIn(aachen_source, sources)
        self.assertNotIn(albi_source, sources)
        self.assertNotIn(no_provenance_source, sources)

    def test_filter_by_century(self):
        ninth_century = Century.objects.create(name="09th century")
        ninth_century_first_half = Century.objects.create(
            name="09th century (1st half)"
        )
        tenth_century = Century.objects.create(name="10th century")

        ninth_century_source = make_fake_source(
            published=True,
            title="source",
        )
        ninth_century_source.century.set([ninth_century])

        ninth_century_first_half_source = make_fake_source(
            published=True,
            title="source",
        )
        ninth_century_first_half_source.century.set([ninth_century_first_half])

        multiple_century_source = make_fake_source(
            published=True,
            title="source",
        )
        multiple_century_source.century.set([ninth_century, tenth_century])

        # display sources in ninth century
        response = self.client.get(
            reverse("source-list"), {"century": ninth_century.id}
        )
        sources = response.context["sources"]
        # ninth_century_source, ninth_century_first_half_source, and
        # multiple_century_source should all be in the list
        self.assertIn(ninth_century_source, sources)
        self.assertIn(ninth_century_first_half_source, sources)
        self.assertIn(multiple_century_source, sources)

        # display sources in ninth century first half
        response = self.client.get(
            reverse("source-list"), {"century": ninth_century_first_half.id}
        )
        sources = response.context["sources"]
        # only ninth_century_first_half_source should be in the list
        self.assertNotIn(ninth_century_source, sources)
        self.assertIn(ninth_century_first_half_source, sources)
        self.assertNotIn(multiple_century_source, sources)

    def test_filter_by_full_source(self):
        full_source = make_fake_source(
            full_source=True,
            published=True,
            title="full source",
        )
        fragment = make_fake_source(
            full_source=False,
            published=True,
            title="fragment",
        )
        unknown = make_fake_source(
            full_source=None,
            published=True,
            title="full_source field is empty",
        )

        # display full sources
        response = self.client.get(reverse("source-list"), {"fullSource": "true"})
        sources = response.context["sources"]
        # full_source and unknown_source should be in the list, fragment should not
        self.assertIn(full_source, sources)
        self.assertNotIn(fragment, sources)
        self.assertIn(unknown, sources)

        # display fragments
        response = self.client.get(reverse("source-list"), {"fullSource": "false"})
        sources = response.context["sources"]
        # fragment should be in the list, full_source and unknown_source should not
        self.assertNotIn(full_source, sources)
        self.assertIn(fragment, sources)
        self.assertNotIn(unknown, sources)

        # display all sources
        response = self.client.get(reverse("source-list"))
        sources = response.context["sources"]
        # all three should be in the list
        self.assertIn(full_source, sources)
        self.assertIn(fragment, sources)
        self.assertIn(unknown, sources)

    def test_search_by_title(self):
        """The "general search" field searches in `title`, `siglum`, `rism_siglum`, `description`, and `summary`"""
        source = make_fake_source(
            title=faker.sentence(),
            published=True,
        )
        search_term = get_random_search_term(source.title)
        response = self.client.get(reverse("source-list"), {"general": search_term})
        self.assertIn(source, response.context["sources"])

        # Test that postgres searches unaccented version of title
        unaccented_title = source.title
        accented_title = add_accents_to_string(unaccented_title)
        source.title = accented_title
        source.save()
        response = self.client.get(reverse("source-list"), {"general": search_term})
        self.assertIn(source, response.context["sources"])

    def test_search_by_siglum(self):
        source = make_fake_source(
            siglum=make_random_string(6),
            published=True,
            title="title",
        )
        search_term = get_random_search_term(source.siglum)
        response = self.client.get(reverse("source-list"), {"general": search_term})
        self.assertIn(source, response.context["sources"])

        # Test that postgres searches unaccented version of siglum
        unaccented_siglum = source.siglum
        accented_siglum = add_accents_to_string(unaccented_siglum)
        source.siglum = accented_siglum
        source.save()
        response = self.client.get(reverse("source-list"), {"general": search_term})
        self.assertIn(source, response.context["sources"])

    def test_search_by_rism_siglum_name(self):
        rism_siglum = make_fake_rism_siglum()
        source = make_fake_source(
            rism_siglum=rism_siglum,
            published=True,
            title="title",
        )
        search_term = get_random_search_term(source.rism_siglum.name)
        response = self.client.get(reverse("source-list"), {"general": search_term})
        self.assertIn(source, response.context["sources"])

        # Test that postgres searches unaccented version of RISM siglum name
        unaccented_name = rism_siglum.name
        accented_name = add_accents_to_string(unaccented_name)
        rism_siglum.name = accented_name
        rism_siglum.save()
        response = self.client.get(reverse("source-list"), {"general": search_term})
        self.assertIn(source, response.context["sources"])

    def test_search_by_rism_siglum_description(self):
        rism_siglum = make_fake_rism_siglum()
        source = make_fake_source(
            rism_siglum=rism_siglum,
            published=True,
            title="title",
        )
        search_term = get_random_search_term(source.rism_siglum.description)
        response = self.client.get(reverse("source-list"), {"general": search_term})
        self.assertIn(source, response.context["sources"])

        # Test that postgres searches unaccented version of RISM siglum description
        unaccented_description = rism_siglum.description
        accented_description = add_accents_to_string(unaccented_description)
        rism_siglum.description = accented_description
        rism_siglum.save()
        response = self.client.get(reverse("source-list"), {"general": search_term})
        self.assertIn(source, response.context["sources"])

    def test_search_by_description(self):
        source = make_fake_source(
            description=faker.sentence(),
            published=True,
            title="title",
        )
        search_term = get_random_search_term(source.description)
        response = self.client.get(reverse("source-list"), {"general": search_term})
        self.assertIn(source, response.context["sources"])

        # Test that postgres searches unaccented version of description
        unaccented_description = source.description
        accented_description = add_accents_to_string(unaccented_description)
        source.title = accented_description
        source.save()
        response = self.client.get(reverse("source-list"), {"general": search_term})
        self.assertIn(source, response.context["sources"])

    def test_search_by_summary(self):
        source = make_fake_source(
            summary=faker.sentence(),
            published=True,
            title="title",
        )
        search_term = get_random_search_term(source.summary)
        response = self.client.get(reverse("source-list"), {"general": search_term})
        self.assertIn(source, response.context["sources"])

        # Test that postgres searches unaccented version of summary
        unaccented_summary = source.summary
        accented_summary = add_accents_to_string(unaccented_summary)
        source.title = accented_summary
        source.save()
        response = self.client.get(reverse("source-list"), {"general": search_term})
        self.assertIn(source, response.context["sources"])

    def test_search_by_indexing_notes(self):
        """The "indexing notes" field searches in `indexing_notes` and indexer/editor related fields"""
        source = make_fake_source(
            indexing_notes=faker.sentence(),
            published=True,
            title="title",
        )
        search_term = get_random_search_term(source.indexing_notes)
        response = self.client.get(reverse("source-list"), {"indexing": search_term})
        self.assertIn(source, response.context["sources"])

        # Test that postgres searches unaccented version of indexing_notes
        unaccented_indexing_notes = source.indexing_notes
        accented_indexing_notes = add_accents_to_string(unaccented_indexing_notes)
        source.title = accented_indexing_notes
        source.save()
        response = self.client.get(reverse("source-list"), {"general": search_term})
        self.assertIn(source, response.context["sources"])


class SourceCreateViewTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        Group.objects.create(name="project manager")

    def setUp(self):
        self.user = get_user_model().objects.create(email="test@test.com")
        self.user.set_password("pass")
        self.user.save()
        self.client = Client()
        project_manager = Group.objects.get(name="project manager")
        project_manager.user_set.add(self.user)
        self.client.login(email="test@test.com", password="pass")
        # unless a segment is specified when a source is created, the source is automatically assigned
        # to the segment with the name "CANTUS Database" - to prevent errors, we must make sure that
        # such a segment exists
        Segment.objects.create(name="CANTUS Database")

    def test_url_and_templates(self):
        response = self.client.get(reverse("source-create"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "source_create_form.html")

    def test_create_source(self):
        response = self.client.post(
            reverse("source-create"),
            {
                "title": "test",
                "siglum": "test-siglum",  # siglum is a required field
            },
        )

        self.assertEqual(response.status_code, 302)
        created_source = Source.objects.get(siglum="test-siglum")
        self.assertRedirects(
            response,
            reverse("source-detail", args=[created_source.id]),
        )

        source = Source.objects.first()
        self.assertEqual(source.title, "test")


class SourceEditViewTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        Group.objects.create(name="project manager")

    def setUp(self):
        self.user = get_user_model().objects.create(email="test@test.com")
        self.user.set_password("pass")
        self.user.save()
        self.client = Client()
        project_manager = Group.objects.get(name="project manager")
        project_manager.user_set.add(self.user)
        self.client.login(email="test@test.com", password="pass")

    def test_context(self):
        source = make_fake_source()
        response = self.client.get(reverse("source-edit", args=[source.id]))
        self.assertEqual(source, response.context["object"])

    def test_url_and_templates(self):
        source = make_fake_source()

        response = self.client.get(reverse("source-edit", args=[source.id]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "source_edit.html")

        response = self.client.get(reverse("source-edit", args=[source.id + 100]))
        self.assertEqual(response.status_code, 404)
        self.assertTemplateUsed(response, "404.html")

    def test_edit_source(self):
        source = make_fake_source()

        response = self.client.post(
            reverse("source-edit", args=[source.id]),
            {
                "title": "test",
                "siglum": "test-siglum",  # siglum is a required field,
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse("source-detail", args=[source.id]))
        source.refresh_from_db()
        self.assertEqual(source.title, "test")


class SourceDetailViewTest(TestCase):
    def test_url_and_templates(self):
        source = make_fake_source()
        response = self.client.get(reverse("source-detail", args=[source.id]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "base.html")
        self.assertTemplateUsed(response, "source_detail.html")

    def test_context_chant_folios(self):
        # create a source and several chants in it
        source = make_fake_source()
        Chant.objects.create(source=source, folio="001r")
        Chant.objects.create(source=source, folio="001r")
        Chant.objects.create(source=source, folio="001v")
        Chant.objects.create(source=source, folio="001v")
        Chant.objects.create(source=source, folio="002r")
        Chant.objects.create(source=source, folio="002v")
        # request the page
        response = self.client.get(reverse("source-detail", args=[source.id]))
        # the element in "folios" should be unique and ordered in this way
        folios = response.context["folios"]
        self.assertEqual(list(folios), ["001r", "001v", "002r", "002v"])

    def test_context_sequence_folios(self):
        # create a sequence source and several sequences in it
        bower_segment = Segment.objects.create(id=4064, name="Bower Sequence Database")
        source = make_fake_source(
            title="a sequence source", published=True, segment=bower_segment
        )
        Sequence.objects.create(source=source, folio="001r")
        Sequence.objects.create(source=source, folio="001r")
        Sequence.objects.create(source=source, folio="001v")
        Sequence.objects.create(source=source, folio="001v")
        Sequence.objects.create(source=source, folio="002r")
        Sequence.objects.create(source=source, folio="002v")
        # request the page
        response = self.client.get(reverse("source-detail", args=[source.id]))
        # the element in "folios" should be unique and ordered in this way
        folios = response.context["folios"]
        self.assertEqual(list(folios), ["001r", "001v", "002r", "002v"])
        # the folios should be ordered by the "folio" field
        self.assertEqual(folios.query.order_by, ("folio",))

    def test_context_feasts_with_folios(self):
        # create a source and several chants (associated with feasts) in it
        source = make_fake_source()
        feast_1 = make_fake_feast()
        feast_2 = make_fake_feast()
        Chant.objects.create(source=source, folio="001r", feast=feast_1)
        Chant.objects.create(source=source, folio="001r", feast=feast_1)
        Chant.objects.create(source=source, folio="001v", feast=feast_2)
        Chant.objects.create(source=source, folio="001v")
        Chant.objects.create(source=source, folio="001v", feast=feast_2)
        Chant.objects.create(source=source, folio="002r", feast=feast_1)
        # request the page
        response = self.client.get(reverse("source-detail", args=[source.id]))
        # context "feasts_with_folios" is a list of tuples
        # it records the folios where the feast changes
        expected_result = [("001r", feast_1), ("001v", feast_2), ("002r", feast_1)]
        self.assertEqual(response.context["feasts_with_folios"], expected_result)

    def test_context_sequences(self):
        # create a sequence source and several sequences in it
        source = make_fake_source(
            segment=Segment.objects.create(id=4064, name="Bower Sequence Database"),
            title="a sequence source",
            published=True,
        )
        sequence = Sequence.objects.create(source=source)
        # request the page
        response = self.client.get(reverse("source-detail", args=[source.id]))
        # the sequence should be in the list of sequences
        self.assertIn(sequence, response.context["sequences"])
        # the list of sequences should be ordered by the "sequence" field
        self.assertEqual(response.context["sequences"].query.order_by, ("s_sequence",))

    def test_published_vs_unpublished(self):
        source = make_fake_source(published=False)
        response_1 = self.client.get(reverse("source-detail", args=[source.id]))
        self.assertEqual(response_1.status_code, 403)

        source.published = True
        source.save()
        response_2 = self.client.get(reverse("source-detail", args=[source.id]))
        self.assertEqual(response_2.status_code, 200)

    def test_chant_list_link(self):
        cantus_segment = make_fake_segment(id=4063)
        cantus_source = make_fake_source(segment=cantus_segment)
        chant_list_link = reverse("chant-list", args=[cantus_source.id])

        cantus_source_response = self.client.get(
            reverse("source-detail", args=[cantus_source.id])
        )
        cantus_source_html = str(cantus_source_response.content)
        self.assertIn(chant_list_link, cantus_source_html)

        bower_segment = make_fake_segment(id=4064)
        bower_source = make_fake_source(segment=bower_segment)
        bower_chant_list_link = reverse("chant-list", args=[bower_source.id])
        bower_source_response = self.client.get(
            reverse("source-detail", args=[bower_source.id])
        )
        bower_source_html = str(bower_source_response.content)
        self.assertNotIn(bower_chant_list_link, bower_source_html)


class SourceInventoryViewTest(TestCase):
    def test_url_and_templates(self):
        source = make_fake_source()
        response = self.client.get(reverse("source-inventory", args=[source.id]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "full_inventory.html")

    def test_published_vs_unpublished(self):
        source = make_fake_source()

        source.published = True
        source.save()
        response = self.client.get(reverse("source-inventory", args=[source.id]))
        self.assertEqual(response.status_code, 200)

        source.published = False
        source.save()
        response = self.client.get(reverse("source-inventory", args=[source.id]))
        self.assertEqual(response.status_code, 403)

    def test_chant_source_queryset(self):
        chant_source = make_fake_source()
        chant = make_fake_chant(source=chant_source)
        response = self.client.get(reverse("source-inventory", args=[chant_source.id]))
        self.assertEqual(chant_source, response.context["source"])
        self.assertIn(chant, response.context["chants"])

    def test_sequence_source_queryset(self):
        seq_source = make_fake_source(
            segment=Segment.objects.create(id=4064, name="Clavis Sequentiarium"),
            title="a sequence source",
            published=True,
        )
        sequence = Sequence.objects.create(source=seq_source)
        response = self.client.get(reverse("source-inventory", args=[seq_source.id]))
        self.assertEqual(seq_source, response.context["source"])
        self.assertIn(sequence, response.context["chants"])

    def test_siglum_column(self):
        siglum = "Sigl-01"
        source = make_fake_source(published=True, siglum=siglum)
        source_title = source.title
        make_fake_chant(source=source)
        response = self.client.get(reverse("source-inventory", args=[source.id]))
        html = str(response.content)
        self.assertIn(siglum, html)
        self.assertIn(source_title, html)
        expected_html_substring = f'<td title="{source_title}">{siglum}</td>'
        self.assertIn(expected_html_substring, html)

    def test_marginalia_column(self):
        source = make_fake_source(published=True)
        chant = make_fake_chant(source=source)
        marginalia = chant.marginalia
        response = self.client.get(reverse("source-inventory", args=[source.id]))
        html = str(response.content)
        self.assertIn(marginalia, html)
        expected_html_substring = f"<td>{marginalia}</td>"
        self.assertIn(expected_html_substring, html)

    def test_folio_column(self):
        source = make_fake_source(published=True)
        chant = make_fake_chant(source=source)
        folio = chant.folio
        response = self.client.get(reverse("source-inventory", args=[source.id]))
        html = str(response.content)
        self.assertIn(folio, html)
        expected_html_substring = f"<td>{folio}</td>"
        self.assertIn(expected_html_substring, html)

    def test_sequence_column_for_chant_source(self):
        source = make_fake_source(published=True)
        chant = make_fake_chant(source=source)
        c_sequence = str(chant.c_sequence)
        response = self.client.get(reverse("source-inventory", args=[source.id]))
        html = str(response.content)
        self.assertIn(c_sequence, html)

    def test_sequence_column_for_sequence_source(self):
        bower_segment = Segment.objects.create(id=4064, name="Bower Sequence Database")
        source = make_fake_source(published=True, segment=bower_segment)
        sequence = make_fake_sequence(source=source)
        s_sequence = sequence.s_sequence
        response = self.client.get(reverse("source-inventory", args=[source.id]))
        html = str(response.content)
        self.assertIn(s_sequence, html)

    def test_feast_column(self):
        source = make_fake_source(published=True)
        feast = make_fake_feast()
        feast_name = feast.name
        feast_description = feast.description
        make_fake_chant(
            source=source,
            feast=feast,
        )
        response = self.client.get(reverse("source-inventory", args=[source.id]))
        html = str(response.content)
        self.assertIn(feast_name, html)
        self.assertIn(feast_description, html)

    def test_office_column(self):
        source = make_fake_source(published=True)
        office = make_fake_office()
        office_name = office.name
        office_description = office.description
        fulltext = "manuscript full text"
        make_fake_chant(
            source=source,
            manuscript_full_text_std_spelling=fulltext,
            office=office,
        )
        response = self.client.get(reverse("source-inventory", args=[source.id]))
        html = str(response.content)
        self.assertIn(office_name, html)
        self.assertIn(office_description, html)

    def test_genre_column(self):
        source = make_fake_source(published=True)
        genre = make_fake_genre()
        genre_name = genre.name
        genre_description = genre.description
        make_fake_chant(
            source=source,
            genre=genre,
        )
        response = self.client.get(reverse("source-inventory", args=[source.id]))
        html = str(response.content)
        self.assertIn(genre_name, html)
        self.assertIn(genre_description, html)

    def test_position_column(self):
        source = make_fake_source(published=True)
        chant = make_fake_chant(
            source=source,
        )
        position = chant.position
        response = self.client.get(reverse("source-inventory", args=[source.id]))
        html = str(response.content)
        self.assertIn(position, html)

    def test_incipit_column_for_chant_source(self):
        source = make_fake_source(published=True)
        chant = make_fake_chant(source=source)
        chant.refresh_from_db()  # incipit is automatically calculated from fulltext
        # on chant save; refreshing from DB allows us to compare the value to what we see in
        # the results.
        incipit = chant.incipit
        url = reverse("chant-detail", args=[chant.id])
        response = self.client.get(reverse("source-inventory", args=[source.id]))
        html = str(response.content)
        self.assertIn(incipit, html)
        self.assertIn(url, html)
        expected_html_substring = f'<a href="{url}" target="_blank">{incipit}</a>'
        self.assertIn(expected_html_substring, html)

    def test_incipit_column_for_sequence_source(self):
        bower_segment = Segment.objects.create(id=4064, name="Bower Sequence Database")
        source = make_fake_source(published=True, segment=bower_segment)
        sequence = make_fake_sequence(source=source)
        sequence.refresh_from_db()  # incipit is automatically calculated from fulltext
        # on sequence save; refreshing from DB allows us to compare the value to what we see in
        # the results.
        incipit = sequence.incipit
        url = reverse("sequence-detail", args=[sequence.id])
        response = self.client.get(reverse("source-inventory", args=[source.id]))
        html = str(response.content)
        self.assertIn(incipit, html)
        self.assertIn(url, html)
        expected_html_substring = f'<a href="{url}" target="_blank">{incipit}</a>'
        self.assertIn(expected_html_substring, html)

    def test_cantus_id_column(self):
        source = make_fake_source(published=True)
        chant = make_fake_chant(source=source)
        cantus_id = chant.cantus_id
        response = self.client.get(reverse("source-inventory", args=[source.id]))
        html = str(response.content)
        self.assertIn(cantus_id, html)
        expected_html_substring = f"<td>{cantus_id}</td>"
        self.assertIn(expected_html_substring, html)

    def test_mode_column(self):
        source = make_fake_source(published=True)
        chant = make_fake_chant(
            source=source,
        )
        mode = "this is the mode"  # not a representative value, but
        # single numerals are found elsewhere in the template
        chant.mode = mode
        chant.save()
        response = self.client.get(reverse("source-inventory", args=[source.id]))
        html = str(response.content)
        self.assertIn(mode, html)
        expected_html_substring = f"<td>{mode}</td>"
        self.assertIn(expected_html_substring, html)

    def test_diff_column(self):
        source = make_fake_source(published=True)
        differentia = "this is a differentia"  # not a representative value, but
        # most differentia are one or two characters, likely to be found elsewhere
        # in the template
        make_fake_chant(
            source=source,
            differentia=differentia,
        )
        response = self.client.get(reverse("source-inventory", args=[source.id]))
        html = str(response.content)
        self.assertIn(differentia, html)
        expected_html_substring = f"<td>{differentia}</td>"
        self.assertIn(expected_html_substring, html)

    def test_dd_column(self):
        source: Source = make_fake_source(published=True)
        diff_id: str = make_random_string(3, "0123456789") + make_random_string(
            1, "abcd"
        )  # e.g., "012a"
        diff_db: Differentia = Differentia.objects.create(differentia_id=diff_id)
        chant: Chant = make_fake_chant(
            source=source,
        )
        chant.diff_db = diff_db
        chant.save()

        response = self.client.get(reverse("source-inventory", args=[source.id]))
        html: str = str(response.content)
        self.assertIn(diff_id, html)
        expected_html_substring: str = f'<a href="https://differentiaedatabase.ca/differentia/{diff_id}" target="_blank">'
        self.assertIn(expected_html_substring, html)

    def test_redirect_with_source_parameter(self):
        cantus_segment = make_fake_segment(id=4063)
        source = make_fake_source(segment=cantus_segment)
        source_id = source.id

        url = reverse("redirect-source-inventory")
        response = self.client.get(f"{url}?source={source_id}")
        self.assertRedirects(
            response, reverse("source-inventory", args=[source_id]), status_code=301
        )

    def test_redirect_without_source_parameter(self):
        url = reverse("redirect-source-inventory")
        # Omitting the source parameter to simulate a bad request
        response = self.client.get(url)
        self.assertEqual(response.status_code, 400)
        self.assertTemplateUsed(response, "400.html")


class JsonMelodyExportTest(TestCase):
    def test_json_melody_response(self):
        NUM_CHANTS = 10
        FAKE_CANTUS_ID = "111111"
        for _ in range(NUM_CHANTS):
            make_fake_chant(cantus_id=FAKE_CANTUS_ID)

        response_1 = self.client.get(f"/json-melody/{FAKE_CANTUS_ID}")
        self.assertEqual(response_1.status_code, 200)
        self.assertIsInstance(response_1, JsonResponse)

        response_2 = self.client.get(
            reverse("json-melody-export", args=[FAKE_CANTUS_ID])
        )
        self.assertEqual(response_1.status_code, 200)
        self.assertIsInstance(response_2, JsonResponse)
        unpacked_response = json.loads(response_2.content)
        self.assertEqual(len(unpacked_response), NUM_CHANTS)

    def test_json_melody_fields(self):
        CORRECT_FIELDS = {
            "mid",
            "nid",
            "cid",
            "siglum",
            "srcnid",
            "folio",
            "incipit",
            "fulltext",
            "volpiano",
            "mode",
            "feast",
            "office",
            "genre",
            "position",
            "chantlink",
            "srclink",
        }
        FAKE_CANTUS_ID = "111111"
        make_fake_chant(cantus_id=FAKE_CANTUS_ID)
        response = self.client.get(reverse("json-melody-export", args=[FAKE_CANTUS_ID]))
        unpacked = json.loads(response.content)[0]
        response_fields = set(unpacked.keys())
        self.assertEqual(response_fields, CORRECT_FIELDS)

    def test_json_melody_published_vs_unpublished(self):
        FAKE_CANTUS_ID = "111111"
        published_source = make_fake_source(published=True)
        published_chant = make_fake_chant(
            cantus_id=FAKE_CANTUS_ID,
            manuscript_full_text_std_spelling="I'm a chant from a published source!",
            source=published_source,
        )
        unpublished_source = make_fake_source(published=False)
        unpublished_chant = make_fake_chant(
            cantus_id=FAKE_CANTUS_ID,
            manuscript_full_text_std_spelling="Help, I'm trapped in a JSON response factory! Can you help me escape...?",
            source=unpublished_source,
        )
        response = self.client.get(reverse("json-melody-export", args=[FAKE_CANTUS_ID]))
        unpacked_response = json.loads(response.content)
        self.assertEqual(len(unpacked_response), 1)  # just published_chant
        self.assertEqual(
            unpacked_response[0]["fulltext"], "I'm a chant from a published source!"
        )


class JsonNodeExportTest(TestCase):
    def test_json_node_response(self):
        chant = make_fake_chant()
        id = chant.id

        response_1 = self.client.get(f"/json-node/{id}")
        self.assertEqual(response_1.status_code, 200)
        self.assertIsInstance(response_1, JsonResponse)

        response_2 = self.client.get(reverse("json-node-export", args=[id]))
        self.assertEqual(response_2.status_code, 200)
        self.assertIsInstance(response_2, JsonResponse)

        response_3 = self.client.get(reverse("json-node-export", args=["1000000000"]))
        self.assertEqual(response_3.status_code, 404)

    def test_404_for_objects_created_in_newcantus(self):
        # json_node should only work for items created in OldCantus, where objects of different
        # types are all guaranteed to have unique IDs.
        # objects created in NewCantus should all have ID >= 1_000_000
        chant = make_fake_chant()
        chant.id = 1_000_001
        chant.save()

        response_3 = self.client.get(reverse("json-node-export", args=["1000001"]))
        self.assertEqual(response_3.status_code, 404)

    def test_json_node_for_chant(self):
        chant = make_fake_chant()
        id = chant.id

        response = self.client.get(reverse("json-node-export", args=[id]))
        self.assertIsInstance(response, JsonResponse)

        unpacked_response = json.loads(response.content)

        response_cantus_id = unpacked_response["cantus_id"]
        self.assertIsInstance(response_cantus_id, str)
        self.assertEqual(response_cantus_id, chant.cantus_id)

        response_id = unpacked_response["id"]
        self.assertIsInstance(response_id, int)
        self.assertEqual(response_id, id)

    def test_json_node_for_sequence(self):
        sequence = make_fake_sequence()
        id = sequence.id

        response = self.client.get(reverse("json-node-export", args=[id]))
        self.assertIsInstance(response, JsonResponse)

        unpacked_response = json.loads(response.content)

        response_cantus_id = unpacked_response["cantus_id"]
        self.assertIsInstance(response_cantus_id, str)
        self.assertEqual(response_cantus_id, sequence.cantus_id)

        response_id = unpacked_response["id"]
        self.assertIsInstance(response_id, int)
        self.assertEqual(response_id, id)

    def test_json_node_for_source(self):
        source = make_fake_source()
        id = source.id

        response = self.client.get(reverse("json-node-export", args=[id]))
        self.assertIsInstance(response, JsonResponse)

        unpacked_response = json.loads(response.content)

        response_title = unpacked_response["title"]
        self.assertIsInstance(response_title, str)
        self.assertEqual(response_title, source.title)

        response_id = unpacked_response["id"]
        self.assertIsInstance(response_id, int)
        self.assertEqual(response_id, id)

    def test_json_node_published_vs_unpublished(self):
        source = make_fake_source(published=True)
        chant = make_fake_chant(source=source)
        sequence = make_fake_sequence(source=source)

        source_id = source.id
        chant_id = chant.id
        sequence_id = sequence.id

        published_source_response = self.client.get(
            reverse("json-node-export", args=[source_id])
        )
        self.assertEqual(published_source_response.status_code, 200)
        published_chant_response = self.client.get(
            reverse("json-node-export", args=[chant_id])
        )
        self.assertEqual(published_chant_response.status_code, 200)
        published_sequence_response = self.client.get(
            reverse("json-node-export", args=[sequence_id])
        )
        self.assertEqual(published_sequence_response.status_code, 200)

        source.published = False
        source.save()

        unpublished_source_response = self.client.get(
            reverse("json-node-export", args=[source_id])
        )
        self.assertEqual(unpublished_source_response.status_code, 404)
        unpublished_chant_response = self.client.get(
            reverse("json-node-export", args=[chant_id])
        )
        self.assertEqual(unpublished_chant_response.status_code, 404)
        unpublished_sequence_response = self.client.get(
            reverse("json-node-export", args=[sequence_id])
        )
        self.assertEqual(unpublished_sequence_response.status_code, 404)


class NotationJsonTest(TestCase):
    def test_response(self):
        notation: Notation = make_fake_notation()
        id: int = notation.id

        response = self.client.get(reverse("notation-json-export", args=[id]))
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response, JsonResponse)

    def test_keys(self):
        notation: Notation = make_fake_notation()
        id: int = notation.id

        response = self.client.get(reverse("notation-json-export", args=[id]))
        response_json: dict = response.json()
        response_keys = response_json.keys()

        expected_keys = [
            "id",
            "name",
            "date_created",
            "date_updated",
            "created_by",
            "last_updated_by",
        ]
        for key in expected_keys:
            with self.subTest(key=key):
                self.assertIn(key, response_keys)


class ProvenanceJsonTest(TestCase):
    def test_response(self):
        provenance: Provenance = make_fake_provenance()
        id: int = provenance.id

        response = self.client.get(reverse("provenance-json-export", args=[id]))
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response, JsonResponse)

    def test_keys(self):
        provenance: Provenance = make_fake_provenance()
        id: int = provenance.id

        response = self.client.get(reverse("provenance-json-export", args=[id]))
        response_json: dict = response.json()
        response_keys = response_json.keys()

        expected_keys = [
            "id",
            "name",
            "date_created",
            "date_updated",
            "created_by",
            "last_updated_by",
        ]
        for key in expected_keys:
            with self.subTest(key=key):
                self.assertIn(key, response_keys)


class JsonSourcesExportTest(TestCase):
    def setUp(self):
        # the JsonSourcesExport View uses the CANTUS Segment's .source_set property,
        # so we need to make sure to set up a CANTUS segment with the right ID for each test.
        self.cantus_segment = make_fake_segment(
            id="4063", name="Bower Sequence Database"
        )
        self.bower_segment = make_fake_segment(id="4064", name="CANTUS Database")

    def test_json_sources_response(self):
        source = make_fake_source(published=True, segment=self.cantus_segment)

        response_1 = self.client.get(f"/json-sources/")
        self.assertEqual(response_1.status_code, 200)
        self.assertIsInstance(response_1, JsonResponse)

        response_2 = self.client.get(reverse("json-sources-export"))
        self.assertEqual(response_2.status_code, 200)
        self.assertIsInstance(response_2, JsonResponse)

    def test_json_sources_format(self):
        NUMBER_OF_SOURCES = 10
        sample_source = None
        for _ in range(NUMBER_OF_SOURCES):
            sample_source = make_fake_source(
                published=True, segment=self.cantus_segment
            )

        # there should be one item for each source
        response = self.client.get(reverse("json-sources-export"))
        unpacked_response = json.loads(response.content)
        self.assertEqual(len(unpacked_response), NUMBER_OF_SOURCES)

        # for each item, the key should be the source's id and the value should be
        # a nested dictionary with a single key: "csv"
        sample_id = str(sample_source.id)
        self.assertIn(sample_id, unpacked_response.keys())
        sample_item = unpacked_response[sample_id]
        sample_item_keys = list(sample_item.keys())
        self.assertEqual(sample_item_keys, ["csv"])

        # the single value should be a link in form `cantusdatabase.com/csv/{source.id}`
        expected_substring = f"source/{sample_id}/csv"
        sample_item_value = list(sample_item.values())[0]
        self.assertIn(expected_substring, sample_item_value)

    def test_json_sources_published_vs_unpublished(self):
        NUM_PUBLISHED_SOURCES = 3
        NUM_UNPUBLISHED_SOURCES = 5
        for _ in range(NUM_PUBLISHED_SOURCES):
            sample_published_source = make_fake_source(
                published=True, segment=self.cantus_segment
            )
        for _ in range(NUM_UNPUBLISHED_SOURCES):
            sample_unpublished_source = make_fake_source(
                published=False, segment=self.cantus_segment
            )

        response = self.client.get(reverse("json-sources-export"))
        unpacked_response = json.loads(response.content)
        response_keys = unpacked_response.keys()
        self.assertEqual(len(unpacked_response), NUM_PUBLISHED_SOURCES)

        published_id = str(sample_published_source.id)
        unpublished_id = str(sample_unpublished_source.id)
        self.assertIn(published_id, response_keys)
        self.assertNotIn(unpublished_id, response_keys)

    def test_only_sources_from_cantus_segment_appear_in_results(self):
        NUM_CANTUS_SOURCES = 5
        NUM_BOWER_SOURCES = 7
        for _ in range(NUM_CANTUS_SOURCES):
            sample_cantus_source = make_fake_source(
                published=True, segment=self.cantus_segment
            )
        for _ in range(NUM_BOWER_SOURCES):
            sample_bower_source = make_fake_source(
                published=True, segment=self.bower_segment
            )

        response = self.client.get(reverse("json-sources-export"))
        unpacked_response = json.loads(response.content)
        response_keys = unpacked_response.keys()
        self.assertEqual(len(unpacked_response), NUM_CANTUS_SOURCES)

        cantus_id = str(sample_cantus_source.id)
        bower_id = str(sample_bower_source.id)
        self.assertIn(cantus_id, response_keys)
        self.assertNotIn(bower_id, response_keys)


class JsonNextChantsTest(TestCase):
    def test_existing_cantus_id(self):
        fake_source_1 = make_fake_source()
        fake_source_2 = make_fake_source()

        fake_chant_2 = Chant.objects.create(
            source=fake_source_1,
            cantus_id="2000",
            folio="001r",
            c_sequence=2,
        )

        fake_chant_1 = Chant.objects.create(
            source=fake_source_1,
            cantus_id="1000",
            folio="001r",
            c_sequence=1,
            next_chant=fake_chant_2,
        )

        fake_chant_4 = Chant.objects.create(
            source=fake_source_2,
            cantus_id="2000",
            folio="001r",
            c_sequence=2,
        )

        fake_chant_3 = Chant.objects.create(
            source=fake_source_2,
            cantus_id="1000",
            folio="001r",
            c_sequence=1,
            next_chant=fake_chant_4,
        )

        path = reverse("json-nextchants", args=["1000"])
        response = self.client.get(path)
        self.assertIsInstance(response, JsonResponse)
        unpacked_response = json.loads(response.content)
        self.assertEqual(unpacked_response, {"2000": 2})

    def test_nonexistent_cantus_id(self):
        fake_source_1 = make_fake_source()
        fake_source_2 = make_fake_source()

        fake_chant_2 = Chant.objects.create(
            source=fake_source_1,
        )
        fake_chant_1 = Chant.objects.create(
            source=fake_source_1, next_chant=fake_chant_2
        )

        fake_chant_4 = Chant.objects.create(
            source=fake_source_2,
        )
        fake_chant_3 = Chant.objects.create(
            source=fake_source_2, next_chant=fake_chant_4
        )

        path = reverse("json-nextchants", args=["9000"])
        response = self.client.get(reverse("json-nextchants", args=["9000"]))
        self.assertIsInstance(response, JsonResponse)
        unpacked_response = json.loads(response.content)
        self.assertEqual(unpacked_response, {})

    def test_published_vs_unpublished(self):
        fake_source_1 = make_fake_source(published=True)
        fake_source_2 = make_fake_source(published=False)

        fake_chant_2 = Chant.objects.create(
            source=fake_source_1,
            cantus_id="2000",
            folio="001r",
            c_sequence=2,
        )

        fake_chant_1 = Chant.objects.create(
            source=fake_source_1,
            cantus_id="1000",
            folio="001r",
            c_sequence=1,
            next_chant=fake_chant_2,
        )

        fake_chant_4 = Chant.objects.create(
            source=fake_source_2,
            cantus_id="2000",
            folio="001r",
            c_sequence=2,
        )

        fake_chant_3 = Chant.objects.create(
            source=fake_source_2,
            cantus_id="1000",
            folio="001r",
            c_sequence=1,
            next_chant=fake_chant_4,
        )

        path = reverse("json-nextchants", args=["1000"])
        response_1 = self.client.get(path)
        self.assertIsInstance(response_1, JsonResponse)
        unpacked_response_1 = json.loads(response_1.content)
        self.assertEqual(unpacked_response_1, {"2000": 1})

        fake_source_2.published = True
        fake_source_2.save()
        response_2 = self.client.get(path)
        self.assertIsInstance(response_2, JsonResponse)
        unpacked_response_2 = json.loads(response_2.content)
        self.assertEqual(unpacked_response_2, {"2000": 2})


class JsonCidTest(TestCase):
    def test_published_vs_unpublished(self):
        published_source = make_fake_source(published=True)
        published_chant = make_fake_chant(
            cantus_id="123.publ",
            source=published_source,
        )
        pub_response = self.client.get(
            reverse("json-cid-export", args=["123.publ"]),
        )
        pub_json = pub_response.json()
        pub_chants = pub_json["chants"]
        self.assertEqual(len(pub_chants), 1)

        unpublished_source = make_fake_source(published=False)
        unpublished_chant = make_fake_chant(
            cantus_id="456.unpub",
            source=unpublished_source,
        )
        unpub_response = self.client.get(
            reverse("json-cid-export", args=["456.unpub"]),
        )
        unpub_json = unpub_response.json()
        unpub_chants = unpub_json["chants"]
        self.assertEqual(len(unpub_chants), 0)

    def test_chant_vs_sequence(self):
        chant = make_fake_chant(cantus_id="123456")
        response_1 = self.client.get(
            reverse("json-cid-export", args=["123456"]),
        )
        json_1 = response_1.json()
        chants_1 = json_1["chants"]
        self.assertEqual(len(chants_1), 1)

        sequence = make_fake_sequence(cantus_id="123456")
        response_2 = self.client.get(
            reverse("json-cid-export", args=["123456"]),
        )
        json_2 = response_2.json()
        chants_2 = json_2["chants"]
        self.assertEqual(
            len(chants_2), 1
        )  # should return the chant, but not the sequence

        chant.delete()
        response_3 = self.client.get(
            reverse("json-cid-export", args=["123456"]),
        )
        json_3 = response_3.json()
        chants_3 = json_3["chants"]
        self.assertEqual(len(chants_3), 0)  # should not return the sequence

    def test_structure(self):
        """
        should be structured thus:
        {
            "chants": [
                "chant": {
                    "siglum": "some string"
                    "srclink": "some string"
                    "chantlink": "some string"
                    "folio": "some string"
                    "sequence": some_integer
                    "incipit": "some string"
                    "feast": "some string"
                    "genre": "some string"
                    "office": "some string"
                    "position": "some string"
                    "cantus_id": "some string"
                    "image": "some string"
                    "mode": "some string"
                    "full_text": "some string"
                    "melody": "some string"
                    "db": "CD"
                },
                "chant": {
                    etc.
                },
            ]
        }
        A more complete specification can be found at
        https://github.com/DDMAL/CantusDB/issues/1170.
        """
        for _ in range(7):
            make_fake_chant(cantus_id="3.14159")
        response = self.client.get(
            reverse("json-cid-export", args=["3.14159"]),
        )
        json_obj = response.json()
        json_keys = json_obj.keys()
        self.assertEqual(list(json_keys), ["chants"])

        chants = json_obj["chants"]
        self.assertIsInstance(chants, list)
        self.assertEqual(len(chants), 7)

        first_item = chants[0]
        item_keys = first_item.keys()
        self.assertIsInstance(first_item, dict)
        self.assertEqual(list(item_keys), ["chant"])

        first_chant = first_item["chant"]
        chant_keys = first_chant.keys()
        expected_keys = {
            "siglum",
            "srclink",
            "chantlink",
            "folio",
            "sequence",
            "incipit",
            "feast",
            "genre",
            "office",
            "position",
            "cantus_id",
            "image",
            "mode",
            "full_text",
            "melody",
            "db",
        }
        self.assertEqual(set(chant_keys), expected_keys)

    def test_values(self):
        chant = make_fake_chant(cantus_id="100000")
        chant.refresh_from_db()  # incipit is automatically calculated from fulltext
        # on chant save; refreshing from DB allows us to compare the value to what we see in
        # the results.

        expected_values = {
            "siglum": chant.source.siglum,
            "srclink": f"http://testserver/source/{chant.source.id}",
            "chantlink": f"http://testserver/chant/{chant.id}",
            "folio": chant.folio,
            "sequence": chant.c_sequence,
            "incipit": chant.incipit,
            "feast": chant.feast.name,
            "genre": chant.genre.name,
            "office": chant.office.name,
            "position": chant.position,
            "mode": chant.mode,
            "image": chant.image_link,
            "melody": chant.volpiano,
            "full_text": chant.manuscript_full_text_std_spelling,
            "db": "CD",
        }
        response_1 = self.client.get(
            reverse("json-cid-export", args=["100000"]),
        )
        json_for_one_chant_1 = response_1.json()["chants"][0]["chant"]
        for key in expected_values.keys():
            self.assertEqual(expected_values[key], json_for_one_chant_1[key])

        chant.manuscript_full_text = None
        chant.manuscript_full_text_std_spelling = None
        chant.folio = None
        chant.incipit = None
        chant.feast = None
        chant.genre = None
        chant.office = None
        chant.position = None
        chant.mode = None
        chant.image_link = None
        chant.volpiano = None
        chant.manuscript_full_text_std_spelling = None
        chant.save()

        response_2 = self.client.get(
            reverse("json-cid-export", args=["100000"]),
        )
        json_for_one_chant_2 = response_2.json()["chants"][0]["chant"]

        sequence_value = json_for_one_chant_2.pop("sequence")
        self.assertIsInstance(sequence_value, int)

        for key, value in json_for_one_chant_2.items():
            with self.subTest(key=key):
                self.assertIsInstance(
                    value,
                    str,  # we've already removed ["sequence"], which should
                    # be an int. All other keys should be strings, and there should
                    # be no Nones or nulls
                )

        chant.manuscript_full_text = "nahn-staendrd spillynge"
        chant.manuscript_full_text_std_spelling = "standard spelling"
        chant.save()
        response_3 = self.client.get(
            reverse("json-cid-export", args=["100000"]),
        )
        json_for_one_chant_3 = response_3.json()["chants"][0]["chant"]
        self.assertEqual(json_for_one_chant_3["full_text"], "standard spelling")


class CsvExportTest(TestCase):
    def test_url(self):
        source = make_fake_source(published=True)
        response_1 = self.client.get(reverse("csv-export", args=[source.id]))
        self.assertEqual(response_1.status_code, 200)

    def test_content(self):
        NUM_CHANTS = 5
        source = make_fake_source(published=True)
        for _ in range(NUM_CHANTS):
            make_fake_chant(source=source)
        response = self.client.get(reverse("csv-export", args=[source.id]))
        content = response.content.decode("utf-8")
        split_content = list(csv.reader(content.splitlines(), delimiter=","))
        header, rows = split_content[0], split_content[1:]

        expected_column_titles = [
            "siglum",
            "marginalia",
            "folio",
            "sequence",
            "incipit",
            "feast",
            "office",
            "genre",
            "position",
            "cantus_id",
            "mode",
            "finalis",
            "differentia",
            "differentiae_database",
            "fulltext_standardized",
            "fulltext_ms",
            "volpiano",
            "image_link",
            "melody_id",
            "addendum",
            "extra",
            "node_id",
        ]
        for t in expected_column_titles:
            self.assertIn(t, header)

        self.assertEqual(len(rows), NUM_CHANTS)
        for row in rows:
            self.assertEqual(len(header), len(row))

    def test_published_vs_unpublished(self):
        published_source = make_fake_source(published=True)
        response_1 = self.client.get(reverse("csv-export", args=[published_source.id]))
        self.assertEqual(response_1.status_code, 200)
        unpublished_source = make_fake_source(published=False)
        response_2 = self.client.get(
            reverse("csv-export", args=[unpublished_source.id])
        )
        self.assertEqual(response_2.status_code, 403)

    def test_csv_export_on_source_with_sequences(self):
        NUM_SEQUENCES = 5
        bower_segment = make_fake_segment(name="Bower Sequence Database")
        bower_segment.id = 4064
        bower_segment.save()
        source = make_fake_source(published=True)
        source.segment = bower_segment
        for _ in range(NUM_SEQUENCES):
            make_fake_sequence(source=source)
        response = self.client.get(reverse("csv-export", args=[source.id]))
        content = response.content.decode("utf-8")
        split_content = list(csv.reader(content.splitlines(), delimiter=","))
        header, rows = split_content[0], split_content[1:]

        self.assertEqual(len(rows), NUM_SEQUENCES)
        for row in rows:
            self.assertEqual(len(header), len(row))
            self.assertNotEqual(
                row[3], ""
            )  # ensure that the .s_sequence field is being written to the "sequence" column


class ChangePasswordViewTest(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create(email="test@test.com")
        self.user.set_password("pass")
        self.user.save()
        self.client.login(email="test@test.com", password="pass")

    def test_url_and_templates(self):
        response_1 = self.client.get(reverse("change-password"))
        self.assertEqual(response_1.status_code, 200)
        self.assertTemplateUsed(response_1, "base.html")
        self.assertTemplateUsed(response_1, "registration/change_password.html")
        response_2 = self.client.get("/change-password/")
        self.assertEqual(response_2.status_code, 200)
        self.assertTemplateUsed(response_2, "base.html")
        self.assertTemplateUsed(response_2, "registration/change_password.html")

    def test_change_password(self):
        response_1 = self.client.post(
            reverse("change-password"),
            {
                "old_password": "pass",
                "new_password1": "updated_pass",
                "new_password2": "updated_pass",
            },
        )
        self.assertEqual(response_1.status_code, 200)
        self.client.logout()
        self.client.login(email="test@test.com", password="updated_pass")
        response_2 = self.client.get(reverse("change-password"))
        self.assertEqual(
            response_2.status_code, 200
        )  # if login failed, status code will be 302


class NodeURLRedirectTest(TestCase):
    def setUp(self):
        self.client = Client()

    def test_chant_redirect(self):
        # generate dummy object with ID in valid range
        example_chant_id = random.randrange(1, 1000000)
        source = make_fake_source()
        Chant.objects.create(id=example_chant_id, source=source)

        # find dummy object using /node/ path
        response_1 = self.client.get(
            reverse("redirect-node-url", args=[example_chant_id])
        )
        expected_url = reverse("chant-detail", args=[example_chant_id])

        self.assertEqual(response_1.status_code, 302)
        self.assertEqual(response_1.url, expected_url)

    def test_source_redirect(self):
        # generate dummy object with ID in valid range
        example_source_id = random.randrange(1, 1000000)
        source_1 = make_fake_source()
        source_1.id = example_source_id
        source_1.save()

        # find dummy object using /node/ path
        response_1 = self.client.get(
            reverse("redirect-node-url", args=[example_source_id])
        )
        expected_url = reverse("source-detail", args=[example_source_id])

        self.assertEqual(response_1.status_code, 302)
        self.assertEqual(response_1.url, expected_url)

    def test_sequence_redirect(self):
        # generate dummy object with ID in valid range
        example_sequence_id = random.randrange(1, 1000000)
        source = make_fake_source()
        Sequence.objects.create(id=example_sequence_id, source=source)

        # find dummy object using /node/ path
        response_1 = self.client.get(
            reverse("redirect-node-url", args=[example_sequence_id])
        )
        expected_url = reverse("sequence-detail", args=[example_sequence_id])

        self.assertEqual(response_1.status_code, 302)
        self.assertEqual(response_1.url, expected_url)

    def test_article_redirect(self):
        # generate dummy object with ID in valid range
        example_article_id = random.randrange(1, 1000000)
        article_1 = make_fake_article()
        article_1.id = example_article_id
        article_1.save()

        # find dummy object using /node/ path
        response_1 = self.client.get(
            reverse("redirect-node-url", args=[example_article_id])
        )
        expected_url = reverse("article-detail", args=[example_article_id])

        self.assertEqual(response_1.status_code, 302)
        self.assertEqual(response_1.url, expected_url)

    def test_indexer_redirect(self):
        # generate dummy object with ID in valid range
        example_indexer_id = random.randrange(1, 1000000)
        example_matching_user_id = random.randrange(1, 1000000)
        User.objects.create(
            id=example_matching_user_id, old_indexer_id=example_indexer_id
        )

        # find dummy object using /node/ path
        response_1 = self.client.get(
            reverse("redirect-node-url", args=[example_indexer_id])
        )
        expected_url = reverse("user-detail", args=[example_matching_user_id])

        self.assertEqual(response_1.status_code, 302)
        self.assertEqual(response_1.url, expected_url)

    def test_bad_redirect(self):
        invalid_node_id = random.randrange(1, 1000000)

        # try to find object that doesn't exist
        response_1 = self.client.get(
            reverse("redirect-node-url", args=[invalid_node_id])
        )
        self.assertEqual(response_1.status_code, 404)

    def test_redirect_above_limit(self):
        # generate dummy object with ID outside of valid range
        over_limit_node_id = 1000001
        source = make_fake_source()
        Chant.objects.create(id=over_limit_node_id, source=source)

        # ID above limit
        response_1 = self.client.get(
            reverse("redirect-node-url", args=[over_limit_node_id])
        )
        self.assertEqual(response_1.status_code, 404)


class IndexerRedirectTest(TestCase):
    def setUp(self):
        self.client = Client()

    def test_indexer_redirect_good(self):
        # generate dummy object
        example_indexer_id = random.randrange(1, 1000000)
        example_matching_user_id = random.randrange(1, 1000000)
        User.objects.create(
            id=example_matching_user_id, old_indexer_id=example_indexer_id
        )

        # find dummy object using /indexer/ path
        response_1 = self.client.get(
            reverse("redirect-indexer", args=[example_indexer_id])
        )
        expected_url = reverse("user-detail", args=[example_matching_user_id])

        self.assertEqual(response_1.status_code, 302)
        self.assertEqual(response_1.url, expected_url)

    def test_indexer_redirect_bad(self):
        example_bad_indexer_id = random.randrange(1, 1000000)
        response_1 = self.client.get(
            reverse("redirect-indexer", args=[example_bad_indexer_id])
        )
        self.assertEqual(response_1.status_code, 404)


class DocumentRedirectTest(TestCase):
    def setUp(self):
        self.client = Client()

    def test_document_redirects(self):
        old_document_paths = (
            "/sites/default/files/documents/1. Quick Guide to Liturgy.pdf",
            "/sites/default/files/documents/2. Volpiano Protocols.pdf",
            "/sites/default/files/documents/3. Volpiano Neumes for Review.docx",
            "/sites/default/files/documents/4. Volpiano Neume Protocols.pdf",
            "/sites/default/files/documents/5. Volpiano Editing Guidelines.pdf",
            "/sites/default/files/documents/7. Guide to Graduals.pdf",
            "/sites/default/files/HOW TO - manuscript descriptions-Nov6-20.pdf",
        )
        for path in old_document_paths:
            # each path should redirect to the new path
            response = self.client.get(path)
            self.assertEqual(response.status_code, 302)
            # In Aug 2023, Jacob struggled to get the following lines to work -
            # I was getting 404s when I expected 200s. This final step would be nice
            # to test properly - if a future developer who is cleverer than me can
            # get this working, that would be excellent!

            # redirect_url = response.url
            # followed_response = self.client.get(redirect_url)
            # self.assertEqual(followed_response.status_code, 200)


class ContentOverviewTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        Group.objects.create(name="project manager")

    def setUp(self):
        self.user = get_user_model().objects.create(email="test@test.com")
        self.user.set_password("pass")
        self.user.save()
        self.client = Client()

        project_manager = Group.objects.get(name="project manager")
        project_manager.user_set.add(self.user)
        self.client.login(email="test@test.com", password="pass")

    def test_templates_used(self):
        response = self.client.get(reverse("content-overview"))
        self.assertTemplateUsed(response, "base.html")
        self.assertTemplateUsed(response, "content_overview.html")

    def test_project_manager_permission(self):
        response = self.client.get(reverse("content-overview"))
        self.assertEqual(response.status_code, 200)

    def test_content_overview_view_with_login_required(self):
        self.client.logout()
        response = self.client.get(reverse("content-overview"))
        self.assertRedirects(response, "/login/?next=/content-overview/")

    def test_content_overview_view_for_non_project_manager(self):
        user = get_user_model().objects.create(email="non_project_manager@test.com")
        user.set_password("pass")
        user.save()
        self.client.login(email="non_project_manager@test.com", password="pass")

        response = self.client.get(reverse("content-overview"))
        self.assertEqual(response.status_code, 403)

    def test_content_overview_view_selected_model(self):
        response = self.client.get(reverse("content-overview"), {"model": "sources"})
        self.assertEqual(response.status_code, 200)

        self.assertIsNotNone(response.context["models"])
        models = response.context["models"]
        self.assertIsNotNone(response.context["page_obj"])
        page_obj = response.context["page_obj"]
        self.assertEqual(response.context["selected_model_name"], "sources")

    def test_source_selected_model(self):
        source = make_fake_source(title="Test Source")
        chant = make_fake_chant()
        response = self.client.get(reverse("content-overview"), {"model": "sources"})
        self.assertContains(response, f"<b>Sources</b>", html=True)
        self.assertContains(
            response,
            f'<a href="?model=chants">Chants</a>',
            html=True,
        )
        self.assertContains(response, "Test Source", html=True)
        self.assertNotContains(response, "Test Chant", html=True)

    def test_chant_selected_model(self):
        source = make_fake_source(title="Test Source")
        chant = make_fake_chant(manuscript_full_text_std_spelling="Test Chant")
        response = self.client.get(reverse("content-overview"), {"model": "chants"})
        self.assertContains(response, f"<b>Chants</b>", html=True)
        self.assertContains(
            response,
            f'<a href="?model=sources">Sources</a>',
            html=True,
        )
        self.assertContains(response, "Test Chant", html=True)
        self.assertNotContains(response, "Test Source", html=True)


class AutocompleteViewsTest(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create(email="test@test.com")
        self.user.set_password("pass")
        self.user.save()
        self.client = Client()
        self.client.login(email="test@test.com", password="pass")

    @classmethod
    def setUpTestData(cls):
        Group.objects.create(name="editor")
        u1 = get_user_model().objects.create(email="hello@test.com")
        u2 = get_user_model().objects.create(full_name="Lucas")
        editor = Group.objects.get(name="editor")
        editor.user_set.add(u1)

        for i in range(10):
            make_fake_century()

    def test_current_editors_autocomplete(self):
        response = self.client.get(reverse("current-editors-autocomplete"))
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertEqual(len(data["results"]), 1)

    def test_all_users_autocomplete(self):
        response = self.client.get(reverse("all-users-autocomplete"))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["results"]), 3)

        response2 = self.client.get(reverse("all-users-autocomplete"), {"q": "L"})
        self.assertEqual(response2.status_code, 200)
        data = response2.json()
        self.assertEqual(len(data["results"]), 1)

    def test_century_autocomplete(self):
        response = self.client.get(reverse("century-autocomplete"))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["results"]), 10)

    def test_non_authenticated_user(self):
        self.client.logout()
        response = self.client.get(reverse("current-editors-autocomplete"))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["results"]), 0)

        response = self.client.get(reverse("all-users-autocomplete"))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["results"]), 0)

        response = self.client.get(reverse("century-autocomplete"))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["results"]), 0)


class AjaxSearchBarTest(TestCase):
    def test_response(self):
        chant = make_fake_chant()
        chant.refresh_from_db()  # incipit is automatically calculated from fulltext
        # on chant save; refreshing from DB allows us to compare the value to what we see in
        # the results.
        cantus_id = chant.cantus_id

        response = self.client.get(reverse("ajax-search-bar", args=[cantus_id]))
        self.assertEqual(response.status_code, 200)

        content = json.loads(response.content)
        self.assertIsInstance(content, dict)

        content_chants = content["chants"]
        self.assertIsInstance(content_chants, list)

        content_chant = content_chants[0]
        expected_keys_and_values = {
            "incipit": chant.incipit,
            "genre__name": chant.genre.name,
            "feast__name": chant.feast.name,
            "cantus_id": chant.cantus_id,
            "mode": chant.mode,
            "source__siglum": chant.source.siglum,
            "folio": chant.folio,
            "c_sequence": chant.c_sequence,
            "chant_link": reverse("chant-detail", args=[chant.id]),
        }
        for key, expected_value in expected_keys_and_values.items():
            with self.subTest(key=key):
                observed_value = content_chant[key]
                self.assertEqual(expected_value, observed_value)

    def test_incipit_search(self):
        unremarkable_chant = make_fake_chant(
            manuscript_full_text_std_spelling=(
                "The fulltext contains no "
                "numbers no asterisks and no punctuation "
                "and is thus completely normal"
            )
        )
        chant_with_asterisk = make_fake_chant(
            manuscript_full_text_std_spelling="few words*"
        )

        istartswith_search_term = "the fulltext"
        istartswith_response = self.client.get(
            reverse("ajax-search-bar", args=[istartswith_search_term])
        )
        istartswith_content = json.loads(istartswith_response.content)
        istartswith_chants = istartswith_content["chants"]
        self.assertEqual(len(istartswith_chants), 1)
        istartswith_chant = istartswith_chants[0]
        self.assertEqual(istartswith_chant["id"], unremarkable_chant.id)

        # we should only find chants that begin with the search term
        icontains_search_term = "contains no"
        icontains_response = self.client.get(
            reverse("ajax-search-bar", args=[icontains_search_term])
        )
        icontains_content = json.loads(icontains_response.content)
        icontains_chants = icontains_content["chants"]
        self.assertEqual(len(icontains_chants), 0)

        # the search bar should only switch to a Cantus ID search when
        # there are numerals present. Special characters like asterisks
        # may occur in chant texts, and should still be treated as
        # incipit searches
        asterisk_search_term = "few words*"
        asterisk_response = self.client.get(
            reverse("ajax-search-bar", args=[asterisk_search_term])
        )
        asterisk_content = json.loads(asterisk_response.content)
        asterisk_chants = asterisk_content["chants"]
        self.assertEqual(len(asterisk_chants), 1)
        asterisk_chant = asterisk_chants[0]
        self.assertEqual(asterisk_chant["id"], chant_with_asterisk.id)

    def test_cantus_id_search(self):
        chant_with_normal_cantus_id = make_fake_chant(
            cantus_id="012345",
            manuscript_full_text_std_spelling="This fulltext contains no numerals",
        )
        chant_with_numerals_in_incipit = make_fake_chant(
            cantus_id="123456",
            manuscript_full_text_std_spelling="0 me! 0 my! This is unexpected!",
        )

        # for search terms that contain numerals, we should only return
        # matches with the cantus_id field, and not the incipit field
        matching_search_term = "0"
        matching_response = self.client.get(
            reverse("ajax-search-bar", args=[matching_search_term])
        )
        matching_content = json.loads(matching_response.content)
        matching_chants = matching_content["chants"]
        self.assertEqual(len(matching_chants), 1)
        matching_chant = matching_chants[0]
        matching_id = matching_chant["id"]
        self.assertEqual(matching_id, chant_with_normal_cantus_id.id)
        self.assertNotEqual(matching_id, chant_with_numerals_in_incipit.id)

        # we should only return istartswith results, and not icontains results
        non_matching_search_term = "2"
        non_matching_response = self.client.get(
            reverse("ajax-search-bar", args=[non_matching_search_term])
        )
        non_matching_content = json.loads(non_matching_response.content)
        non_matching_chants = non_matching_content["chants"]
        self.assertEqual(len(non_matching_chants), 0)
