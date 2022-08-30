from main_app.tests.make_fakes import make_fake_text
import random

from django.test import TestCase
from django.urls import reverse

from faker import Faker

from main_app.models import Source
from main_app.models import Chant

from .make_fakes import *

fake = Faker()

# test_input (this file) is out of date and should not be run.
# Instead, run test_views_general and test_models.

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

    def test_no_suggest(self):
        NUM_CHANTS = 3
        fake_folio = fake.numerify("###")
        source = Source.objects.all()[self.rand_source]
        # create some chants in the test folio
        for i in range(NUM_CHANTS):
            fake_cantus_id = fake.numerify("######")
            Chant.objects.create(
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

    def test_suggest_one_folio(self):
        NUM_CHANTS = 3
        fake_folio = fake.numerify("###")
        fake_cantus_ids = []
        fake_chants = []
        source = Source.objects.all()[self.rand_source]
        # create some chants in the test folio
        for i in range(NUM_CHANTS):
            fake_cantus_id = fake.numerify("######")
            fake_cantus_ids.append(fake_cantus_id)
            fake_chants.append(
                Chant.objects.create(
                    source=source,
                    folio=fake_folio,
                    sequence_number=i,
                    cantus_id=fake_cantus_id,
                )
            )
        # create one more chant with a cantus_id that is supposed to have suggestions
        Chant.objects.create(
            source=source,
            folio=fake_folio,
            sequence_number=i + 1,
            # if it has the same cantus_id as the first chant in this folio
            # it should give a suggestion of the second chant in this folio
            cantus_id=fake_cantus_ids[0],
        )
        # go to the same source and access the input form
        url = reverse("chant-create", args=[source.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        # suggested chants should be [the second chant in source]
        self.assertEqual(1, len(response.context["suggested_chants"]))
        self.assertListEqual(
            fake_cantus_ids[1], response.context["suggested_chants"][0].cantus_id
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


