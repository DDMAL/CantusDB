import unittest
import random
from django.urls import reverse
from django.test import TestCase
from django.http import HttpResponseNotFound
from main_app.views.feast import FeastListView
from django.http.response import JsonResponse
import json
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import Client
from django.db.models import Q
from abc import abstractmethod
from abc import ABC
import csv

from faker import Faker
from .make_fakes import (make_fake_text,
    make_fake_century,
    make_fake_chant,
    make_fake_feast,
    make_fake_genre,
    make_fake_indexer,
    make_fake_notation,
    make_fake_office,
    make_fake_provenance,
    make_fake_rism_siglum,
    make_fake_segment,
    make_fake_sequence,
    make_fake_source,
)

from main_app.models import Century
from main_app.models import Chant
from main_app.models import Feast
from main_app.models import Genre
from main_app.models import Indexer
from main_app.models import Notation
from main_app.models import Office
from main_app.models import Provenance
from main_app.models import RismSiglum
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
        self.user = get_user_model().objects.create(email='test@test.com')
        self.user.set_password('pass')
        self.user.save()
        self.client = Client()

    def test_login(self):
        source = make_fake_source()
        chant = make_fake_chant()
        sequence = make_fake_sequence()

        # currently not logged in, should redirect

        # ChantCreateView
        response = self.client.get(f'/chant-create/{source.id}')
        self.assertRedirects(response, f'/login/?next=/chant-create/{source.id}')       

        # ChantDeleteView
        response = self.client.get(f'/chant-delete/{chant.id}')
        self.assertRedirects(response, f'/login/?next=/chant-delete/{chant.id}')        
        
        # SourceEditChantsView
        response = self.client.get(f'/edit-chants/{source.id}')
        self.assertRedirects(response, f'/login/?next=/edit-chants/{source.id}')        

        # SequenceEditView
        response = self.client.get(f'/edit-sequence/{sequence.id}')
        self.assertRedirects(response, f'/login/?next=/edit-sequence/{sequence.id}')        

        # SourceCreateView
        response = self.client.get('/source-create/')
        self.assertRedirects(response, '/login/?next=/source-create/')    

        # SourceEditView
        response = self.client.get(f'/edit-source/{source.id}')
        self.assertRedirects(response, f'/login/?next=/edit-source/{source.id}')

        # UserSourceListView
        response = self.client.get('/my-sources/')
        self.assertRedirects(response, '/login/?next=/my-sources/')        

        # UserListView
        response = self.client.get('/users/')
        self.assertRedirects(response, '/login/?next=/users/')        

    def test_permissions_project_manager(self):
        project_manager = Group.objects.get(name='project manager') 
        project_manager.user_set.add(self.user)
        self.client.login(email='test@test.com', password='pass')

        # get random source, chant and sequence
        source = Source.objects.order_by('?').first()
        chant = Chant.objects.order_by('?').first()
        sequence = Sequence.objects.order_by('?').first()

        # ChantCreateView
        response = self.client.get(f'/chant-create/{source.id}')
        self.assertEqual(response.status_code, 200)

        # ChantDeleteView
        response = self.client.get(f'/chant-delete/{chant.id}')
        self.assertEqual(response.status_code, 200)

        # SourceEditChantsView
        response = self.client.get(f'/edit-chants/{source.id}')
        self.assertEqual(response.status_code, 200)

        # SequenceEditView
        response = self.client.get(f'/edit-sequence/{sequence.id}')
        self.assertEqual(response.status_code, 200)

        # SourceCreateView
        response = self.client.get('/source-create/')
        self.assertEqual(response.status_code, 200)

        # SourceEditView
        response = self.client.get(f'/edit-source/{source.id}')
        self.assertEqual(response.status_code, 200)

    def test_permissions_contributor(self):
        contributor = Group.objects.get(name='contributor') 
        contributor.user_set.add(self.user)
        self.client.login(email='test@test.com', password='pass')

        # a source assigned to the current user
        assigned_source = make_fake_source()
        self.user.sources_user_can_edit.add(assigned_source)
        for i in range(5):
            Chant.objects.create(source=assigned_source)
        chant_in_assigned_source = Chant.objects.filter(source=assigned_source).order_by('?').first()

        # a source created by the current user
        source_created_by_contributor = make_fake_source()
        source_created_by_contributor.created_by = self.user
        source_created_by_contributor.save()
        for i in range(5):
            Chant.objects.create(source=source_created_by_contributor)
        chant_in_source_created_by_contributor = Chant.objects.filter(source=source_created_by_contributor).order_by('?').first()

        # did not create the source, was not assigned the source
        restricted_source = Source.objects.filter(~Q(created_by=self.user)&~Q(id=assigned_source.id)).order_by('?').first()
        restricted_chant = Chant.objects.filter(source=restricted_source).order_by('?').first()
        
        # a random sequence
        sequence = Sequence.objects.order_by('?').first()

        # ChantCreateView
        response = self.client.get(f'/chant-create/{restricted_source.id}')
        self.assertEqual(response.status_code, 403)

        response = self.client.get(f'/chant-create/{source_created_by_contributor.id}')
        self.assertEqual(response.status_code, 200)

        response = self.client.get(f'/chant-create/{assigned_source.id}')
        self.assertEqual(response.status_code, 200)

        # ChantDeleteView
        response = self.client.get(f'/chant-delete/{restricted_chant.id}')
        self.assertEqual(response.status_code, 403)

        response = self.client.get(f'/chant-delete/{chant_in_source_created_by_contributor.id}')
        self.assertEqual(response.status_code, 200)

        response = self.client.get(f'/chant-delete/{chant_in_assigned_source.id}')
        self.assertEqual(response.status_code, 200)

        # SourceEditChantsView
        response = self.client.get(f'/edit-chants/{restricted_source.id}')
        self.assertEqual(response.status_code, 403)

        response = self.client.get(f'/edit-chants/{source_created_by_contributor.id}')
        self.assertEqual(response.status_code, 200)

        response = self.client.get(f'/edit-chants/{assigned_source.id}')
        self.assertEqual(response.status_code, 200)

        # SequenceEditView
        response = self.client.get(f'/edit-sequence/{sequence.id}')
        self.assertEqual(response.status_code, 403)

        # SourceCreateView
        response = self.client.get('/source-create/')
        self.assertEqual(response.status_code, 200)

        # SourceEditView
        response = self.client.get(f'/edit-source/{restricted_source.id}')
        self.assertEqual(response.status_code, 403)

        response = self.client.get(f'/edit-source/{source_created_by_contributor.id}')
        self.assertEqual(response.status_code, 200)

        response = self.client.get(f'/edit-source/{assigned_source.id}')
        self.assertEqual(response.status_code, 403)

    def test_permissions_editor(self):
        editor = Group.objects.get(name='editor') 
        editor.user_set.add(self.user)
        self.client.login(email='test@test.com', password='pass')

        # a source assigned to the current user
        assigned_source = make_fake_source()
        self.user.sources_user_can_edit.add(assigned_source)
        for i in range(5):
            Chant.objects.create(source=assigned_source)
        chant_in_assigned_source = Chant.objects.filter(source=assigned_source).order_by('?').first()

        # a source created by the current user
        source_created_by_contributor = make_fake_source()
        source_created_by_contributor.created_by = self.user
        source_created_by_contributor.save()
        for i in range(5):
            Chant.objects.create(source=source_created_by_contributor)
        chant_in_source_created_by_contributor = Chant.objects.filter(source=source_created_by_contributor).order_by('?').first()

        # did not create the source, was not assigned the source
        restricted_source = Source.objects.filter(~Q(created_by=self.user)&~Q(id=assigned_source.id)).order_by('?').first()
        restricted_chant = Chant.objects.filter(source=restricted_source).order_by('?').first()
        
        # a random sequence
        sequence = Sequence.objects.order_by('?').first()

        # ChantCreateView
        response = self.client.get(f'/chant-create/{restricted_source.id}')
        self.assertEqual(response.status_code, 403)

        response = self.client.get(f'/chant-create/{source_created_by_contributor.id}')
        self.assertEqual(response.status_code, 200)

        response = self.client.get(f'/chant-create/{assigned_source.id}')
        self.assertEqual(response.status_code, 200)

        # ChantDeleteView
        response = self.client.get(f'/chant-delete/{restricted_chant.id}')
        self.assertEqual(response.status_code, 403)

        response = self.client.get(f'/chant-delete/{chant_in_source_created_by_contributor.id}')
        self.assertEqual(response.status_code, 200)

        response = self.client.get(f'/chant-delete/{chant_in_assigned_source.id}')
        self.assertEqual(response.status_code, 200)

        # SourceEditChantsView
        response = self.client.get(f'/edit-chants/{restricted_source.id}')
        self.assertEqual(response.status_code, 403)

        response = self.client.get(f'/edit-chants/{source_created_by_contributor.id}')
        self.assertEqual(response.status_code, 200)

        response = self.client.get(f'/edit-chants/{assigned_source.id}')
        self.assertEqual(response.status_code, 200)

        # SequenceEditView
        response = self.client.get(f'/edit-sequence/{sequence.id}')
        self.assertEqual(response.status_code, 403)

        # SourceCreateView
        response = self.client.get('/source-create/')
        self.assertEqual(response.status_code, 200)

        # SourceEditView
        response = self.client.get(f'/edit-source/{restricted_source.id}')
        self.assertEqual(response.status_code, 403)

        response = self.client.get(f'/edit-source/{source_created_by_contributor.id}')
        self.assertEqual(response.status_code, 200)

        response = self.client.get(f'/edit-source/{assigned_source.id}')
        self.assertEqual(response.status_code, 200)

    def test_permissions_default(self):
        self.client.login(email='test@test.com', password='pass')

        # get random source, chant and sequence
        source = Source.objects.order_by('?').first()
        chant = Chant.objects.order_by('?').first()
        sequence = Sequence.objects.order_by('?').first()

        # ChantCreateView
        response = self.client.get(f'/chant-create/{source.id}')
        self.assertEqual(response.status_code, 403)

        # ChantDeleteView
        response = self.client.get(f'/chant-delete/{chant.id}')
        self.assertEqual(response.status_code, 403)

        # SourceEditChantsView
        response = self.client.get(f'/edit-chants/{source.id}')
        self.assertEqual(response.status_code, 403)

        # SequenceEditView
        response = self.client.get(f'/edit-sequence/{sequence.id}')
        self.assertEqual(response.status_code, 403)

        # SourceCreateView
        response = self.client.get('/source-create/')
        self.assertEqual(response.status_code, 403)

        # SourceEditView
        response = self.client.get(f'/edit-source/{source.id}')
        self.assertEqual(response.status_code, 403)


