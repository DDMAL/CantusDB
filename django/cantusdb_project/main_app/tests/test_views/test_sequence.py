"""
Tests for views in views/sequence.py
"""

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

from faker import Faker

from main_app.models import Segment, Sequence
from main_app.tests.make_fakes import (
    make_fake_sequence,
    make_fake_source,
    get_random_search_term,
    make_random_string,
)

# Create a Faker instance with locale set to Latin
faker = Faker("la")


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
        self.assertEqual(
            sequences.query.order_by,
            ("source__holding_institution__siglum", "s_sequence"),
        )

    def test_search_incipit(self):
        # create a published sequence source and some sequence in it
        source = make_fake_source(
            published=True,
            shelfmark="a sequence source",
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

    def test_search_shelfmark(self):
        # create a published sequence source and some sequence in it
        source = make_fake_source(
            published=True,
            shelfmark="a sequence source",
        )
        sequence = Sequence.objects.create(siglum=make_random_string(6), source=source)
        search_term = get_random_search_term(sequence.siglum)
        # request the page, search for the siglum
        response = self.client.get(reverse("sequence-list"), {"siglum": search_term})
        # the sequence should be present in the results
        self.assertIn(sequence, response.context["sequences"])

    def test_search_cantus_id(self):
        # create a published sequence source and some sequence in it
        source = make_fake_source(published=True, shelfmark="a sequence source")
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
