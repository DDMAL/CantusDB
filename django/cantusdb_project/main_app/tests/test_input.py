import random

from django.test import TestCase
from django.urls import reverse

from faker import Faker

from main_app.forms import ChantCreateForm
from main_app.models import Source
from main_app.models import Chant

fake = Faker()

"""
run tests with 'python manage.py test main_app'
it creates a special database for the purpose of testing
it looks for subclass of django.test.TestCase, in any file whose name begins with 'test'
and methods whose names begin with 'test'
https://docs.djangoproject.com/en/3.0/topics/testing/overview/

# Run all the tests found within the 'animals' package
$ ./manage.py test animals

# Run just one test case
$ ./manage.py test animals.tests.AnimalTestCase

# Run just one test method
$ ./manage.py test animals.tests.AnimalTestCase.test_animals_can_speak

https://developer.mozilla.org/en-US/docs/Learn/Server-side/Django/Testing
"""


class ChantCreateViewTest(TestCase):
    fixtures = [
        "source_fixtures.json",
        "provenance_fixtures.json",
        "segment_fixtures.json",
        "century_fixtures.json",
        "indexer_fixtures.json",
        "notation_fixtures.json",
    ]
    SLICE_SIZE = 10

    def setUp(self):
        self.number_of_sources = Source.objects.all().count()
        self.slice_begin = random.randint(0, self.number_of_sources - self.SLICE_SIZE)
        self.slice_end = self.slice_begin + self.SLICE_SIZE
        self.rand_source = random.randint(0, self.number_of_sources)
        return super().setUp()

    def test_view_url_path(self):
        for source in Source.objects.all()[self.slice_begin : self.slice_end]:
            response = self.client.get(f"/chant-create/{source.id}")
            self.assertEqual(response.status_code, 200)

    def test_view_url_reverse_name(self):
        for source in Source.objects.all()[self.slice_begin : self.slice_end]:
            response = self.client.get(reverse("chant-create", args=[source.id]))
            self.assertEqual(response.status_code, 200)

    def test_template_used(self):
        for source in Source.objects.all()[self.slice_begin : self.slice_end]:
            response = self.client.get(reverse("chant-create", args=[source.id]))
            self.assertEqual(response.status_code, 200)
            self.assertTemplateUsed(response, "base.html")
            self.assertTemplateUsed(response, "input_form_w.html")

    def test_fake_source(self):
        """cannot go to input form with a fake source
        """
        fake_source = fake.numerify(
            "#####"
        )  # there's not supposed to be 5-digits source id
        response = self.client.get(reverse("chant-create", args=[fake_source]))
        self.assertEqual(response.status_code, 404)

    def test_post_success(self):
        """post with correct source and random full-text
        """
        source = Source.objects.all()[self.rand_source]
        url = reverse("chant-create", args=[source.id])
        fake_text = fake.text(100)
        response = self.client.post(
            url, data={"manuscript_full_text_std_spelling": fake_text}, follow=True
        )
        self.assertTrue(
            Chant.objects.filter(manuscript_full_text_std_spelling=fake_text).exists()
        )
        self.assertRedirects(response, reverse("chant-create", args=[source.id]))

    def test_autofill(self):
        """Test pre-prepopulate when input chants to a non-empty source
        """
        # create some chants in the test source
        source = Source.objects.all()[self.rand_source]
        for i in range(1, 5):
            Chant.objects.create(
                source=source,
                manuscript_full_text=fake.text(10),
                folio="010r",
                sequence_number=i,
            )
        chants_in_source = Chant.objects.all().filter(source=source).order_by("-id")
        last_chant = chants_in_source[0]
        last_folio = last_chant.folio
        last_sequence = last_chant.sequence_number
        # create a new chant using input form
        url = reverse("chant-create", args=[source.id])
        fake_text = fake.text(100)
        response = self.client.post(
            url, data={"manuscript_full_text_std_spelling": fake_text}, follow=True,
        )
        # after inputting, should redirect to another input form
        self.assertRedirects(response, reverse("chant-create", args=[source.id]))
        # get the newly created chant
        posted_chant = Chant.objects.get(manuscript_full_text_std_spelling=fake_text)
        # see if it has the default folio and sequence
        self.assertEqual(posted_chant.folio, last_folio)
        self.assertEqual(posted_chant.sequence_number, last_sequence + 1)

    def test_autofill_empty(self):
        """Test pre-prepopulate when input chants to an empty source
        """
        DEFAULT_FOLIO = "001r"
        DEFAULT_SEQ = 1
        source = Source.objects.all()[self.rand_source]
        # create a new chant using input form
        url = reverse("chant-create", args=[source.id])
        fake_text = fake.text(100)
        response = self.client.post(
            url, data={"manuscript_full_text_std_spelling": fake_text}, follow=True,
        )
        # after inputting, should redirect to another input form
        self.assertRedirects(response, reverse("chant-create", args=[source.id]))
        # get the newly created chant
        posted_chant = Chant.objects.get(manuscript_full_text_std_spelling=fake_text)
        # see if it has the default folio and sequence
        self.assertEqual(posted_chant.folio, DEFAULT_FOLIO)
        self.assertEqual(posted_chant.sequence_number, DEFAULT_SEQ)

    def test_repeated_seq(self):
        """post with a folio and seq that already exists in the source
        """
        TEST_FOLIO = "001r"
        # create some chants in the test source
        source = Source.objects.all()[self.rand_source]
        for i in range(1, 5):
            Chant.objects.create(
                source=source,
                manuscript_full_text=fake.text(10),
                folio=TEST_FOLIO,
                sequence_number=i,
            )
        # post a chant with the same folio and seq
        url = reverse("chant-create", args=[source.id])
        fake_text = fake.text(10)
        response = self.client.post(
            url,
            data={
                "manuscript_full_text_std_spelling": fake_text,
                "folio": TEST_FOLIO,
                "sequence_number": random.randint(0, 4),
            },
            follow=True,
        )
        self.assertFormError(
            response,
            "form",
            None,
            errors="Chant with the same sequence and folio already exists in this source.",
        )

    def test_post_error(self):
        """post with correct source and empty full-text
        """
        source = Source.objects.all()[self.rand_source]
        url = reverse("chant-create", args=[source.id])
        response = self.client.post(url, data={"manuscript_full_text_std_spelling": ""})
        self.assertFormError(
            response,
            "form",
            "manuscript_full_text_std_spelling",
            "This field is required.",
        )

    def test_context(self):
        """some context variable passed to templates
        """
        source = Source.objects.all()[self.rand_source]
        url = reverse("chant-create", args=[source.id])
        response = self.client.get(url)
        self.assertEqual(response.context["source"].title, source.title)
        self.assertEqual(
            response.context["source_link"], reverse("source-detail", args=[source.id])
        )


class CISearchViewTest(TestCase):
    def test_view_url_path(self):
        fake_search_term = fake.text(6)
        response = self.client.get(f"/ci-search/{fake_search_term}")
        self.assertEqual(response.status_code, 200)

    def test_view_url_reverse_name(self):
        fake_search_term = fake.text(6)
        response = self.client.get(reverse("ci-search", args=[fake_search_term]))
        self.assertEqual(response.status_code, 200)

    def test_template_used(self):
        fake_search_term = fake.text(6)
        response = self.client.get(reverse("ci-search", args=[fake_search_term]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "ci_search.html")

    def test_context_returned(self):
        fake_search_term = fake.text(6)
        # fake_search_term = "eia adest"
        response = self.client.get(f"/ci-search/{fake_search_term}")
        self.assertTrue("results" in response.context)
