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
import csv

from faker import Faker

from users.models import User
from .make_fakes import (
    make_fake_century,
    make_fake_chant,
    make_fake_feast,
    make_fake_genre,
    make_fake_office,
    make_fake_provenance,
    make_fake_rism_siglum,
    make_fake_segment,
    make_fake_sequence,
    make_fake_source,
    make_fake_volpiano,
    make_random_string,
)

from main_app.models import Century
from main_app.models import Chant
from main_app.models import Feast
from main_app.models import Genre
from main_app.models import Office
from main_app.models import Segment
from main_app.models import Sequence
from main_app.models import Source

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
        response = self.client.get(f"/chant-create/{source.id}")
        self.assertRedirects(response, f"/login/?next=/chant-create/{source.id}")

        # ChantDeleteView
        response = self.client.get(f"/chant-delete/{chant.id}")
        self.assertRedirects(response, f"/login/?next=/chant-delete/{chant.id}")

        # SourceEditChantsView
        response = self.client.get(f"/edit-chants/{source.id}")
        self.assertRedirects(response, f"/login/?next=/edit-chants/{source.id}")

        # SequenceEditView
        response = self.client.get(f"/edit-sequence/{sequence.id}")
        self.assertRedirects(response, f"/login/?next=/edit-sequence/{sequence.id}")

        # SourceCreateView
        response = self.client.get("/source-create/")
        self.assertRedirects(response, "/login/?next=/source-create/")

        # SourceEditView
        response = self.client.get(f"/edit-source/{source.id}")
        self.assertRedirects(response, f"/login/?next=/edit-source/{source.id}")

        # UserSourceListView
        response = self.client.get("/my-sources/")
        self.assertRedirects(response, "/login/?next=/my-sources/")

        # UserListView
        response = self.client.get("/users/")
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
        response = self.client.get(f"/chant-create/{source.id}")
        self.assertEqual(response.status_code, 200)

        # ChantDeleteView
        response = self.client.get(f"/chant-delete/{chant.id}")
        self.assertEqual(response.status_code, 200)

        # SourceEditChantsView
        response = self.client.get(f"/edit-chants/{source.id}")
        self.assertEqual(response.status_code, 200)

        # SequenceEditView
        response = self.client.get(f"/edit-sequence/{sequence.id}")
        self.assertEqual(response.status_code, 200)

        # SourceCreateView
        response = self.client.get("/source-create/")
        self.assertEqual(response.status_code, 200)

        # SourceEditView
        response = self.client.get(f"/edit-source/{source.id}")
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
        response = self.client.get(f"/chant-create/{restricted_source.id}")
        self.assertEqual(response.status_code, 403)

        response = self.client.get(f"/chant-create/{source_created_by_contributor.id}")
        self.assertEqual(response.status_code, 200)

        response = self.client.get(f"/chant-create/{assigned_source.id}")
        self.assertEqual(response.status_code, 200)

        # ChantDeleteView
        response = self.client.get(f"/chant-delete/{restricted_chant.id}")
        self.assertEqual(response.status_code, 403)

        response = self.client.get(
            f"/chant-delete/{chant_in_source_created_by_contributor.id}"
        )
        self.assertEqual(response.status_code, 200)

        response = self.client.get(f"/chant-delete/{chant_in_assigned_source.id}")
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
        response = self.client.get(f"/chant-delete/{restricted_chant.id}")
        self.assertEqual(response.status_code, 403)

        response = self.client.get(
            f"/chant-delete/{chant_in_source_created_by_contributor.id}"
        )
        self.assertEqual(response.status_code, 200)

        response = self.client.get(f"/chant-delete/{chant_in_assigned_source.id}")
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
        response = self.client.get(f"/chant-delete/{chant.id}")
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
        response = self.client.get(reverse("chant-list"), {"source": source.id})
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "base.html")
        self.assertTemplateUsed(response, "chant_list.html")

    def test_published_vs_unpublished(self):
        cantus_segment = make_fake_segment(id=4063)

        published_source = make_fake_source(segment=cantus_segment, published=True)
        response_1 = self.client.get(
            reverse("chant-list"), {"source": published_source.id}
        )
        self.assertEqual(response_1.status_code, 200)

        unpublished_source = make_fake_source(segment=cantus_segment, published=False)
        response_2 = self.client.get(
            reverse("chant-list"), {"source": unpublished_source.id}
        )
        self.assertEqual(response_2.status_code, 403)

    def test_visibility_by_segment(self):
        cantus_segment = make_fake_segment(id=4063)
        cantus_source = make_fake_source(segment=cantus_segment, published=True)
        response_1 = self.client.get(
            reverse("chant-list"), {"source": cantus_source.id}
        )
        self.assertEqual(response_1.status_code, 200)

        bower_segment = make_fake_segment(id=4064)
        bower_source = make_fake_source(segment=bower_segment, published=True)
        response_1 = self.client.get(reverse("chant-list"), {"source": bower_source.id})
        self.assertEqual(response_1.status_code, 404)

    def test_filter_by_source(self):
        cantus_segment = make_fake_segment(id=4063)
        source = make_fake_source(segment=cantus_segment)
        another_source = make_fake_source(segment=cantus_segment)
        chant_in_source = Chant.objects.create(source=source)
        chant_in_another_source = Chant.objects.create(source=another_source)
        response = self.client.get(reverse("chant-list"), {"source": source.id})
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
            reverse("chant-list"), {"source": source.id, "feast": feast.id}
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
            reverse("chant-list"), {"source": source.id, "genre": genre.id}
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
            reverse("chant-list"), {"source": source.id, "folio": "001r"}
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
            reverse("chant-list"), {"source": source.id, "search_text": search_term}
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
            reverse("chant-list"), {"source": source.id, "search_text": search_term}
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
            reverse("chant-list"), {"source": source.id, "search_text": search_term}
        )
        self.assertIn(chant, response.context["chants"])

    def test_context_source(self):
        cantus_segment = make_fake_segment(id=4063)
        source = make_fake_source(segment=cantus_segment)
        response = self.client.get(reverse("chant-list"), {"source": source.id})
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
        response = self.client.get(reverse("chant-list"), {"source": source.id})
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
        response = self.client.get(reverse("chant-list"), {"source": source.id})
        # context "feasts_with_folios" is a list of tuples
        # it records the folios where the feast changes
        expected_result = [("001r", feast_1), ("001v", feast_2), ("002r", feast_1)]
        self.assertEqual(response.context["feasts_with_folios"], expected_result)


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
        search_term = get_random_search_term(office.name)
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

    def test_order_by_siglum(self):
        source_1 = make_fake_source(published=True, siglum="sigl-1")
        chant_1 = make_fake_chant(incipit="thing 1", source=source_1)
        source_2 = make_fake_source(published=True, siglum="sigl-2")
        chant_2 = make_fake_chant(incipit="thing 2", source=source_2)

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
        first_result_incipit = descending_results[1]["incipit"]
        self.assertEqual(first_result_incipit, chant_1.incipit)
        last_result_incipit = descending_results[0]["incipit"]
        self.assertEqual(last_result_incipit, chant_2.incipit)

    def test_order_by_incipit(self):
        pass

    def test_order_by_office(self):
        pass

    def test_order_by_genre(self):
        pass

    def test_order_by_cantus_id(self):
        pass

    def test_order_by_mode(self):
        pass

    def test_order_by_ms_fulltext(self):
        pass

    def test_order_by_volpiano(self):
        pass

    def test_order_by_image_link(self):
        pass

    def test_column_header_links(self):
        pass

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
        search_term = get_random_search_term(office.name)
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


