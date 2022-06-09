from django.forms import ValidationError
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
        # because the pk sequence is not reset between test cases,
        # even though objects created by other tests are removed from db
        century = Century.objects.first()
        field_label = century._meta.get_field("name").verbose_name
        self.assertEqual(field_label, "name")

    def test_name_max_length(self):
        century = Century.objects.first()
        max_length = century._meta.get_field("name").max_length
        self.assertEqual(max_length, 255)

    def test_display_name(self):
        century = Century.objects.first()
        display_name = century.display_name
        name_str = century.__str__()
        self.assertEqual(display_name, name_str)


class ChantModelTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        make_fake_chant()

    def test_get_ci_url(self):
        chant = Chant.objects.first()
        ci_url = chant.get_ci_url()
        ci_url_correct = "http://cantusindex.org/id/{}".format(chant.cantus_id)
        self.assertEqual(ci_url, ci_url_correct)

    def test_index_components(self):
        chant = Chant.objects.first()
        weight_search_term_dict = chant.index_components()
        expected_dict = {
            "A": (
                " ".join(
                    filter(
                        None,
                        [
                            chant.incipit,
                            chant.manuscript_full_text,
                            chant.manuscript_full_text_std_spelling,
                            chant.source.title,
                        ],
                    )
                )
            ),
            "B": (
                " ".join(
                    filter(
                        None, [chant.genre.name, chant.feast.name, chant.office.name]
                    )
                )
            ),
        }
        self.assertEqual(weight_search_term_dict, expected_dict)

    def test_get_concordances(self):
        chant = Chant.objects.get(id=1)
        chant_with_same_cantus_id = Chant.objects.create(cantus_id=chant.cantus_id)
        concordances = chant.related_chants_by_cantus_id()
        self.assertIn(chant_with_same_cantus_id, concordances)

    def test_display_name(self):
        chant = Chant.objects.first()
        display_name = chant.display_name
        name_str = chant.__str__()
        self.assertEqual(display_name, name_str)

    def test_absolute_url(self):
        chant = Chant.objects.first()
        absolute_url = reverse("chant-detail", args=[str(chant.id)])
        self.assertEqual(chant.get_absolute_url(), absolute_url)

    def test_chant_and_sequence_have_same_fields(self):
        chant_fields = Chant.get_fields_and_properties()
        seq_fields = Sequence.get_fields_and_properties()
        self.assertEqual(chant_fields, seq_fields)


class FeastModelTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        make_fake_feast()

    def test_object_name(self):
        feast = Feast.objects.first()
        self.assertEqual(str(feast), feast.name)

    def test_date_constraints(self):
        def create_fake_feast(month, day):
            f = Feast.objects.create(name="fakeFeast", month=month, day=day)

        self.assertRaises(ValidationError, create_fake_feast, month=13, day=1)
        self.assertRaises(ValidationError, create_fake_feast, month=0, day=1)
        self.assertRaises(ValidationError, create_fake_feast, month=-1, day=1)
        self.assertRaises(ValidationError, create_fake_feast, month=1, day=32)
        self.assertRaises(ValidationError, create_fake_feast, month=1, day=0)
        self.assertRaises(ValidationError, create_fake_feast, month=1, day=-1)

    def test_display_name(self):
        feast = Feast.objects.first()
        display_name = feast.display_name
        name_str = feast.__str__()
        self.assertEqual(display_name, name_str)

    def test_absolute_url(self):
        feast = Feast.objects.first()
        absolute_url = reverse("feast-detail", args=[str(feast.id)])
        self.assertEqual(feast.get_absolute_url(), absolute_url)


class GenreModelTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        make_fake_genre()

    def test_object_name(self):
        genre = Genre.objects.first()
        self.assertEqual(str(genre), genre.name)

    def test_display_name(self):
        genre = Genre.objects.first()
        display_name = genre.display_name
        name_str = genre.__str__()
        self.assertEqual(display_name, name_str)

    def test_absolute_url(self):
        genre = Genre.objects.first()
        absolute_url = reverse("genre-detail", args=[str(genre.id)])
        self.assertEqual(genre.get_absolute_url(), absolute_url)


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

    def test_absolute_url(self):
        indexer = Indexer.objects.first()
        absolute_url = reverse("indexer-detail", args=[str(indexer.id)])
        self.assertEqual(indexer.get_absolute_url(), absolute_url)


class OfficeModelTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        make_fake_office()

    def test_object_name(self):
        office = Office.objects.first()
        self.assertEqual(str(office), office.name)

    def test_display_name(self):
        office = Office.objects.first()
        display_name = office.display_name
        name_str = office.__str__()
        self.assertEqual(display_name, name_str)

    def test_absolute_url(self):
        office = Office.objects.first()
        absolute_url = reverse("office-detail", args=[str(office.id)])
        self.assertEqual(office.get_absolute_url(), absolute_url)


class SequenceModelTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        make_fake_sequence()

    def test_display_name(self):
        sequence = Sequence.objects.first()
        display_name = sequence.display_name
        name_str = sequence.__str__()
        self.assertEqual(display_name, name_str)

    def test_absolute_url(self):
        sequence = Sequence.objects.first()
        absolute_url = reverse("sequence-detail", args=[str(sequence.id)])
        self.assertEqual(sequence.get_absolute_url(), absolute_url)

    def test_chant_and_sequence_have_same_fields(self):
        chant_fields = Chant.get_fields_and_properties()
        seq_fields = Sequence.get_fields_and_properties()
        self.assertEqual(chant_fields, seq_fields)


class SourceModelTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        make_fake_source()

    def test_number_of_chants(self):
        source = Source.objects.first()
        chant = Chant.objects.create(source=source)
        sequence = Sequence.objects.create(source=source)
        self.assertIn(chant, source.chant_set.all())
        self.assertIn(sequence, source.sequence_set.all())
        self.assertEqual(source.number_of_chants(), 2)

    def test_number_of_melodies(self):
        source = Source.objects.first()
        chant_w_melody = Chant.objects.create(source=source, volpiano="1-a-b-c")
        chant = Chant.objects.create(source=source)
        self.assertEqual(source.number_of_melodies(), 1)

    def test_display_name(self):
        source = Source.objects.first()
        display_name = source.display_name
        name_str = source.__str__()
        self.assertEqual(display_name, name_str)

    def test_absolute_url(self):
        source = Source.objects.first()
        absolute_url = reverse("source-detail", args=[str(source.id)])
        self.assertEqual(source.get_absolute_url(), absolute_url)

class ChantSequenceSyncTest(TestCase):
    def test_chant_sequence_sync(self):
        # for each of the models:
        # retrieve all fields of that model
        # go through all of the fields and create a list of tuples of the following format:
        # [
        #    ("field name", "field type"),
        #    ("field name", "field type"), ...
        # ]

        # if the two models are defined such that
        # they specify the same fields (with the same name and type) in the same order,
        # we assert true

        chant_field_names = [(f.name, f.get_internal_type()) for f in Chant._meta.get_fields()]
        sequence_field_names = [(f.name, f.get_internal_type()) for f in Sequence._meta.get_fields()]
        self.assertEqual(chant_field_names, sequence_field_names)
