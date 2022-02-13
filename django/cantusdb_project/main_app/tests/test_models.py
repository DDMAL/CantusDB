from django.test import TestCase
from django.urls import reverse
from .make_fakes import *

# run with `python -Wa manage.py test main_app.tests.test_models`
# the -Wa flag tells Python to display deprecation warnings


class CenturyModelTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Set up non-modified objects used by all test methods
        make_fake_century()

    def test_name_label(self):
        # Using first() is better than hardcoding the pk like Century.objects.get(pk=1)
        # because the pk squence is not reset between test cases,
        # even though objects created by other tests are removed from db
        century = Century.objects.first()
        field_label = century._meta.get_field("name").verbose_name
        self.assertEqual(field_label, "name")

    def test_name_max_length(self):
        century = Century.objects.first()
        max_length = century._meta.get_field("name").max_length
        self.assertEqual(max_length, 255)


class ChantModelTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        make_fake_chant()

    def test_get_ci_url(self):
        chant = Chant.objects.first()
        ci_url = chant.get_ci_url()
        ci_url_correct = "http://cantusindex.org/id/{}".format(chant.cantus_id)
        self.assertEqual(ci_url, ci_url_correct)

    def test_get_concordances(self):
        chant = Chant.objects.get(id=1)
        chant_with_same_cantus_id = Chant.objects.create(cantus_id=chant.cantus_id)
        concordances = chant.related_chants_by_cantus_id()
        self.assertIn(chant_with_same_cantus_id, concordances)


class IndexerModelTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        make_fake_indexer()

    def test_first_name_label(self):
        indexer = Indexer.objects.first()
        field_label = indexer._meta.get_field("first_name").verbose_name
        self.assertEqual(field_label, "first name")

    def test_first_name_max_length(self):
        indexer = Indexer.objects.first()
        max_length = indexer._meta.get_field("first_name").max_length
        self.assertEqual(max_length, 50)

    def test_family_name_label(self):
        indexer = Indexer.objects.first()
        field_label = indexer._meta.get_field("family_name").verbose_name
        self.assertEqual(field_label, "family name")

    def test_family_name_max_length(self):
        indexer = Indexer.objects.first()
        max_length = indexer._meta.get_field("family_name").max_length
        self.assertEqual(max_length, 50)

    def test_insitution_label(self):
        indexer = Indexer.objects.first()
        field_label = indexer._meta.get_field("institution").verbose_name
        self.assertEqual(field_label, "institution")

    def test_institution_max_length(self):
        indexer = Indexer.objects.first()
        max_length = indexer._meta.get_field("institution").max_length
        self.assertEqual(max_length, 255)

    def test_city_label(self):
        indexer = Indexer.objects.first()
        field_label = indexer._meta.get_field("city").verbose_name
        self.assertEqual(field_label, "city")

    def test_city_max_length(self):
        indexer = Indexer.objects.first()
        max_length = indexer._meta.get_field("city").max_length
        self.assertEqual(max_length, 255)

    def test_country_label(self):
        indexer = Indexer.objects.first()
        field_label = indexer._meta.get_field("country").verbose_name
        self.assertEqual(field_label, "country")

    def test_country_max_length(self):
        indexer = Indexer.objects.first()
        max_length = indexer._meta.get_field("country").max_length
        self.assertEqual(max_length, 255)

    def test_indexer_absolute_url(self):
        indexer = Indexer.objects.first()
        absolute_url = reverse("indexer-detail", args=[str(indexer.id)])
        self.assertEqual(indexer.get_absolute_url(), absolute_url)

