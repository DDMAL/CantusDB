from django.forms import ValidationError
from django.test import TestCase
from django.urls import reverse
from main_app.models import (
    Century,
    Chant,
    Feast,
    Genre,
    Service,
    Sequence,
    Source,
    SourceURL,
)
from .make_fakes import (
    make_fake_century,
    make_fake_chant,
    make_fake_feast,
    make_fake_genre,
    make_fake_service,
    make_fake_sequence,
    make_fake_source,
)

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
        source = make_fake_source()
        make_fake_chant(source=source)

    def test_get_ci_url(self):
        chant = Chant.objects.first()
        ci_url = chant.get_ci_url()
        ci_url_correct = "https://cantusindex.org/id/{}".format(chant.cantus_id)
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
                        None, [chant.genre.name, chant.feast.name, chant.service.name]
                    )
                )
            ),
        }
        self.assertEqual(weight_search_term_dict, expected_dict)

    def test_get_concordances(self):
        chant = Chant.objects.first()
        chant_with_same_cantus_id = make_fake_chant(
            cantus_id=chant.cantus_id, source=chant.source
        )
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

    def test_get_next_chant__same_folio_next_sequence_number(self):
        source = make_fake_source()
        current_folio = "001"
        chant1 = make_fake_chant(
            source=source,
            folio=current_folio,
            c_sequence=1,
        )
        chant2 = make_fake_chant(
            source=source,
            folio=current_folio,
            c_sequence=2,
        )
        self.assertEqual(chant1.get_next_chant(), chant2)

    def test_get_next_chant__recto_to_verso(self):
        source = make_fake_source()
        current_folio = "001r"
        next_folio = "001v"
        chant1 = make_fake_chant(
            source=source,
            folio=current_folio,
            c_sequence=1,
        )
        chant2 = make_fake_chant(
            source=source,
            folio=next_folio,
            c_sequence=1,
        )
        self.assertEqual(chant1.get_next_chant(), chant2)

    def test_get_next_chant__verso_to_recto(self):
        source2 = make_fake_source()
        current_folio = "555v"
        next_folio = "556r"
        chant1 = make_fake_chant(
            source=source2,
            folio=current_folio,
            c_sequence=1,
        )
        chant2 = make_fake_chant(
            source=source2,
            folio=next_folio,
            c_sequence=1,
        )
        self.assertEqual(chant1.get_next_chant(), chant2)

    def test_get_next_chant__one_numbered_page_to_the_next(self):
        source = make_fake_source()
        current_folio = "004"
        next_folio = "005"
        end_of_page_chant = make_fake_chant(
            source=source,
            folio=current_folio,
            c_sequence=2,
        )
        beginning_of_next_page_chant = make_fake_chant(
            source=source,
            folio=next_folio,
            c_sequence=1,
        )
        self.assertEqual(
            end_of_page_chant.get_next_chant(), beginning_of_next_page_chant
        )

    def test_get_next_chant__last_chant_in_manuscript(self):
        source = make_fake_source()
        last_folio_in_ms = "999r"
        last_chant_in_ms = make_fake_chant(
            source=source,
            folio=last_folio_in_ms,
            c_sequence=98,
        )
        self.assertIsNone(last_chant_in_ms.get_next_chant())

    def test_get_next_chant__collision(self):
        # if there are multiple chants with the same source, folio and c_sequence,
        # someone has messed up their data entry, and we should set next_chant to None
        source = make_fake_source()
        current_folio = "444"
        chant1 = make_fake_chant(
            source=source,
            folio=current_folio,
            c_sequence=1,
        )
        chant2a = make_fake_chant(
            source=source,
            folio=current_folio,
            c_sequence=2,
        )
        chant2b = make_fake_chant(
            source=source,
            folio=current_folio,
            c_sequence=2,
        )
        self.assertIsNone(chant1.get_next_chant())

    def test_get_next_chant__lacuna(self):
        # if pages from a manuscript have been lost, the lacuna (gap) is often
        # assigned to the previous folio and given a c_sequence of 99.
        source = make_fake_source()
        first_folio = "500v"
        second_folio = "501r"
        chant1 = make_fake_chant(
            source=source,
            folio=first_folio,
            c_sequence=51,
        )
        lacuna = make_fake_chant(
            source=source,
            folio=first_folio,
            c_sequence=99,
            manuscript_full_text_std_spelling="LACUNA",
        )
        chant3 = make_fake_chant(source=source, folio=second_folio, c_sequence=1)
        self.assertEqual(chant1.get_next_chant(), lacuna)
        self.assertEqual(lacuna.get_next_chant(), chant3)

    def test_incipit_generated_from_fulltext(self):
        """A chant with no existing incipit has one generated from its
        standardized-spelling fulltext upon save."""
        chant: Chant = make_fake_chant(
            manuscript_full_text_std_spelling="Incipit should be five words sheep headphones bongoes"
        )
        self.assertEqual(chant.incipit, "Incipit should be five words")

    def test_incipit_protected_when_not_proofread(self):
        """When a chant already has an incipit and its standardized-spelling
        fulltext is not proofread, changing the fulltext does not overwrite the
        incipit (issue #1803)."""
        chant: Chant = make_fake_chant(
            manuscript_full_text_std_spelling="Original curated incipit words here",
            manuscript_full_text_std_proofread=False,
        )
        original_incipit: str = chant.incipit
        chant.manuscript_full_text_std_spelling = (
            "Completely different replacement fulltext now"
        )
        chant.save()
        chant.refresh_from_db()
        self.assertEqual(chant.incipit, original_incipit)

    def test_incipit_updated_when_proofread(self):
        """Once the standardized-spelling fulltext is marked proofread, saving
        re-syncs the incipit to the fulltext."""
        chant: Chant = make_fake_chant(
            manuscript_full_text_std_spelling="Original curated incipit words here",
        )
        chant.manuscript_full_text_std_spelling = (
            "Corrected fulltext after proofreading is complete"
        )
        chant.manuscript_full_text_std_proofread = True
        chant.save()
        chant.refresh_from_db()
        self.assertEqual(chant.incipit, "Corrected fulltext after proofreading is")


class FeastModelTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        make_fake_feast()

    def test_object_name(self):
        feast = Feast.objects.first()
        self.assertEqual(str(feast), feast.name)

    def test_date_constraints(self):
        def create_fake_feast(month, day):
            make_fake_feast(name="fakeFeast", month=month, day=day)

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

    def test_update_prefix_field_signal(self):
        feast = make_fake_feast()
        feast_code = "12345678"
        expected_prefix = feast_code[:2]
        feast.feast_code = feast_code
        feast.save()
        feast.refresh_from_db()
        self.assertEqual(feast.feast_code, feast_code)
        self.assertEqual(feast.prefix, expected_prefix)

        feast.feast_code = None
        feast.save()
        feast.refresh_from_db()
        self.assertIs(feast.feast_code, None)
        self.assertEqual(feast.prefix, "")

        feast.feast_code = ""
        feast.save()
        feast.refresh_from_db()
        self.assertIs(feast.feast_code, "")
        self.assertEqual(feast.prefix, "")


class GenreModelTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        make_fake_genre()

    def test_string_representation(self):
        genre = Genre.objects.first()
        self.assertEqual(str(genre), f"[{genre.name}] {genre.description}")

    def test_display_name(self):
        genre = Genre.objects.first()
        display_name = genre.display_name
        name_str = genre.__str__()
        self.assertEqual(display_name, name_str)

    def test_absolute_url(self):
        genre = Genre.objects.first()
        absolute_url = reverse("genre-detail", args=[str(genre.id)])
        self.assertEqual(genre.get_absolute_url(), absolute_url)


class ServiceModelTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        make_fake_service()

    def test_object_string_representation(self):
        service = Service.objects.first()
        self.assertEqual(str(service), f"[{service.name}] {service.description}")

    def test_display_name(self):
        service = Service.objects.first()
        display_name = service.display_name
        name_str = service.__str__()
        self.assertEqual(display_name, name_str)

    def test_absolute_url(self):
        service = Service.objects.first()
        absolute_url = reverse("service-detail", args=[str(service.id)])
        self.assertEqual(service.get_absolute_url(), absolute_url)


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

    def test_incipit_signal(self):
        """Test whether a sequence's incipit is updated to reflect its title upon save"""
        sequence: Sequence = make_fake_sequence()
        title: str = "Incipit titulus esse debet"
        expected_incipit: str = title
        sequence.title = title
        sequence.save()
        sequence.refresh_from_db()
        observed_incipit: str = sequence.incipit
        self.assertEqual(observed_incipit, expected_incipit)


class SourceModelTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        make_fake_source()

    def test_number_of_chants(self):
        source = Source.objects.first()
        chant = make_fake_chant(source=source)
        sequence = make_fake_sequence(source=source)
        self.assertIn(chant, source.chant_set.all())
        self.assertIn(sequence, source.sequence_set.all())
        self.assertEqual(source.number_of_chants, 2)

    def test_number_of_melodies(self):
        source = Source.objects.first()
        make_fake_chant(source=source, volpiano="1-a-b-c")
        make_fake_chant(source=source, volpiano=None)
        self.assertEqual(source.number_of_melodies, 1)

    def test_display_name(self):
        source = Source.objects.first()
        display_name = source.display_name
        name_str = source.__str__()
        self.assertEqual(display_name, name_str)

    def test_absolute_url(self):
        source = Source.objects.first()
        absolute_url = reverse("source-detail", args=[str(source.id)])
        self.assertEqual(source.get_absolute_url(), absolute_url)


class SourceExternalImagesTest(TestCase):
    """Tests for the two properties that reconcile the legacy `image_link`
    field with `SourceURL(EXTERNAL_IMAGES)`, which supersedes it.
    """

    LEGACY = "https://example.com/legacy-images"
    SOURCE_URL = "https://example.com/source-url-images"

    def _make_source_url(self, source, url_type, url=SOURCE_URL):
        return SourceURL.objects.create(source=source, url=url, url_type=url_type)

    def test_legacy_field_used_when_no_source_links(self):
        source = make_fake_source(image_link=self.LEGACY)
        self.assertEqual(source.external_images_url, self.LEGACY)
        self.assertIs(source.show_legacy_image_link, True)

    def test_source_url_supersedes_legacy_field(self):
        source = make_fake_source(image_link=self.LEGACY)
        self._make_source_url(source, SourceURL.URLTypes.EXTERNAL_IMAGES)
        # Pages rendering a single link follow the SourceURL...
        self.assertEqual(source.external_images_url, self.SOURCE_URL)
        # ...and pages that render source_links themselves drop the legacy one,
        # rather than showing the same gallery twice.
        self.assertIs(source.show_legacy_image_link, False)

    def test_source_url_used_when_legacy_field_empty(self):
        source = make_fake_source(image_link="")
        self._make_source_url(source, SourceURL.URLTypes.EXTERNAL_IMAGES)
        self.assertEqual(source.external_images_url, self.SOURCE_URL)
        self.assertIs(source.show_legacy_image_link, False)

    def test_other_url_types_do_not_supersede_legacy_field(self):
        source = make_fake_source(image_link=self.LEGACY)
        self._make_source_url(source, SourceURL.URLTypes.IIIF_MANIFEST)
        self._make_source_url(source, SourceURL.URLTypes.HOST_INSTITUTION_RECORD)
        self.assertEqual(source.external_images_url, self.LEGACY)
        self.assertIs(source.show_legacy_image_link, True)

    def test_no_images_anywhere(self):
        source = make_fake_source(image_link="")
        # Both properties are used as `{% if %}` conditions, so a blank
        # image_link must not leak "" through as the URL.
        self.assertIsNone(source.external_images_url)
        self.assertIs(source.show_legacy_image_link, False)

    def test_null_legacy_field(self):
        # image_link is null=True, so None is reachable as well as "".
        source = make_fake_source(image_link=None)
        self.assertIsNone(source.external_images_url)
        self.assertIs(source.show_legacy_image_link, False)

    def test_reads_prefetch_cache_without_extra_queries(self):
        # Both properties iterate source_links in Python rather than filtering
        # in SQL precisely so a prefetching view pays no per-source query. A
        # .filter() here would still pass every test above.
        source = make_fake_source(image_link=self.LEGACY)
        self._make_source_url(source, SourceURL.URLTypes.EXTERNAL_IMAGES)
        prefetched = Source.objects.prefetch_related("source_links").get(id=source.id)
        with self.assertNumQueries(0):
            self.assertEqual(prefetched.external_images_url, self.SOURCE_URL)
            self.assertIs(prefetched.show_legacy_image_link, False)


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

        chant_field_names = [
            (f.name, f.get_internal_type()) for f in Chant._meta.get_fields()
        ]
        sequence_field_names = [
            (f.name, f.get_internal_type()) for f in Sequence._meta.get_fields()
        ]
        self.assertEqual(chant_field_names, sequence_field_names)
