from django.test import TestCase
from main_app.forms import ChantCreateForm
from django.urls import reverse

from main_app.models import Source
from main_app.models import Chant

import random
from faker import Faker

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
        "segment_fixtures",
        "century_fixtures",
        "indexer_fixtures",
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
        fake_source = fake.numerify(
            "#####"
        )  # there's not supposed to be 5-digits source id
        response = self.client.get(reverse("chant-create", args=[fake_source]))
        self.assertEqual(response.status_code, 404)

    def test_post_success(self):
        # post with correct source and random full-text
        source = Source.objects.all()[self.rand_source]
        url = reverse("chant-create", args=[source.id])
        fake_text = fake.text(100)
        response = self.client.post(
            url, data={"manuscript_full_text_std_spelling": fake_text}, follow=True
        )
        self.assertTrue(
            Chant.objects.filter(manuscript_full_text_std_spelling=fake_text).exists()
        )
        self.assertRedirects(response, reverse("chant-list"))
        self.assertRedirects(response, "/chants/")

    def test_post_error(self):
        # post with correct source and empty full-text
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
        # some context variable passed to templates
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


class ChantCreateFormTest(TestCase):
    fixtures = [
        "source_fixtures.json",
        "provenance_fixtures.json",
        "segment_fixtures",
        "century_fixtures",
        "indexer_fixtures",
        "notation_fixtures.json",
    ]

    def test_fake_source(self):
        # if the source does not exist, the form is not valid
        form = ChantCreateForm(data={"source": 000000})
        self.assertEqual(
            form.errors["source"],
            ["This source does not exist, please switch to a different source."],
        )
        self.assertFalse(form.is_valid())

    def test_empty_full_text(self):
        # if full-text is empty, the form is not valid
        form = ChantCreateForm(
            data={"source": 123610, "manuscript_full_text_std_spelling": ""}
        )
        self.assertEqual(
            form.errors["manuscript_full_text_std_spelling"],
            ["This field is required."],
        )
        self.assertFalse(form.is_valid())

    def test_mandatory_field(self):
        # if source and full-text are correct, the form is valid
        form = ChantCreateForm(
            data={
                "source": 123610,
                "manuscript_full_text_std_spelling": "some random text",
            }
        )
        self.assertTrue(form.is_valid())

