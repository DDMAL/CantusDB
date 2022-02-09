from django.test import TestCase
from django.urls import reverse
from main_app.models import Indexer
from .make_fakes import *

# run with `python -Wa manage.py test main_app.tests.test_models`
# the -Wa flag tells Python to display deprecation warnings


class CenturyModelTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        make_fake_century()

    def test_name_label(self):
        century = Century.objects.get(id=1)
        field_label = century._meta.get_field("name").verbose_name
        self.assertEqual(field_label, "name")

    def test_name_max_length(self):
        century = Century.objects.get(id=1)
        max_length = century._meta.get_field("name").max_length
        self.assertEqual(max_length, 255)


class ChantModelTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        make_fake_chant()

    # TODO: Check all chant fields and add doc. Many fields are not clear about what they do.


class IndexerModelTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Set up non-modified objects used by all test methods
        make_fake_indexer()

    def test_first_name_label(self):
        indexer = Indexer.objects.get(id=1)
        field_label = indexer._meta.get_field("first_name").verbose_name
        self.assertEqual(field_label, "first name")

    def test_first_name_max_length(self):
        indexer = Indexer.objects.get(id=1)
        max_length = indexer._meta.get_field("first_name").max_length
        self.assertEqual(max_length, 50)

    def test_family_name_label(self):
        indexer = Indexer.objects.get(id=1)
        field_label = indexer._meta.get_field("family_name").verbose_name
        self.assertEqual(field_label, "family name")

    def test_family_name_max_length(self):
        indexer = Indexer.objects.get(id=1)
        max_length = indexer._meta.get_field("family_name").max_length
        self.assertEqual(max_length, 50)

    def test_insitution_label(self):
        indexer = Indexer.objects.get(id=1)
        field_label = indexer._meta.get_field("institution").verbose_name
        self.assertEqual(field_label, "institution")

    def test_institution_max_length(self):
        indexer = Indexer.objects.get(id=1)
        max_length = indexer._meta.get_field("institution").max_length
        self.assertEqual(max_length, 255)

    def test_city_label(self):
        indexer = Indexer.objects.get(id=1)
        field_label = indexer._meta.get_field("city").verbose_name
        self.assertEqual(field_label, "city")

    def test_city_max_length(self):
        indexer = Indexer.objects.get(id=1)
        max_length = indexer._meta.get_field("city").max_length
        self.assertEqual(max_length, 255)

    def test_country_label(self):
        indexer = Indexer.objects.get(id=1)
        field_label = indexer._meta.get_field("country").verbose_name
        self.assertEqual(field_label, "country")

    def test_country_max_length(self):
        indexer = Indexer.objects.get(id=1)
        max_length = indexer._meta.get_field("country").max_length
        self.assertEqual(max_length, 255)

    def test_indexer_absolute_url(self):
        indexer = Indexer.objects.get(id=1)
        absolute_url = reverse("indexer-detail", args=[str(indexer.id)])
        self.assertEqual(indexer.get_absolute_url(), absolute_url)

    # this is useful only when __str__() is defined
    # def test_object_name_is_last_name_comma_first_name(self):
    #     indexer = indexer.objects.get(id=1)
    #     expected_object_name = f"{indexer.last_name}, {indexer.first_name}"
    #     self.assertEqual(str(indexer), expected_object_name)