class ChantListViewTest(TestCase):
    def test_url_and_templates(self):
        source = make_fake_source()
        response = self.client.get(reverse("chant-list"), {"source": source.id})
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "base.html")
        self.assertTemplateUsed(response, "chant_list.html")

    def test_published_vs_unpublished(self):
        published_source = make_fake_source(published=True)
        response_1 = self.client.get(reverse("chant-list"), {"source": published_source.id})
        self.assertEqual(response_1.status_code, 200)

        unpublished_source = make_fake_source(published=False)
        response_2 = self.client.get(reverse("chant-list"), {"source": unpublished_source.id})
        self.assertEqual(response_2.status_code, 403)

    def test_filter_by_source(self):
        source = make_fake_source()
        another_source = make_fake_source()
        chant_in_source = Chant.objects.create(source=source)
        chant_in_another_source = Chant.objects.create(source=another_source)
        response = self.client.get(reverse("chant-list"), {"source": source.id})
        chants = response.context["chants"]
        self.assertIn(chant_in_source, chants)
        self.assertNotIn(chant_in_another_source, chants)

    def test_filter_by_feast(self):
        source = make_fake_source()
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
        source = make_fake_source()
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
        source = make_fake_source()
        chant_on_folio = Chant.objects.create(source=source, folio="001r")
        chant_on_another_folio = Chant.objects.create(source=source, folio="002r")
        response = self.client.get(
            reverse("chant-list"), {"source": source.id, "folio": "001r"}
        )
        chants = response.context["chants"]
        self.assertIn(chant_on_folio, chants)
        self.assertNotIn(chant_on_another_folio, chants)

    def test_search_full_text(self):
        source = make_fake_source()
        chant = Chant.objects.create(
            source=source, manuscript_full_text=make_fake_text(max_size=100)
        )
        search_term = get_random_search_term(chant.manuscript_full_text)
        response = self.client.get(
            reverse("chant-list"), {"source": source.id, "search_text": search_term}
        )
        self.assertIn(chant, response.context["chants"])

    def test_search_incipit(self):
        source = make_fake_source()
        chant = Chant.objects.create(source=source, incipit=make_fake_text(max_size=30))
        search_term = get_random_search_term(chant.incipit)
        response = self.client.get(
            reverse("chant-list"), {"source": source.id, "search_text": search_term}
        )
        self.assertIn(chant, response.context["chants"])

    def test_search_full_text_std_spelling(self):
        source = make_fake_source()
        chant = Chant.objects.create(
            source=source,
            manuscript_full_text_std_spelling=make_fake_text(max_size=100),
        )
        search_term = get_random_search_term(chant.manuscript_full_text_std_spelling)
        response = self.client.get(
            reverse("chant-list"), {"source": source.id, "search_text": search_term}
        )
        self.assertIn(chant, response.context["chants"])

    def test_context_source(self):
        source = make_fake_source()
        response = self.client.get(reverse("chant-list"), {"source": source.id})
        self.assertEqual(source, response.context["source"])

    def test_context_folios(self):
        # create a source and several chants in it
        source = make_fake_source()
        Chant.objects.create(source=source, folio="001r")
        Chant.objects.create(source=source, folio="001r")
        Chant.objects.create(source=source, folio="001v")
        Chant.objects.create(source=source, folio="001v")
        Chant.objects.create(source=source, folio="002r")
        Chant.objects.create(source=source, folio="002v")
        # request the page
        response = self.client.get(reverse("chant-list"), {"source": source.id})
        # the element in "folios" should be unique and ordered in this way
        folios = response.context["folios"]
        self.assertEqual(list(folios), ["001r", "001v", "002r", "002v"])

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

        source.published=True
        source.save()
        response = self.client.get(
            reverse("chant-detail", args=[chant.id])
        )
        self.assertEqual(response.status_code, 200)

        source.published=False
        source.save()
        response = self.client.get(
            reverse("chant-detail", args=[chant.id])
        )
        self.assertEqual(response.status_code, 403)

    def test_chant_edit_link(self):

        source = make_fake_source()
        chant = make_fake_chant(
            source=source, folio="001r", 
            manuscript_full_text_std_spelling="manuscript_full_text_std_spelling"
        )

        # have to create project manager user - "View | Edit" toggle only visible for those with edit access for a chant's source
        self.user = get_user_model().objects.create(email='test@test.com')
        self.user.set_password('pass')
        self.user.save()
        self.client = Client()
        project_manager = Group.objects.get(name='project manager') 
        project_manager.user_set.add(self.user)
        self.client.login(email='test@test.com', password='pass')

        response = self.client.get(
            reverse("chant-detail", args=[chant.id])
        )
        expected_url_fragment = f"edit-chants/{source.id}?pk={chant.id}&folio={chant.folio}"

        self.assertIn(expected_url_fragment, str(response.content))


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
        chant = make_fake_chant(source=source, manuscript_full_text_std_spelling="lorem ipsum")

        source.published = True
        source.save()
        response = self.client.get(
            reverse("chant-search"), {"keyword": "lorem", "op": "contains"}
        )
        self.assertIn(chant, response.context["chants"])

        source.published = False
        source.save()
        response = self.client.get(
            reverse("chant-search"), {"keyword": "lorem", "op": "contains"}
        )
        self.assertNotIn(chant, response.context["chants"])

    def test_search_by_office(self):
        source = Source.objects.create(published=True, title="a source")
        office = make_fake_office()
        chant = Chant.objects.create(source=source, office=office)
        search_term = get_random_search_term(office.name)
        response = self.client.get(reverse("chant-search"), {"office": search_term})
        self.assertIn(chant, response.context["chants"])

    def test_filter_by_genre(self):
        source = Source.objects.create(published=True, title="a source")
        genre = make_fake_genre()
        chant = Chant.objects.create(source=source, genre=genre)
        response = self.client.get(reverse("chant-search"), {"genre": genre.id})
        self.assertIn(chant, response.context["chants"])

    def test_search_by_cantus_id(self):
        source = Source.objects.create(published=True, title="a source")
        chant = Chant.objects.create(source=source, cantus_id=faker.numerify("######"))
        search_term = get_random_search_term(chant.cantus_id)
        response = self.client.get(reverse("chant-search"), {"cantus_id": search_term})
        self.assertIn(chant, response.context["chants"])

    def test_search_by_mode(self):
        source = Source.objects.create(published=True, title="a source")
        chant = Chant.objects.create(source=source, mode=faker.numerify("#"))
        search_term = get_random_search_term(chant.mode)
        response = self.client.get(reverse("chant-search"), {"mode": search_term})
        self.assertIn(chant, response.context["chants"])

    def test_search_by_feast(self):
        source = Source.objects.create(published=True, title="a source")
        feast = make_fake_feast()
        chant = Chant.objects.create(source=source, feast=feast)
        search_term = get_random_search_term(feast.name)
        response = self.client.get(reverse("chant-search"), {"feast": search_term})
        self.assertIn(chant, response.context["chants"])

    def test_search_by_position(self):
        source = Source.objects.create(published=True, title="a source")
        position = 1
        chant = Chant.objects.create(source=source, position=position)
        search_term = "1"
        response = self.client.get(reverse("chant-search"), {"position": search_term})
        self.assertIn(chant, response.context["chants"])

    def test_filter_by_melody(self):
        source = Source.objects.create(published=True, title="a source")
        chant_with_melody = Chant.objects.create(
            source=source, volpiano=make_fake_text(max_size=20)
        )
        chant_without_melody = Chant.objects.create(source=source)
        response = self.client.get(reverse("chant-search"), {"melodies": "true"})
        # only chants with melodies should be in the result
        self.assertIn(chant_with_melody, response.context["chants"])
        self.assertNotIn(chant_without_melody, response.context["chants"])

    def test_keyword_search_starts_with(self):
        source = Source.objects.create(published=True, title="a source")
        chant = Chant.objects.create(
            source=source, incipit=make_fake_text(max_size=200)
        )
        # use the beginning part of the incipit as search term
        search_term = chant.incipit[0 : random.randint(1, len(chant.incipit))]
        response = self.client.get(
            reverse("chant-search"), {"keyword": search_term, "op": "starts_with"}
        )
        self.assertIn(chant, response.context["chants"])

    def test_keyword_search_contains(self):
        source = Source.objects.create(published=True, title="a source")
        chant = Chant.objects.create(
            source=source, manuscript_full_text=make_fake_text(max_size=400)
        )
        # split full text into words
        full_text_words = chant.manuscript_full_text.split(" ")
        # use a random subset of words as search term
        search_term = " ".join(
            random.choices(
                full_text_words, k=random.randint(1, max(len(full_text_words) - 1, 1))
            )
        )
        response = self.client.get(
            reverse("chant-search"), {"keyword": search_term, "op": "contains"}
        )
        self.assertIn(chant, response.context["chants"])


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
        # source = Source.objects.create(public=True,published, title="a source")
        source = make_fake_source()
        office = make_fake_office()
        chant = Chant.objects.create(source=source, office=office)
        search_term = get_random_search_term(office.name)
        response = self.client.get(
            reverse("chant-search-ms", args=[source.id]), {"office": search_term}
        )
        self.assertIn(chant, response.context["chants"])

    def test_filter_by_genre(self):
        source = make_fake_source()
        genre = make_fake_genre()
        chant = Chant.objects.create(source=source, genre=genre)
        response = self.client.get(
            reverse("chant-search-ms", args=[source.id]), {"genre": genre.id}
        )
        self.assertIn(chant, response.context["chants"])

    def test_search_by_cantus_id(self):
        source = make_fake_source()
        chant = Chant.objects.create(source=source, cantus_id=faker.numerify("######"))
        search_term = get_random_search_term(chant.cantus_id)
        response = self.client.get(
            reverse("chant-search-ms", args=[source.id]), {"cantus_id": search_term}
        )
        self.assertIn(chant, response.context["chants"])

    def test_search_by_mode(self):
        source = make_fake_source()
        chant = Chant.objects.create(source=source, mode=faker.numerify("#"))
        search_term = get_random_search_term(chant.mode)
        response = self.client.get(
            reverse("chant-search-ms", args=[source.id]), {"mode": search_term}
        )
        self.assertIn(chant, response.context["chants"])

    def test_search_by_feast(self):
        source = make_fake_source()
        feast = make_fake_feast()
        chant = Chant.objects.create(source=source, feast=feast)
        search_term = get_random_search_term(feast.name)
        response = self.client.get(
            reverse("chant-search-ms", args=[source.id]), {"feast": search_term}
        )
        self.assertIn(chant, response.context["chants"])

    def test_filter_by_melody(self):
        source = make_fake_source()
        chant_with_melody = Chant.objects.create(
            source=source, volpiano=make_fake_text(max_size=20)
        )
        chant_without_melody = Chant.objects.create(source=source)
        response = self.client.get(
            reverse("chant-search-ms", args=[source.id]), {"melodies": "true"}
        )
        # only chants with melodies should be in the result
        self.assertIn(chant_with_melody, response.context["chants"])
        self.assertNotIn(chant_without_melody, response.context["chants"])

    def test_keyword_search_starts_with(self):
        source = make_fake_source()
        chant = Chant.objects.create(
            source=source, incipit=make_fake_text(max_size=200)
        )
        # use the beginning part of the incipit as search term
        search_term = chant.incipit[0 : random.randint(1, len(chant.incipit))]
        response = self.client.get(
            reverse("chant-search-ms", args=[source.id]),
            {"keyword": search_term, "op": "starts_with"},
        )
        self.assertIn(chant, response.context["chants"])

    def test_keyword_search_contains(self):
        source = make_fake_source()
        chant = Chant.objects.create(
            source=source, manuscript_full_text=make_fake_text(max_size=400)
        )
        # split full text into words
        full_text_words = chant.manuscript_full_text.split(" ")
        # use a random subset of words as search term
        search_term = " ".join(
            random.choices(
                full_text_words, k=random.randint(1, max(len(full_text_words) - 1, 1))
            )
        )
        response = self.client.get(
            reverse("chant-search-ms", args=[source.id]),
            {"keyword": search_term, "op": "contains"},
        )
        self.assertIn(chant, response.context["chants"])


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
        chant = Chant.objects.create(source=chant_source)
        response = self.client.get(reverse("chant-index"), {"source": chant_source.id})
        self.assertEqual(chant_source, response.context["source"])
        self.assertIn(chant, response.context["chants"])

    def test_sequence_source_queryset(self):
        seq_source = Source.objects.create(
            segment=Segment.objects.create(id=4064, name="Clavis Sequentiarium"),
            title="a sequence source",
            published=True
        )
        sequence = Sequence.objects.create(source=seq_source)
        response = self.client.get(reverse("chant-index"), {"source": seq_source.id})
        self.assertEqual(seq_source, response.context["source"])
        self.assertIn(sequence, response.context["chants"])


class ChantCreateViewTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        Group.objects.create(name="project manager")

    def setUp(self):
        self.user = get_user_model().objects.create(email='test@test.com')
        self.user.set_password('pass')
        self.user.save()
        self.client = Client()
        project_manager = Group.objects.get(name='project manager') 
        project_manager.user_set.add(self.user)
        self.client.login(email='test@test.com', password='pass')

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
            {"manuscript_full_text_std_spelling": "initial", "folio": "001r", "sequence_number": "1"})
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('chant-create', args=[source.id]))  
        chant = Chant.objects.first()
        self.assertEqual(chant.manuscript_full_text_std_spelling, "initial")
    
    def test_view_url_path(self):
        source = make_fake_source()
        response = self.client.get(f"/chant-create/{source.id}")
        self.assertEqual(response.status_code, 200)

    def test_context(self):
        """some context variable passed to templates
        """
        source = make_fake_source()
        url = reverse("chant-create", args=[source.id])
        response = self.client.get(url)
        self.assertEqual(response.context["source"].title, source.title)

    def test_post_error(self):
        """post with correct source and empty full-text
        """
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
            sequence_number=3,
        )
        fake_chant_2 = make_fake_chant(
            source=fake_source,
            cantus_id="007450", # this has to be an actual cantus ID, since next_chants pulls data from CantusIndex and we'll get an empty response if we use "222222" etc.
            folio="001",
            sequence_number=2,
            next_chant=fake_chant_3,
        )
        fake_chant_1 = make_fake_chant(
            source=fake_source,
            cantus_id="111111",
            folio="001",
            sequence_number=1,
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
        self.assertEqual(
            "007450", response.context["suggested_chants"][0]["cid"]
        )
        self.assertEqual(
            fake_R_genre.id, response.context["suggested_chants"][0]["genre_id"]
        )

    def test_fake_source(self):
        """cannot go to input form with a fake source
        """
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
                sequence_number=i,
                cantus_id=fake_cantus_id,
            )
        # go to the same source and access the input form
        url = reverse("chant-create", args=[source.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        # assert context previous_chant, suggested_chants
        self.assertEqual(i, response.context["previous_chant"].sequence_number)
        self.assertEqual(fake_cantus_id, response.context["previous_chant"].cantus_id)
        self.assertListEqual([], response.context["suggested_chants"])

    def test_repeated_seq(self):
        """post with a folio and seq that already exists in the source
        """
        TEST_FOLIO = "001r"
        # create some chants in the test source
        source = make_fake_source()
        for i in range(1, 5):
            Chant.objects.create(
                source=source,
                manuscript_full_text=faker.text(10),
                folio=TEST_FOLIO,
                sequence_number=i,
            )
        # post a chant with the same folio and seq
        url = reverse("chant-create", args=[source.id])
        fake_text = faker.text(10)
        response = self.client.post(
            url,
            data={
                "manuscript_full_text_std_spelling": fake_text,
                "folio": TEST_FOLIO,
                "sequence_number": random.randint(1, 4),
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
                "sequence_number": "1",
                # liquescents, to be converted to lowercase
                #                    vv v v v v v v  
                "volpiano": "9abcdefg)A-B1C2D3E4F5G67?. yiz"
                #                      ^ ^ ^ ^ ^ ^ ^^^^^^^^
                # clefs, accidentals, etc., to be deleted
            }
        )
        chant_1 = Chant.objects.get(manuscript_full_text_std_spelling="ut queant lactose")
        self.assertEqual(chant_1.volpiano, "9abcdefg)A-B1C2D3E4F5G67?. yiz")
        self.assertEqual(chant_1.volpiano_notes, "9abcdefg9abcdefg")
        self.client.post(
            reverse("chant-create", args=[source.id]), 
            {"manuscript_full_text_std_spelling": "resonare foobaz", "folio": "001r", "sequence_number": "2", "volpiano": "abacadaeafagahaja"}
        )
        chant_2 = Chant.objects.get(manuscript_full_text_std_spelling="resonare foobaz")
        self.assertEqual(chant_2.volpiano, "abacadaeafagahaja")
        self.assertEqual(chant_2.volpiano_intervals, "1-12-23-34-45-56-67-78-8")


class ChantDeleteViewTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        Group.objects.create(name="project manager")

    def setUp(self):
        self.user = get_user_model().objects.create(email='test@test.com')
        self.user.set_password('pass')
        self.user.save()
        self.client = Client()
        project_manager = Group.objects.get(name='project manager') 
        project_manager.user_set.add(self.user)
        self.client.login(email='test@test.com', password='pass')

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
        self.user = get_user_model().objects.create(email='test@test.com')
        self.user.set_password('pass')
        self.user.save()
        self.client = Client()
        project_manager = Group.objects.get(name='project manager') 
        project_manager.user_set.add(self.user)
        self.client.login(email='test@test.com', password='pass')

    def test_url_and_templates(self):
        source1 = make_fake_source()

        # must specify folio, or SourceEditChantsView.get_queryset will fail when it tries to default to displaying the first folio
        Chant.objects.create(source=source1, folio="001r")

        response = self.client.get(reverse("source-edit-chants", args=[source1.id]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "chant_edit.html")

        response = self.client.get(reverse("source-edit-chants", args=[source1.id + 100]))
        self.assertEqual(response.status_code, 404)
        self.assertTemplateUsed(response, "404.html")

        # trying to access chant-edit with a source that has no chant should return 404
        source2 = make_fake_source()

        response = self.client.get(reverse("source-edit-chants", args=[source2.id]))
        self.assertEqual(response.status_code, 404)
        self.assertTemplateUsed(response, "404.html")

    def test_update_chant(self):
        source = make_fake_source()
        chant = Chant.objects.create(source=source, manuscript_full_text_std_spelling="initial")

        response = self.client.get(
            reverse('source-edit-chants', args=[source.id]), 
            {'pk': chant.id})
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "chant_edit.html")

        response = self.client.post(
            reverse('source-edit-chants', args=[source.id]), 
            {'manuscript_full_text_std_spelling': 'test', 'pk': chant.id})
        self.assertEqual(response.status_code, 302)
        # Check that after the edit, the user is redirected to the source-edit-chants page
        self.assertRedirects(response, reverse('source-edit-chants', args=[source.id]))  
        chant.refresh_from_db()
        self.assertEqual(chant.manuscript_full_text_std_spelling, 'test')
    
    def test_provide_suggested_fulltext(self):
        source = make_fake_source()
        chant = make_fake_chant(source=source, manuscript_full_text_std_spelling="",
        cantus_id="007450")
        response = self.client.get(
            reverse('source-edit-chants', args=[source.id]), 
            {'pk': chant.id}
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
            sequence_number=1
        )
        self.client.post(
            reverse('source-edit-chants', args=[source.id]),
            {
                "manuscript_full_text_std_spelling": "ut queant lactose",
                "folio": "001r",
                "sequence_number": "1",
                # liquescents, to be converted to lowercase
                #                    vv v v v v v v  
                "volpiano": "9abcdefg)A-B1C2D3E4F5G67?. yiz"
                #                      ^ ^ ^ ^ ^ ^ ^^^^^^^^
                # clefs, accidentals, etc., to be deleted
            }
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
            sequence_number=2
        )
        self.client.post(
            reverse('source-edit-chants', args=[source.id]),  
            {
                "manuscript_full_text_std_spelling": "resonare foobaz",
                "folio": "001r",
                "sequence_number": "2",
                "volpiano": "abacadaeafagahaja",
            }
        )
        chant_2 = Chant.objects.get(
            manuscript_full_text_std_spelling="resonare foobaz"
        )
        self.assertEqual(chant_2.volpiano, "abacadaeafagahaja")
        self.assertEqual(chant_2.volpiano_intervals, "1-12-23-34-45-56-67-78-8")


class ChantProofreadViewTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        Group.objects.create(name="project manager")

    def setUp(self):
        self.user = get_user_model().objects.create(email='test@test.com')
        self.user.set_password('pass')
        self.user.save()
        self.client = Client()
        project_manager = Group.objects.get(name='project manager') 
        project_manager.user_set.add(self.user)
        self.client.login(email='test@test.com', password='pass')

    def test_view_url_and_templates(self):
        source = make_fake_source()
        source_id = source.id

        for i in range(3):
            chant = make_fake_chant(source=source, folio="001r", sequence_number=i)
            sample_folio = chant.folio
            sample_pk = chant.id
        nonexistent_folio = "001v"

        response_1 = self.client.get(f"/proofread-chant/{source_id}")
        self.assertEqual(response_1.status_code, 200)
        self.assertTemplateUsed(response_1, "base.html")
        self.assertTemplateUsed(response_1, "chant_proofread.html")

        response_2 = self.client.get(reverse("chant-proofread", args=[source_id]))
        self.assertEqual(response_2.status_code, 200)

        response_3 = self.client.get(f"/proofread-chant/{source_id}?folio={sample_folio}")
        self.assertEqual(response_3.status_code, 200)

        response_4 = self.client.get(f"/proofread-chant/{source_id}?folio={nonexistent_folio}")
        self.assertEqual(response_4.status_code, 404)

        response_5 = self.client.get(f"/proofread-chant/{source_id}?pk={sample_pk}&folio={sample_folio}")
        self.assertEqual(response_5.status_code, 200)

        self.client.logout()
        response_6 = self.client.get(reverse("chant-proofread", args=[source_id]))
        self.assertEqual(response_6.status_code, 302) # 302 Found
    
    def test_proofread_chant(self):
        chant = make_fake_chant(manuscript_full_text_std_spelling="lorem ipsum", folio="001r")
        self.assertIs(chant.manuscript_full_text_std_proofread, False)
        source = chant.source
        response = self.client.post(f"/proofread-chant/{source.id}?pk={chant.id}&folio=001r", 
            {'manuscript_full_text_std_proofread': 'True'})
        self.assertEqual(response.status_code, 302) # 302 Found
        chant.refresh_from_db()
        self.assertIs(chant.manuscript_full_text_std_proofread, True)


class ChantEditSyllabificationViewTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        Group.objects.create(name="project manager")

    def setUp(self):
        self.user = get_user_model().objects.create(email='test@test.com')
        self.user.set_password('pass')
        self.user.save()
        self.client = Client()
        project_manager = Group.objects.get(name='project manager') 
        project_manager.user_set.add(self.user)
        self.client.login(email='test@test.com', password='pass')

    def test_view_url_and_templates(self):
        chant = make_fake_chant()
        chant_id = chant.id

        response_1 = self.client.get(f"/edit-syllabification/{chant_id}")
        self.assertEqual(response_1.status_code, 200)
        self.assertTemplateUsed(response_1, "base.html")
        self.assertTemplateUsed(response_1, "chant_syllabification_edit.html")

        response_2 = self.client.get(reverse("source-edit-syllabification", args=[chant_id]))
        self.assertEqual(response_2.status_code, 200)

        self.client.logout()
        response_3 = self.client.get(reverse("source-edit-syllabification", args=[chant_id]))
        self.assertEqual(response_3.status_code, 302) # 302: redirect to login page

    def test_edit_syllabification(self):
        chant = make_fake_chant(
            manuscript_syllabized_full_text="lorem ipsum"
        )
        self.assertIs(chant.manuscript_syllabized_full_text, "lorem ipsum")
        response = self.client.post(f"/edit-syllabification/{chant.id}", {"manuscript_syllabized_full_text": "lo-rem ip-sum"})
        self.assertEqual(response.status_code, 302) # 302 Found
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
            reverse("feast-list"), {"sort_by": make_fake_text(max_size=5)}
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
        source = Source.objects.create(published=True, title="published_source")
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
        big_source = Source.objects.create(
            published=True, title="big_source", siglum="big"
        )
        small_source = Source.objects.create(
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
        self.assertEqual(len(sources_zip), 1) # only item should be a duple corresponding to published_source
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
            name="genre1", description="test", mass_office="Mass, Office",
        )
        mass_genre = Genre.objects.create(
            name="genre2", description="test", mass_office="Mass"
        )
        office_genre = Genre.objects.create(
            name="genre3", description="test", mass_office="Office"
        )
        old_hispanic_genre = Genre.objects.create(
            name="genre4", description="test", mass_office="Old Hispanic",
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
            name="genre1", description="test", mass_office="Mass, Office",
        )
        mass_genre = Genre.objects.create(
            name="genre2", description="test", mass_office="Mass"
        )
        office_genre = Genre.objects.create(
            name="genre3", description="test", mass_office="Office"
        )
        old_hispanic_genre = Genre.objects.create(
            name="genre4", description="test", mass_office="Old Hispanic",
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
            name="genre1", description="test", mass_office="Mass, Office",
        )
        mass_genre = Genre.objects.create(
            name="genre2", description="test", mass_office="Mass"
        )
        office_genre = Genre.objects.create(
            name="genre3", description="test", mass_office="Office"
        )
        old_hispanic_genre = Genre.objects.create(
            name="genre4", description="test", mass_office="Old Hispanic",
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
            name="genre1", description="test", mass_office="Mass, Office",
        )
        mass_genre = Genre.objects.create(
            name="genre2", description="test", mass_office="Mass"
        )
        office_genre = Genre.objects.create(
            name="genre3", description="test", mass_office="Office"
        )
        old_hispanic_genre = Genre.objects.create(
            name="genre4", description="test", mass_office="Old Hispanic",
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

    def test_chants_by_genre(self):
        genre = make_fake_genre()
        # create a source because if chants1, 2 and 3 don't have a source,
        # source.published will be None, and they won't be included in
        # the response context
        source = make_fake_source()
        chant1 = Chant.objects.create(incipit="chant1", genre=genre, cantus_id="100000", source=source)
        chant2 = Chant.objects.create(incipit="chant2", genre=genre, cantus_id="100000", source=source)
        chant3 = Chant.objects.create(incipit="chant3", genre=genre, cantus_id="123456", source=source)
        response = self.client.get(reverse("genre-detail", args=[genre.id]))
        self.assertEqual(response.status_code, 200)
        # the context should be a list of dicts, each corresponding to one cantus id
        chant_info_list = response.context["object_list"]
        # the chant info list should be ordered by the number of chants
        # the first one should be the one that has two chants
        self.assertEqual(chant_info_list[0]["cantus_id"], "100000")
        self.assertEqual(chant_info_list[0]["num_chants"], 2)
        self.assertEqual(chant_info_list[1]["cantus_id"], "123456")
        self.assertEqual(chant_info_list[1]["num_chants"], 1)
    
    def test_genre_cantus_ids_published_vs_unpublished(self):
        genre = make_fake_genre()
        published_source = make_fake_source(published=True)
        unpublished_source = make_fake_source(published=False)
        published_chant = make_fake_chant(
            source=published_source,
            genre=genre,
            cantus_id="111111",
        )
        unpublished_chant = make_fake_chant(
            source=unpublished_source,
            genre=genre,
            cantus_id="999999",
        )
        response = self.client.get(reverse("genre-detail", args=[genre.id]))
        chant_info_list = response.context["object_list"]
        self.assertEqual(len(chant_info_list), 1)
        self.assertEqual(chant_info_list[0]["cantus_id"], "111111")

    def test_search_incipit(self):
        genre = make_fake_genre()
        # create a source because if chants1 and 2 don't have a source,
        # source.published will be None, and they won't be included in
        # the response context
        source = make_fake_source()
        chant1 = Chant.objects.create(incipit="chant1", genre=genre, cantus_id="100000", source=source)
        chant2 = Chant.objects.create(incipit="chant2", genre=genre, cantus_id="123456", source=source)
        response = self.client.get(reverse("genre-detail", args=[genre.id]))
        self.assertEqual(response.status_code, 200)

        # search for the common part of incipit
        response = self.client.get(
            reverse("genre-detail", args=[genre.id]), {"incipit": "chant"}
        )
        # both cantus_ids should be in the list
        self.assertEqual(len(response.context["object_list"]), 2)
        # search for the unique part of incipit
        response = self.client.get(
            reverse("genre-detail", args=[genre.id]), {"incipit": "chant1"}
        )
        # only one record should be in the list
        self.assertEqual(len(response.context["object_list"]), 1)
        # search for random incipit that don't exist
        response = self.client.get(
            reverse("genre-detail", args=[genre.id]), {"incipit": "random"}
        )
        # the list should be empty
        self.assertEqual(len(response.context["object_list"]), 0)


class IndexerListViewTest(TestCase):
    def setUp(self):
        # unless a segment is specified when a source is created, the source is automatically assigned
        # to the segment with the name "CANTUS Database" - to prevent errors, we must make sure that
        # such a segment exists
        Segment.objects.create(name="CANTUS Database")

    def test_view_url_path(self):
        response = self.client.get("/indexers/")
        self.assertEqual(response.status_code, 200)

    def test_view_url_reverse_name(self):
        response = self.client.get(reverse("indexer-list"))
        self.assertEqual(response.status_code, 200)

    def test_url_and_templates(self):
        """Test the url and templates used"""
        response = self.client.get(reverse("indexer-list"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "base.html")
        self.assertTemplateUsed(response, "indexer_list.html")

    def test_only_public_indexer_visible(self):
        """In the indexer list view, only public indexers (those who have at least one published source) should be visible"""
        # generate some indexers
        indexer_with_published_source = make_fake_indexer()
        indexer_with_unpublished_source = make_fake_indexer()
        indexer_with_no_source = make_fake_indexer()

        # generate published/unpublished sources and assign indexers to them
        unpublished_source = Source.objects.create(title="unpublished source", published=False)
        unpublished_source.inventoried_by.set([indexer_with_unpublished_source])

        published_source = Source.objects.create(title="published source", published=True)
        published_source.inventoried_by.set([indexer_with_published_source])

        source_with_multiple_indexers = Source.objects.create(
            title="unpublished source with multiple indexers", published=False,
        )
        source_with_multiple_indexers.inventoried_by.set(
            [indexer_with_published_source, indexer_with_unpublished_source]
        )

        # access the page context, only the public indexer should be in the context
        response = self.client.get(reverse("indexer-list"))
        self.assertEqual(response.status_code, 200)
        self.assertIn(indexer_with_published_source, response.context["indexers"])
        self.assertNotIn(indexer_with_unpublished_source, response.context["indexers"])
        self.assertNotIn(indexer_with_no_source, response.context["indexers"])

    def test_search_given_name(self):
        """
        Indexer can be searched by passing a `q` parameter to the url \\
        Search fields include first name, family name, country, city, and institution \\
        Only public indexers should appear in the results
        """
        indexer_with_published_source = make_fake_indexer()
        published_source = Source.objects.create(title="published source", published=True)
        published_source.inventoried_by.set([indexer_with_published_source])

        # search with a random slice of first name
        target = indexer_with_published_source.given_name
        search_term = get_random_search_term(target)
        response = self.client.get(reverse("indexer-list"), {"q": search_term})
        self.assertEqual(response.status_code, 200)
        self.assertIn(indexer_with_published_source, response.context["indexers"])

    def test_search_family_name(self):
        indexer_with_published_source = make_fake_indexer()
        published_source = Source.objects.create(title="published source", published=True)
        published_source.inventoried_by.set([indexer_with_published_source])

        target = indexer_with_published_source.family_name
        search_term = get_random_search_term(target)
        response = self.client.get(reverse("indexer-list"), {"q": search_term})
        self.assertEqual(response.status_code, 200)
        self.assertIn(indexer_with_published_source, response.context["indexers"])

    def test_search_country(self):
        indexer_with_published_source = make_fake_indexer()
        published_source = Source.objects.create(title="published source", published=True)
        published_source.inventoried_by.set([indexer_with_published_source])

        target = indexer_with_published_source.country
        search_term = get_random_search_term(target)
        response = self.client.get(reverse("indexer-list"), {"q": search_term})
        self.assertEqual(response.status_code, 200)
        self.assertIn(indexer_with_published_source, response.context["indexers"])

    def test_search_city(self):
        indexer_with_published_source = make_fake_indexer()
        published_source = Source.objects.create(title="published source", published=True)
        published_source.inventoried_by.set([indexer_with_published_source])

        target = indexer_with_published_source.city
        search_term = get_random_search_term(target)
        response = self.client.get(reverse("indexer-list"), {"q": search_term})
        self.assertEqual(response.status_code, 200)
        self.assertIn(indexer_with_published_source, response.context["indexers"])

    def test_search_institution(self):
        indexer_with_published_source = make_fake_indexer()
        published_source = Source.objects.create(title="published source", published=True)
        published_source.inventoried_by.set([indexer_with_published_source])

        target = indexer_with_published_source.institution
        search_term = get_random_search_term(target)
        response = self.client.get(reverse("indexer-list"), {"q": search_term})
        self.assertEqual(response.status_code, 200)
        self.assertIn(indexer_with_published_source, response.context["indexers"])


class IndexerDetailViewTest(TestCase):
    NUM_INDEXERS = 10

    @classmethod
    def setUpTestData(cls):
        for i in range(cls.NUM_INDEXERS):
            make_fake_indexer()

    def test_view_url_path(self):
        for indexer in Indexer.objects.all():
            response = self.client.get(f"/indexer/{indexer.id}")
            self.assertEqual(response.status_code, 200)

    def test_view_url_reverse_name(self):
        for indexer in Indexer.objects.all():
            response = self.client.get(reverse("indexer-detail", args=[indexer.id]))
            self.assertEqual(response.status_code, 200)

    def test_url_and_templates(self):
        """Test the url and templates used"""
        indexer = make_fake_indexer()
        response = self.client.get(reverse("indexer-detail", args=[indexer.id]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "base.html")
        self.assertTemplateUsed(response, "indexer_detail.html")

    def test_context(self):
        indexer = make_fake_indexer()
        response = self.client.get(reverse("indexer-detail", args=[indexer.id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(indexer, response.context["indexer"])


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
        self.assertEqual(sequences.query.order_by, ("siglum", "sequence"))

    def test_search_incipit(self):
        # create a published sequence source and some sequence in it
        source = Source.objects.create(
            published=True, title="a sequence source"
        )
        sequence = Sequence.objects.create(
            incipit=make_fake_text(max_size=30), source=source
        )
        search_term = get_random_search_term(sequence.incipit)
        # request the page, search for the incipit
        response = self.client.get(reverse("sequence-list"), {"incipit": search_term})
        # the sequence should be present in the results
        self.assertIn(sequence, response.context["sequences"])

    def test_search_siglum(self):
        # create a published sequence source and some sequence in it
        source = Source.objects.create(
            published=True, title="a sequence source"
        )
        sequence = Sequence.objects.create(
            siglum=make_fake_text(max_size=10), source=source
        )
        search_term = get_random_search_term(sequence.siglum)
        # request the page, search for the siglum
        response = self.client.get(reverse("sequence-list"), {"siglum": search_term})
        # the sequence should be present in the results
        self.assertIn(sequence, response.context["sequences"])

    def test_search_cantus_id(self):
        # create a published sequence source and some sequence in it
        source = Source.objects.create(
            published=True, title="a sequence source"
        )
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


class SequenceEditViewTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        Group.objects.create(name="project manager")

    def setUp(self):
        self.user = get_user_model().objects.create(email='test@test.com')
        self.user.set_password('pass')
        self.user.save()
        self.client = Client()
        project_manager = Group.objects.get(name='project manager') 
        project_manager.user_set.add(self.user)
        self.client.login(email='test@test.com', password='pass')

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
            reverse('sequence-edit', args=[sequence_id]), 
            {'title': 'test', 'source': sequence.source.id})
        self.assertEqual(response.status_code, 302)
        sequence.refresh_from_db()
        self.assertEqual(sequence.title, 'test')


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
        published_source = Source.objects.create(
            published=True, title="published source"
        )
        private_source = Source.objects.create(
            published=False, title="private source"
        )
        response = self.client.get(reverse("source-list"))
        sources = response.context["sources"]
        self.assertIn(published_source, sources)
        self.assertNotIn(private_source, sources)

    def test_filter_by_segment(self):
        """The source list can be filtered by `segment`, `provenance`, `century`, and `full_source`"""
        cantus_segment = make_fake_segment(name="cantus")
        clavis_segment = make_fake_segment(name="clavis")
        chant_source = Source.objects.create(
            segment=cantus_segment, title="chant source", published=True
        )
        seq_source = Source.objects.create(
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
        aachen_source = Source.objects.create(
            provenance=aachen,
            published=True,
            title="source originated in Aachen",
        )
        albi_source = Source.objects.create(
            provenance=albi,
            published=True,
            title="source originated in Albi",
        )
        no_provenance_source = Source.objects.create(
            published=True, title="source with empty provenance"
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

        ninth_century_source = Source.objects.create(
            published=True, title="source",
        )
        ninth_century_source.century.set([ninth_century])

        ninth_century_first_half_source = Source.objects.create(
            published=True, title="source",
        )
        ninth_century_first_half_source.century.set([ninth_century_first_half])

        multiple_century_source = Source.objects.create(
            published=True, title="source",
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
        full_source = Source.objects.create(
            full_source=True, published=True, title="full source"
        )
        fragment = Source.objects.create(
            full_source=False, published=True, title="fragment"
        )
        unknown = Source.objects.create(
            published=True, title="full_source field is empty"
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
        source = Source.objects.create(
            title=make_fake_text(max_size=20), published=True
        )
        search_term = get_random_search_term(source.title)
        response = self.client.get(reverse("source-list"), {"general": search_term})
        self.assertIn(source, response.context["sources"])

    def test_search_by_siglum(self):
        source = Source.objects.create(
            siglum=make_fake_text(max_size=20), published=True, title="title"
        )
        search_term = get_random_search_term(source.siglum)
        response = self.client.get(reverse("source-list"), {"general": search_term})
        self.assertIn(source, response.context["sources"])

    def test_search_by_rism_siglum_name(self):
        rism_siglum = make_fake_rism_siglum()
        source = Source.objects.create(
            rism_siglum=rism_siglum, published=True, title="title",
        )
        search_term = get_random_search_term(source.rism_siglum.name)
        response = self.client.get(reverse("source-list"), {"general": search_term})
        self.assertIn(source, response.context["sources"])

    def test_search_by_rism_siglum_description(self):
        rism_siglum = make_fake_rism_siglum()
        source = Source.objects.create(
            rism_siglum=rism_siglum, published=True, title="title",
        )
        search_term = get_random_search_term(source.rism_siglum.description)
        response = self.client.get(reverse("source-list"), {"general": search_term})
        self.assertIn(source, response.context["sources"])

    def test_search_by_description(self):
        source = Source.objects.create(
            description=make_fake_text(max_size=200),
            published=True,
            title="title",
        )
        search_term = get_random_search_term(source.description)
        response = self.client.get(reverse("source-list"), {"general": search_term})
        self.assertIn(source, response.context["sources"])

    def test_search_by_summary(self):
        source = Source.objects.create(
            summary=make_fake_text(max_size=200),
            published=True,
            title="title",
        )
        search_term = get_random_search_term(source.summary)
        response = self.client.get(reverse("source-list"), {"general": search_term})
        self.assertIn(source, response.context["sources"])

    def test_search_by_indexing_notes(self):
        """The "indexing notes" field searches in `indexing_notes` and indexer/editor related fields"""
        source = Source.objects.create(
            indexing_notes=make_fake_text(max_size=200),
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
        self.user = get_user_model().objects.create(email='test@test.com')
        self.user.set_password('pass')
        self.user.save()
        self.client = Client()
        project_manager = Group.objects.get(name='project manager') 
        project_manager.user_set.add(self.user)
        self.client.login(email='test@test.com', password='pass')
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
            reverse('source-create'), 
            {'title': 'test'})

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('source-create'))       

        source = Source.objects.first()
        self.assertEqual(source.title, 'test')


class SourceEditViewTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        Group.objects.create(name="project manager")

    def setUp(self):
        self.user = get_user_model().objects.create(email='test@test.com')
        self.user.set_password('pass')
        self.user.save()
        self.client = Client()
        project_manager = Group.objects.get(name='project manager') 
        project_manager.user_set.add(self.user)
        self.client.login(email='test@test.com', password='pass')

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
            reverse('source-edit', args=[source.id]), 
            {'title': 'test'})

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('source-detail', args=[source.id]))       
        source.refresh_from_db()
        self.assertEqual(source.title, 'test')


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
        source = Source.objects.create(
            segment=Segment.objects.create(id=4064, name="Bower Sequence Database"),
            title="a sequence source",
            published=True
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
        source = Source.objects.create(
            segment=Segment.objects.create(id=4064, name="Bower Sequence Database"),
            title="a sequence source",
            published=True
        )
        sequence = Sequence.objects.create(source=source)
        # request the page
        response = self.client.get(reverse("source-detail", args=[source.id]))
        # the sequence should be in the list of sequences
        self.assertIn(sequence, response.context["sequences"])
        # the list of sequences should be ordered by the "sequence" field
        self.assertEqual(response.context["sequences"].query.order_by, ("sequence",))

    def test_published_vs_unpublished(self):
        source = make_fake_source(published=False)
        response_1 = self.client.get(reverse("source-detail", args=[source.id]))
        self.assertEqual(response_1.status_code, 403)

        source.published = True
        source.save()
        response_2 = self.client.get(reverse("source-detail", args=[source.id]))
        self.assertEqual(response_2.status_code, 200)


class JsonMelodyExportTest(TestCase):
    def test_json_melody_response(self):
        NUM_CHANTS = 10
        FAKE_CANTUS_ID = "111111"
        for _ in range(NUM_CHANTS):
            make_fake_chant(cantus_id=FAKE_CANTUS_ID)

        response_1 = self.client.get(f"/json-melody/{FAKE_CANTUS_ID}")
        self.assertEqual(response_1.status_code, 200)
        self.assertIsInstance(response_1, JsonResponse)

        response_2 = self.client.get(reverse("json-melody-export", args=[FAKE_CANTUS_ID]))
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
        self.assertEqual(len(unpacked_response), 1) # just published_chant
        self.assertEqual(unpacked_response[0]["fulltext"], "I'm a chant from a published source!")


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

        response_3 = self.client.get(reverse('json-node-export', args=["1000000000"]))
        self.assertEqual(response_3.status_code, 404)
        
    def test_json_node_for_chant(self):
        chant = make_fake_chant()
        id = chant.id

        response = self.client.get(reverse("json-node-export", args=[id]))
        self.assertIsInstance(response, JsonResponse)

        unpacked_response = json.loads(response.content)

        response_cantus_id = unpacked_response['cantus_id']
        self.assertIsInstance(response_cantus_id, str)
        self.assertEqual(response_cantus_id, chant.cantus_id)

        response_id = unpacked_response['id']
        self.assertIsInstance(response_id, int)
        self.assertEqual(response_id, id)

    def test_json_node_for_sequence(self):
        sequence = make_fake_sequence()
        id = sequence.id

        response = self.client.get(reverse("json-node-export", args=[id]))
        self.assertIsInstance(response, JsonResponse)

        unpacked_response = json.loads(response.content)

        response_cantus_id = unpacked_response['cantus_id']
        self.assertIsInstance(response_cantus_id, str)
        self.assertEqual(response_cantus_id, sequence.cantus_id)

        response_id = unpacked_response['id']
        self.assertIsInstance(response_id, int)
        self.assertEqual(response_id, id)

    def test_json_node_for_source(self):
        source = make_fake_source()
        id = source.id

        response = self.client.get(reverse("json-node-export", args=[id]))
        self.assertIsInstance(response, JsonResponse)

        unpacked_response = json.loads(response.content)

        response_title = unpacked_response['title']
        self.assertIsInstance(response_title, str)
        self.assertEqual(response_title, source.title)

        response_id = unpacked_response['id']
        self.assertIsInstance(response_id, int)
        self.assertEqual(response_id, id)

    def test_json_node_for_indexer(self):
        indexer = make_fake_indexer()
        id = indexer.id

        response = self.client.get(reverse("json-node-export", args=[id]))
        self.assertIsInstance(response, JsonResponse)

        unpacked_response = json.loads(response.content)

        response_name = unpacked_response['given_name']
        self.assertIsInstance(response_name, str)
        self.assertEqual(response_name, indexer.given_name)

        response_id = unpacked_response['id']
        self.assertIsInstance(response_id, int)
        self.assertEqual(response_id, id)

    def test_json_node_published_vs_unpublished(self):
        source = make_fake_source(published=True)
        chant = make_fake_chant(source=source)
        sequence = make_fake_sequence(source=source)

        source_id = source.id
        chant_id = chant.id
        sequence_id = sequence.id

        published_source_response = self.client.get(reverse("json-node-export", args=[source_id]))
        self.assertEqual(published_source_response.status_code, 200)
        published_chant_response = self.client.get(reverse("json-node-export", args=[chant_id]))
        self.assertEqual(published_chant_response.status_code, 200)
        published_sequence_response = self.client.get(reverse("json-node-export", args=[sequence_id]))
        self.assertEqual(published_sequence_response.status_code, 200)

        source.published = False
        source.save()

        unpublished_source_response = self.client.get(reverse("json-node-export", args=[source_id]))
        self.assertEqual(unpublished_source_response.status_code, 404)
        unpublished_chant_response = self.client.get(reverse("json-node-export", args=[chant_id]))
        self.assertEqual(unpublished_chant_response.status_code, 404)
        unpublished_sequence_response = self.client.get(reverse("json-node-export", args=[sequence_id]))
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
        self.assertEqual(sample_item_keys, ['csv'])

        # the single value should be a link in form `cantusdatabase.com/csv/{source.id}`
        expected_substring = f"/csv/{sample_id}"
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
            source = fake_source_1,
            cantus_id = "2000",
            folio="001r",
            sequence_number=2,
        )

        fake_chant_1 = Chant.objects.create(
            source = fake_source_1,
            cantus_id = "1000",
            folio="001r",
            sequence_number=1,
            next_chant=fake_chant_2,
        )

        fake_chant_4 = Chant.objects.create(
            source = fake_source_2,
            cantus_id = "2000",
            folio="001r",
            sequence_number=2,
        )

        fake_chant_3 = Chant.objects.create(
            source = fake_source_2,
            cantus_id = "1000",
            folio="001r",
            sequence_number=1,
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
            source = fake_source_1,
        )
        fake_chant_1 = Chant.objects.create(
            source = fake_source_1,
            next_chant = fake_chant_2
        )
        
        fake_chant_4 = Chant.objects.create(
            source = fake_source_2,
        )
        fake_chant_3 = Chant.objects.create(
            source = fake_source_2,
            next_chant = fake_chant_4
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
            source = fake_source_1,
            cantus_id = "2000",
            folio="001r",
            sequence_number=2,
        )

        fake_chant_1 = Chant.objects.create(
            source = fake_source_1,
            cantus_id = "1000",
            folio="001r",
            sequence_number=1,
            next_chant=fake_chant_2
        )

        fake_chant_4 = Chant.objects.create(
            source = fake_source_2,
            cantus_id = "2000",
            folio="001r",
            sequence_number=2,
        )

        fake_chant_3 = Chant.objects.create(
            source = fake_source_2,
            cantus_id = "1000",
            folio="001r",
            sequence_number=1,
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


class CsvExportTest(TestCase):
    def test_url(self):
        source = make_fake_source(published=True)
        response_1 = self.client.get(reverse("csv-export", args=[source.id]))
        self.assertEqual(response_1.status_code, 200)
        response_2 = self.client.get(f'/csv/{source.id}')
        self.assertEqual(response_2.status_code, 200)
    
    def test_content(self):
        NUM_CHANTS = 5
        source = make_fake_source(published=True)
        for _ in range(NUM_CHANTS):
            make_fake_chant(source=source)
        response = self.client.get(reverse("csv-export", args=[source.id]))
        content = response.content.decode('utf-8')
        split_content = list(csv.reader(content.splitlines(), delimiter=','))
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
            "cao_concordances",
            "addendum",
            "extra",
            "node_id",
        ]
        for t in expected_column_titles:
            self.assertIn(t, header)

        self.assertEqual(len(rows), NUM_CHANTS)
    
    def test_published_vs_unpublished(self):
        published_source = make_fake_source(published=True)
        response_1 = self.client.get(reverse("csv-export", args=[published_source.id]))
        self.assertEqual(response_1.status_code, 200)
        unpublished_source = make_fake_source(published=False)
        response_2 = self.client.get(reverse("csv-export", args=[unpublished_source.id]))
        self.assertEqual(response_2.status_code, 403)



class ChangePasswordViewTest(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create(email='test@test.com')
        self.user.set_password('pass')
        self.user.save()
        self.client.login(email='test@test.com', password='pass')

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
        response_1 = self.client.post(reverse("change-password"), {"old_password": "pass", "new_password1": "updated_pass", "new_password2": "updated_pass"})
        self.assertEqual(response_1.status_code, 200)
        self.client.logout()
        self.client.login(email='test@test.com', password='updated_pass')
        response_2 = self.client.get(reverse("change-password"))
        self.assertEqual(response_2.status_code, 200) # if login failed, status code will be 302
