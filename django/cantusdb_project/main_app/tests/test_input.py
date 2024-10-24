import unittest

from django.test import TestCase
from django.urls import reverse

from faker import Faker

from main_app.models import Source
from main_app.models import Chant

from .make_fakes import *

fake = Faker()

# test_input (this file) is out of date and should not be run.
# Instead, run test_views and test_models.

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
    SLICE_SIZE = 10

    def setUp(self):
        return super().setUp()

    @unittest.skip(
        "post request fails to make chant - see comment above `response = ...`"
    )
    def test_post_success(self):
        """post with correct source and random full-text"""
        source = make_fake_source()
        url = reverse("chant-create", args=[source.id])
        fake_text = fake.text(100)

        # post request seems to be failing to make a chant
        # at least, `Chant.objects.get(manuscript_full_text_std_spelling=fake_text)` can't find it...
        response = self.client.post(
            url, data={"manuscript_full_text_std_spelling": fake_text}, follow=True
        )
        self.assertTrue(
            Chant.objects.filter(manuscript_full_text_std_spelling=fake_text).exists()
        )
        self.assertRedirects(response, reverse("chant-create", args=[source.id]))

    @unittest.skip(
        "post request fails to make chant - see comment above `response = ...`"
    )
    def test_autofill(self):
        """Test pre-prepopulate when input chants to a non-empty source"""
        # create some chants in the test source
        source = Source.objects.all()[self.rand_source]
        for i in range(1, 5):
            Chant.objects.create(
                source=source,
                manuscript_full_text=fake.text(10),
                folio="010r",
                c_sequence=i,
            )
        chants_in_source = Chant.objects.all().filter(source=source).order_by("-id")
        last_chant = chants_in_source[0]
        last_folio = last_chant.folio
        last_sequence = last_chant.c_sequence
        # create a new chant using input form
        url = reverse("chant-create", args=[source.id])
        fake_text = fake.text(100)

        # post request seems to be failing to make a chant
        # at least, `Chant.objects.get(manuscript_full_text_std_spelling=fake_text)` can't find it...
        response = self.client.post(
            url,
            data={"manuscript_full_text_std_spelling": fake_text},
            follow=True,
        )
        # after inputting, should redirect to another input form
        self.assertRedirects(response, reverse("chant-create", args=[source.id]))
        # get the newly created chant
        posted_chant = Chant.objects.get(manuscript_full_text_std_spelling=fake_text)
        # see if it has the default folio and c_sequence
        self.assertEqual(posted_chant.folio, last_folio)
        self.assertEqual(posted_chant.c_sequence, last_sequence + 1)

    @unittest.skip(
        "post request fails to make chant - see comment above `response = ...`"
    )
    def test_autofill_empty(self):
        """Test pre-prepopulate when input chants to an empty source"""
        DEFAULT_FOLIO = "001r"
        DEFAULT_SEQ = 1
        source = Source.objects.all()[self.rand_source]
        # create a new chant using input form
        url = reverse("chant-create", args=[source.id])
        fake_text = fake.text(100)

        # post request seems to be failing to make a chant
        # at least, `Chant.objects.get(manuscript_full_text_std_spelling=fake_text)` can't find it...
        response = self.client.post(
            url,
            data={"manuscript_full_text_std_spelling": fake_text},
            follow=True,
        )
        # after inputting, should redirect to another input form
        self.assertRedirects(response, reverse("chant-create", args=[source.id]))
        # get the newly created chant
        posted_chant = Chant.objects.get(manuscript_full_text_std_spelling=fake_text)
        # see if it has the default folio and c_sequence
        self.assertEqual(posted_chant.folio, DEFAULT_FOLIO)
        self.assertEqual(posted_chant.c_sequence, DEFAULT_SEQ)