class ChantIndexViewTest(TestCase):
    def test_url_and_templates(self):
        source = make_fake_source()
        response = self.client.get(reverse("chant-index"), {"source": source.id})
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "full_index.html")

    def test_published_vs_unpublished(self):
        source = make_fake_source()

        source.published = True
        source.save()
        response = self.client.get(reverse("chant-index"), {"source": source.id})
        self.assertEqual(response.status_code, 200)

        source.published = False
        source.save()
        response = self.client.get(reverse("chant-index"), {"source": source.id})
        self.assertEqual(response.status_code, 403)

    def test_chant_source_queryset(self):
        chant_source = make_fake_source()
        chant = make_fake_chant(source=chant_source)
        response = self.client.get(reverse("chant-index"), {"source": chant_source.id})
        self.assertEqual(chant_source, response.context["source"])
        self.assertIn(chant, response.context["chants"])

    def test_sequence_source_queryset(self):
        seq_source = make_fake_source(
            segment=Segment.objects.create(id=4064, name="Clavis Sequentiarium"),
            title="a sequence source",
            published=True,
        )
        sequence = Sequence.objects.create(source=seq_source)
        response = self.client.get(reverse("chant-index"), {"source": seq_source.id})
        self.assertEqual(seq_source, response.context["source"])
        self.assertIn(sequence, response.context["chants"])

    def test_siglum_column(self):
        siglum = "Sigl-01"
        source = make_fake_source(published=True, siglum=siglum)
        source_title = source.title
        make_fake_chant(source=source)
        response = self.client.get(reverse("chant-index"), {"source": source.id})
        html = str(response.content)
        self.assertIn(siglum, html)
        self.assertIn(source_title, html)
        expected_html_substring = f'<td title="{source_title}">{siglum}</td>'
        self.assertIn(expected_html_substring, html)

    def test_marginalia_column(self):
        source = make_fake_source(published=True)
        chant = make_fake_chant(source=source)
        marginalia = chant.marginalia
        response = self.client.get(reverse("chant-index"), {"source": source.id})
        html = str(response.content)
        self.assertIn(marginalia, html)
        expected_html_substring = f"<td>{marginalia}</td>"
        self.assertIn(expected_html_substring, html)

    def test_folio_column(self):
        source = make_fake_source(published=True)
        chant = make_fake_chant(source=source)
        folio = chant.folio
        response = self.client.get(reverse("chant-index"), {"source": source.id})
        html = str(response.content)
        self.assertIn(folio, html)
        expected_html_substring = f"<td>{folio}</td>"
        self.assertIn(expected_html_substring, html)

    def test_sequence_column_for_chant_source(self):
        source = make_fake_source(published=True)
        chant = make_fake_chant(source=source)
        c_sequence = str(chant.c_sequence)
        response = self.client.get(reverse("chant-index"), {"source": source.id})
        html = str(response.content)
        self.assertIn(c_sequence, html)

    def test_sequence_column_for_sequence_source(self):
        bower_segment = Segment.objects.create(id=4064, name="Bower Sequence Database")
        source = make_fake_source(published=True, segment=bower_segment)
        sequence = make_fake_sequence(source=source)
        s_sequence = sequence.s_sequence
        response = self.client.get(reverse("chant-index"), {"source": source.id})
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
        response = self.client.get(reverse("chant-index"), {"source": source.id})
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
        response = self.client.get(reverse("chant-index"), {"source": source.id})
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
        response = self.client.get(reverse("chant-index"), {"source": source.id})
        html = str(response.content)
        self.assertIn(genre_name, html)
        self.assertIn(genre_description, html)

    def test_position_column(self):
        source = make_fake_source(published=True)
        chant = make_fake_chant(
            source=source,
        )
        position = chant.position
        response = self.client.get(reverse("chant-index"), {"source": source.id})
        html = str(response.content)
        self.assertIn(position, html)

    def test_incipit_column_for_chant_source(self):
        source = make_fake_source(published=True)
        chant = make_fake_chant(source=source)
        incipit = chant.incipit
        url = reverse("chant-detail", args=[chant.id])
        response = self.client.get(reverse("chant-index"), {"source": source.id})
        html = str(response.content)
        self.assertIn(incipit, html)
        self.assertIn(url, html)
        expected_html_substring = f'<a href="{url}" target="_blank">{incipit}</a>'
        self.assertIn(expected_html_substring, html)

    def test_incipit_column_for_sequence_source(self):
        bower_segment = Segment.objects.create(id=4064, name="Bower Sequence Database")
        source = make_fake_source(published=True, segment=bower_segment)
        sequence = make_fake_sequence(source=source)
        incipit = sequence.incipit
        url = reverse("sequence-detail", args=[sequence.id])
        response = self.client.get(reverse("chant-index"), {"source": source.id})
        html = str(response.content)
        self.assertIn(incipit, html)
        self.assertIn(url, html)
        expected_html_substring = f'<a href="{url}" target="_blank">{incipit}</a>'
        self.assertIn(expected_html_substring, html)

    def test_cantus_id_column(self):
        source = make_fake_source(published=True)
        chant = make_fake_chant(source=source)
        cantus_id = chant.cantus_id
        response = self.client.get(reverse("chant-index"), {"source": source.id})
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
        response = self.client.get(reverse("chant-index"), {"source": source.id})
        html = str(response.content)
        self.assertIn(mode, html)
        expected_html_substring = f"<td>{mode}</td>"
        self.assertIn(expected_html_substring, html)

    def test_differentia_column(self):
        source = make_fake_source(published=True)
        differentia = "this is a differentia"  # not a representative value, but
        # most differentia are one or two characters, likely to be found elsewhere
        # in the template
        make_fake_chant(
            source=source,
            differentia=differentia,
        )
        response = self.client.get(reverse("chant-index"), {"source": source.id})
        html = str(response.content)
        self.assertIn(differentia, html)
        expected_html_substring = f"<td>{differentia}</td>"
        self.assertIn(expected_html_substring, html)


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

    def test_suggest_one_folio(self):
        fake_source = make_fake_source()
        # create fake genre to match fake_chant_2
        fake_R_genre = make_fake_genre(name="R")
        fake_chant_3 = make_fake_chant(
            source=fake_source,
            cantus_id="333333",
            folio="001",
            c_sequence=3,
        )
        fake_chant_2 = make_fake_chant(
            source=fake_source,
            cantus_id="007450",  # this has to be an actual cantus ID, since
            # next_chants pulls data from CantusIndex and we'll get an empty
            # response if we use "222222" etc.
            folio="001",
            c_sequence=2,
            next_chant=fake_chant_3,
        )
        fake_chant_1 = make_fake_chant(
            source=fake_source,
            cantus_id="111111",
            folio="001",
            c_sequence=1,
            next_chant=fake_chant_2,
        )

        # create one more chant with a cantus_id that is supposed to have suggestions
        # if it has the same cantus_id as the fake_chant_1,
        # it should give a suggestion of fake_chant_2
        fake_chant_4 = make_fake_chant(
            source=fake_source,
            cantus_id="111111",
        )

        # go to the same source and access the input form
        url = reverse("chant-create", args=[fake_source.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        # only one chant, i.e. fake_chant_2, should be returned
        self.assertEqual(1, len(response.context["suggested_chants"]))
        self.assertEqual("007450", response.context["suggested_chants"][0]["cid"])
        self.assertEqual(
            fake_R_genre.id, response.context["suggested_chants"][0]["genre_id"]
        )

    def test_fake_source(self):
        """cannot go to input form with a fake source"""
        fake_source = faker.numerify(
            "#####"
        )  # there's not supposed to be 5-digits source id
        response = self.client.get(reverse("chant-create", args=[fake_source]))
        self.assertEqual(response.status_code, 404)

    def test_no_suggest(self):
        NUM_CHANTS = 3
        fake_folio = faker.numerify("###")
        source = make_fake_source()
        # create some chants in the test folio
        for i in range(NUM_CHANTS):
            fake_cantus_id = faker.numerify("######")
            make_fake_chant(
                source=source,
                folio=fake_folio,
                c_sequence=i,
                cantus_id=fake_cantus_id,
            )
        # go to the same source and access the input form
        url = reverse("chant-create", args=[source.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        # assert context previous_chant, suggested_chants
        self.assertEqual(i, response.context["previous_chant"].c_sequence)
        self.assertEqual(fake_cantus_id, response.context["previous_chant"].cantus_id)
        self.assertListEqual([], response.context["suggested_chants"])

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

    def test_provide_suggested_fulltext(self):
        source = make_fake_source()
        chant = make_fake_chant(
            source=source, manuscript_full_text_std_spelling="", cantus_id="007450"
        )
        response = self.client.get(
            reverse("source-edit-chants", args=[source.id]), {"pk": chant.id}
        )
        # expected_suggestion is copied from Cantus Index. If this test is failing,
        # it could be because the value stored in Cantus Index has changed.
        # To verify, visit http://cantusindex.org/id/007450.
        expected_suggestion = "Puer natus est nobis alleluia alleluia"
        suggested_fulltext = response.context["suggested_fulltext"]
        self.assertEqual(suggested_fulltext, expected_suggestion)

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
        chant = make_fake_chant(
            source=source, volpiano="1---f--e---f--d---e--c---d--d", incipit="dies irae"
        )
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


class ChantProofreadViewTest(TestCase):
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
        source = make_fake_source()
        source_id = source.id

        for i in range(3):
            chant = make_fake_chant(source=source, folio="001r", c_sequence=i)
            sample_folio = chant.folio
            sample_pk = chant.id
        nonexistent_folio = "001v"

        response_1 = self.client.get(f"/proofread-chant/{source_id}")
        self.assertEqual(response_1.status_code, 200)
        self.assertTemplateUsed(response_1, "base.html")
        self.assertTemplateUsed(response_1, "chant_proofread.html")

        response_2 = self.client.get(reverse("chant-proofread", args=[source_id]))
        self.assertEqual(response_2.status_code, 200)

        response_3 = self.client.get(
            f"/proofread-chant/{source_id}?folio={sample_folio}"
        )
        self.assertEqual(response_3.status_code, 200)

        response_4 = self.client.get(
            f"/proofread-chant/{source_id}?folio={nonexistent_folio}"
        )
        self.assertEqual(response_4.status_code, 404)

        response_5 = self.client.get(
            f"/proofread-chant/{source_id}?pk={sample_pk}&folio={sample_folio}"
        )
        self.assertEqual(response_5.status_code, 200)

        self.client.logout()
        response_6 = self.client.get(reverse("chant-proofread", args=[source_id]))
        self.assertEqual(response_6.status_code, 302)  # 302 Found

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
            f"/proofread-chant/{source.id}?pk={chant.id}&folio=001r",
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

    def test_chant_with_volpiano_with_no_incipit(self):
        # in the past, a Chant Proofread page will error rather than loading properly when the chant has volpiano but no fulltext/incipit
        source = make_fake_source()
        chant = make_fake_chant(
            source=source,
            volpiano="1---m---l---k---m---h",
        )
        chant.manuscript_full_text = None
        chant.manuscript_full_text_std_spelling = None
        chant.incipit = None
        chant.save()
        response = self.client.get(
            reverse("source-edit-chants", args=[source.id]), {"pk": chant.id}
        )
        self.assertEqual(response.status_code, 200)


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
        self.assertEqual(feasts.query.order_by[0], "name")

        # Empty ordering parameters in GET request should default to ordering by name
        response = self.client.get(reverse("feast-list"), {"sort_by": ""})
        self.assertEqual(response.status_code, 200)
        feasts = response.context["feasts"]
        self.assertEqual(feasts.query.order_by[0], "name")

        # Anything other than name and feast_code should default to ordering by name
        response = self.client.get(
            reverse("feast-list"), {"sort_by": make_random_string(4)}
        )
        self.assertEqual(response.status_code, 200)
        feasts = response.context["feasts"]
        self.assertEqual(feasts.query.order_by[0], "name")

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
        sequence = make_fake_sequence(incipit="test_update_sequence")
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

    def test_search_by_siglum(self):
        source = make_fake_source(
            siglum=make_random_string(6),
            published=True,
            title="title",
        )
        search_term = get_random_search_term(source.siglum)
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

    def test_search_by_description(self):
        source = make_fake_source(
            description=faker.sentence(),
            published=True,
            title="title",
        )
        search_term = get_random_search_term(source.description)
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
        self.assertRedirects(response, reverse("source-create"))

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
        chant_list_link = reverse("chant-list")

        cantus_segment = make_fake_segment(id=4063)
        cantus_source = make_fake_source(segment=cantus_segment)
        cantus_chant_list_link = chant_list_link + f"?source={cantus_source.id}"

        cantus_source_response = self.client.get(
            reverse("source-detail", args=[cantus_source.id])
        )
        cantus_source_html = str(cantus_source_response.content)
        self.assertIn(cantus_chant_list_link, cantus_source_html)

        bower_segment = make_fake_segment(id=4064)
        bower_source = make_fake_source(segment=bower_segment)
        bower_chant_list_link = chant_list_link + f"?source={bower_source.id}"
        bower_source_response = self.client.get(
            reverse("source-detail", args=[bower_source.id])
        )
        bower_source_html = str(bower_source_response.content)
        self.assertNotIn(bower_chant_list_link, bower_source_html)


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


class JsonSourcesExportTest(TestCase):
    def test_json_sources_response(self):
        source = make_fake_source(published=True)

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
            sample_source = make_fake_source(published=True)

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
            sample_published_source = make_fake_source(published=True)
        for _ in range(NUM_UNPUBLISHED_SOURCES):
            sample_unpublished_source = make_fake_source(published=False)

        response = self.client.get(reverse("json-sources-export"))
        unpacked_response = json.loads(response.content)
        response_keys = unpacked_response.keys()
        self.assertEqual(len(unpacked_response), NUM_PUBLISHED_SOURCES)

        published_id = str(sample_published_source.id)
        unpublished_id = str(sample_unpublished_source.id)
        self.assertIn(published_id, response_keys)
        self.assertNotIn(unpublished_id, response_keys)


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
                    "siglum": "some value"
                    "srclink": "some value"
                    "chantlink": "some value"
                    "folio": "some value"
                    "incipit": "some value"
                    "feast": "some value"
                    "genre": "some value"
                    "office": "some value"
                    "position": "some value"
                    "mode": "some value"
                    "image": "some value"
                    "melody": "some value"
                    "fulltext": "some value"
                    "db": "CD"
                },
                "chant": {
                    etc.
                },
            ]
        }
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
        expected_keys = [
            "siglum",
            "srclink",
            "chantlink",
            "folio",
            "incipit",
            "feast",
            "genre",
            "office",
            "position",
            "mode",
            "image",
            "melody",
            "fulltext",
            "db",
        ]
        self.assertEqual(list(chant_keys), expected_keys)

    def test_values(self):
        chant = make_fake_chant(cantus_id="100000")
        expected_values = {
            "siglum": chant.source.siglum,
            "folio": chant.folio,
            "incipit": chant.incipit,
            "feast": chant.feast.name,
            "genre": chant.genre.name,
            "office": chant.office.name,
            "position": chant.position,
            "mode": chant.mode,
            "image": chant.image_link,
            "melody": chant.volpiano,
            "fulltext": chant.manuscript_full_text_std_spelling,
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
        for item in json_for_one_chant_2.items():
            try:
                assert isinstance(item[1], str)
            except AssertionError:
                print(item)

            self.assertIsInstance(item[1], str)  # we shouldn't see any Nones or nulls

        chant.manuscript_full_text = "nahn-staendrd spillynge"
        chant.manuscript_full_text_std_spelling = "standard spelling"
        chant.save()
        response_3 = self.client.get(
            reverse("json-cid-export", args=["100000"]),
        )
        json_for_one_chant_3 = response_3.json()["chants"][0]["chant"]
        self.assertEqual(json_for_one_chant_3["fulltext"], "standard spelling")


class CISearchViewTest(TestCase):
    def test_view_url_path(self):
        fake_search_term = faker.word()
        response = self.client.get(f"/ci-search/{fake_search_term}")
        self.assertEqual(response.status_code, 200)

    def test_view_url_reverse_name(self):
        fake_search_term = faker.word()
        response = self.client.get(reverse("ci-search", args=[fake_search_term]))
        self.assertEqual(response.status_code, 200)

    def test_template_used(self):
        fake_search_term = faker.word()
        response = self.client.get(reverse("ci-search", args=[fake_search_term]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "ci_search.html")

    def test_context_returned(self):
        fake_search_term = faker.word()
        response = self.client.get(f"/ci-search/{fake_search_term}")
        self.assertTrue("results" in response.context)
        self.assertTrue("genres" in response.context)


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
            "differentia_new",
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
        Chant.objects.create(id=example_chant_id)

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
        Sequence.objects.create(id=example_sequence_id)

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
        Chant.objects.create(id=over_limit_node_id)

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
