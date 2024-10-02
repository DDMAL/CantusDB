"""
Test views in views/source.py
"""

from faker import Faker

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

from main_app.models import Source, Segment, Sequence, Chant, Differentia, Century
from main_app.tests.make_fakes import (
    make_fake_source,
    make_fake_segment,
    make_fake_feast,
    make_fake_chant,
    make_fake_service,
    make_random_string,
    make_fake_sequence,
    make_fake_genre,
    get_random_search_term,
    make_fake_institution,
    make_fake_provenance,
    make_fake_century,
    add_accents_to_string,
)

# Create a Faker instance with locale set to Latin
faker = Faker("la")


class SourceCreateViewTest(TestCase):
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
        # unless a segment is specified when a source is created, the source is automatically assigned
        # to the segment with the name "CANTUS Database" - to prevent errors, we must make sure that
        # such a segment exists
        Segment.objects.create(name="CANTUS Database")

    def test_url_and_templates(self):
        response = self.client.get(reverse("source-create"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "source_create.html")

    def test_create_source(self):
        hinst = make_fake_institution(siglum="FA-Ke")
        response = self.client.post(
            reverse("source-create"),
            {
                "shelfmark": "test-shelfmark",  # shelfmark is a required field
                "holding_institution": hinst.id,  # holding institution is a required field
                "source_completeness": "1",  # required field
                "production_method": "1",  # required field
            },
        )

        self.assertEqual(response.status_code, 302)
        created_source = Source.objects.get(shelfmark="test-shelfmark")
        self.assertRedirects(
            response,
            reverse("source-detail", args=[created_source.id]),
        )

        source = Source.objects.first()
        self.assertEqual(source.shelfmark, "test-shelfmark")


class SourceEditViewTest(TestCase):
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
        hinst = make_fake_institution(siglum="FA-Ke")

        response = self.client.post(
            reverse("source-edit", args=[source.id]),
            {
                "shelfmark": "test-shelfmark",  # shelfmark is a required field,
                "holding_institution": hinst.id,  # holding institution is a required field
                "source_completeness": "1",  # required field
                "production_method": "1",  # required field
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse("source-detail", args=[source.id]))
        source.refresh_from_db()
        self.assertEqual(source.shelfmark, "test-shelfmark")


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
        bower_segment = Segment.objects.create(id=4064, name="Bower Sequence Database")
        source = make_fake_source(
            shelfmark="a sequence source", published=True, segment=bower_segment
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
        expected_result = [
            ("001r", feast_1.id, feast_1.name),
            ("001v", feast_2.id, feast_2.name),
            ("002r", feast_1.id, feast_1.name),
        ]
        self.assertEqual(response.context["feasts_with_folios"], expected_result)

    def test_context_sequences(self):
        # create a sequence source and several sequences in it
        source = make_fake_source(
            segment=Segment.objects.create(id=4064, name="Bower Sequence Database"),
            shelfmark="a sequence source",
            published=True,
        )
        sequence = Sequence.objects.create(source=source)
        # request the page
        response = self.client.get(reverse("source-detail", args=[source.id]))
        # the sequence should be in the list of sequences
        self.assertIn(sequence, response.context["sequences"])
        # the list of sequences should be ordered by the "sequence" field
        self.assertEqual(response.context["sequences"].query.order_by, ("s_sequence",))

    def test_published_vs_unpublished(self):
        source = make_fake_source(published=False)
        response_1 = self.client.get(reverse("source-detail", args=[source.id]))
        self.assertEqual(response_1.status_code, 403)

        source.published = True
        source.save()
        response_2 = self.client.get(reverse("source-detail", args=[source.id]))
        self.assertEqual(response_2.status_code, 200)

    def test_chant_list_link(self):
        cantus_segment = make_fake_segment(id=4063)
        cantus_source = make_fake_source(segment=cantus_segment)
        chant_list_link = reverse("browse-chants", args=[cantus_source.id])

        cantus_source_response = self.client.get(
            reverse("source-detail", args=[cantus_source.id])
        )
        cantus_source_html = str(cantus_source_response.content)
        self.assertIn(chant_list_link, cantus_source_html)

        bower_segment = make_fake_segment(id=4064)
        bower_source = make_fake_source(segment=bower_segment)
        bower_chant_list_link = reverse("browse-chants", args=[bower_source.id])
        bower_source_response = self.client.get(
            reverse("source-detail", args=[bower_source.id])
        )
        bower_source_html = str(bower_source_response.content)
        self.assertNotIn(bower_chant_list_link, bower_source_html)


class SourceInventoryViewTest(TestCase):
    def test_url_and_templates(self):
        source = make_fake_source()
        response = self.client.get(reverse("source-inventory", args=[source.id]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "full_inventory.html")

    def test_published_vs_unpublished(self):
        source = make_fake_source()

        source.published = True
        source.save()
        response = self.client.get(reverse("source-inventory", args=[source.id]))
        self.assertEqual(response.status_code, 200)

        source.published = False
        source.save()
        response = self.client.get(reverse("source-inventory", args=[source.id]))
        self.assertEqual(response.status_code, 403)

    def test_chant_source_queryset(self):
        chant_source = make_fake_source()
        chant = make_fake_chant(source=chant_source)
        response = self.client.get(reverse("source-inventory", args=[chant_source.id]))
        self.assertEqual(chant_source, response.context["source"])
        self.assertIn(chant, response.context["chants"])

    def test_sequence_source_queryset(self):
        seq_source = make_fake_source(
            segment=Segment.objects.create(id=4064, name="Clavis Sequentiarium"),
            shelfmark="a sequence source",
            published=True,
        )
        sequence = Sequence.objects.create(source=seq_source)
        response = self.client.get(reverse("source-inventory", args=[seq_source.id]))
        self.assertEqual(seq_source, response.context["source"])
        self.assertIn(sequence, response.context["chants"])

    def test_shelfmark_column(self):
        shelfmark = "Sigl-01"
        source = make_fake_source(published=True, shelfmark=shelfmark)
        source_shelfmark = source.shelfmark
        make_fake_chant(source=source)
        response = self.client.get(reverse("source-inventory", args=[source.id]))
        html = str(response.content)
        self.assertIn(shelfmark, html)
        expected_html_substring = (
            f'<td title="{source.heading}">{source.short_heading}</td>'
        )
        self.assertIn(expected_html_substring, html)

    def test_marginalia_column(self):
        source = make_fake_source(published=True)
        chant = make_fake_chant(source=source)
        marginalia = chant.marginalia
        response = self.client.get(reverse("source-inventory", args=[source.id]))
        html = str(response.content)
        self.assertIn(marginalia, html)
        expected_html_substring = f"<td>{marginalia}</td>"
        self.assertIn(expected_html_substring, html)

    def test_folio_column(self):
        source = make_fake_source(published=True)
        chant = make_fake_chant(source=source)
        folio = chant.folio
        response = self.client.get(reverse("source-inventory", args=[source.id]))
        html = str(response.content)
        self.assertIn(folio, html)
        expected_html_substring = f"<td>{folio}</td>"
        self.assertIn(expected_html_substring, html)

    def test_sequence_column_for_chant_source(self):
        source = make_fake_source(published=True)
        chant = make_fake_chant(source=source)
        c_sequence = str(chant.c_sequence)
        response = self.client.get(reverse("source-inventory", args=[source.id]))
        html = str(response.content)
        self.assertIn(c_sequence, html)

    def test_sequence_column_for_sequence_source(self):
        bower_segment = Segment.objects.create(id=4064, name="Bower Sequence Database")
        source = make_fake_source(published=True, segment=bower_segment)
        sequence = make_fake_sequence(source=source)
        s_sequence = sequence.s_sequence
        response = self.client.get(reverse("source-inventory", args=[source.id]))
        html = str(response.content)
        self.assertIn(s_sequence, html)

    def test_feast_column(self):
        source = make_fake_source(published=True)
        feast = make_fake_feast()
        feast_name = feast.name
        feast_description = feast.description
        make_fake_chant(
            source=source,
            feast=feast,
        )
        response = self.client.get(reverse("source-inventory", args=[source.id]))
        html = str(response.content)
        self.assertIn(feast_name, html)
        self.assertIn(feast_description, html)

    def test_service_column(self):
        source = make_fake_source(published=True)
        service = make_fake_service()
        service_name = service.name
        service_description = service.description
        fulltext = "manuscript full text"
        make_fake_chant(
            source=source,
            manuscript_full_text_std_spelling=fulltext,
            service=service,
        )
        response = self.client.get(reverse("source-inventory", args=[source.id]))
        html = str(response.content)
        self.assertIn(service_name, html)
        self.assertIn(service_description, html)

    def test_genre_column(self):
        source = make_fake_source(published=True)
        genre = make_fake_genre()
        genre_name = genre.name
        genre_description = genre.description
        make_fake_chant(
            source=source,
            genre=genre,
        )
        response = self.client.get(reverse("source-inventory", args=[source.id]))
        html = str(response.content)
        self.assertIn(genre_name, html)
        self.assertIn(genre_description, html)

    def test_position_column(self):
        source = make_fake_source(published=True)
        chant = make_fake_chant(
            source=source,
        )
        position = chant.position
        response = self.client.get(reverse("source-inventory", args=[source.id]))
        html = str(response.content)
        self.assertIn(position, html)

    def test_incipit_column_for_chant_source(self):
        source = make_fake_source(published=True)
        chant = make_fake_chant(source=source)
        incipit = chant.incipit
        url = reverse("chant-detail", args=[chant.id])
        response = self.client.get(reverse("source-inventory", args=[source.id]))
        html = str(response.content)
        self.assertIn(incipit, html)
        self.assertIn(url, html)
        expected_html_substring = f'<a href="{url}" target="_blank">{incipit}</a>'
        self.assertIn(expected_html_substring, html)

    def test_incipit_column_for_sequence_source(self):
        bower_segment = Segment.objects.create(id=4064, name="Bower Sequence Database")
        source = make_fake_source(published=True, segment=bower_segment)
        sequence = make_fake_sequence(source=source)
        incipit = sequence.incipit
        url = reverse("sequence-detail", args=[sequence.id])
        response = self.client.get(reverse("source-inventory", args=[source.id]))
        html = str(response.content)
        self.assertIn(incipit, html)
        self.assertIn(url, html)
        expected_html_substring = f'<a href="{url}" target="_blank">{incipit}</a>'
        self.assertIn(expected_html_substring, html)

    def test_cantus_id_column(self):
        source = make_fake_source(published=True)
        chant = make_fake_chant(source=source)
        cantus_id = chant.cantus_id
        response = self.client.get(reverse("source-inventory", args=[source.id]))
        html = str(response.content)
        self.assertIn(cantus_id, html)
        expected_html_substring = f"<td>{cantus_id}</td>"
        self.assertIn(expected_html_substring, html)

    def test_mode_column(self):
        source = make_fake_source(published=True)
        chant = make_fake_chant(
            source=source,
        )
        mode = "this is the mode"  # not a representative value, but
        # single numerals are found elsewhere in the template
        chant.mode = mode
        chant.save()
        response = self.client.get(reverse("source-inventory", args=[source.id]))
        html = str(response.content)
        self.assertIn(mode, html)
        expected_html_substring = f"<td>{mode}</td>"
        self.assertIn(expected_html_substring, html)

    def test_diff_column(self):
        source = make_fake_source(published=True)
        differentia = "this is a differentia"  # not a representative value, but
        # most differentia are one or two characters, likely to be found elsewhere
        # in the template
        make_fake_chant(
            source=source,
            differentia=differentia,
        )
        response = self.client.get(reverse("source-inventory", args=[source.id]))
        html = str(response.content)
        self.assertIn(differentia, html)
        expected_html_substring = f"<td>{differentia}</td>"
        self.assertIn(expected_html_substring, html)

    def test_dd_column(self):
        source: Source = make_fake_source(published=True)
        diff_id: str = make_random_string(3, "0123456789") + make_random_string(
            1, "abcd"
        )  # e.g., "012a"
        diff_db: Differentia = Differentia.objects.create(differentia_id=diff_id)
        chant: Chant = make_fake_chant(
            source=source,
        )
        chant.diff_db = diff_db
        chant.save()

        response = self.client.get(reverse("source-inventory", args=[source.id]))
        html: str = str(response.content)
        self.assertIn(diff_id, html)
        expected_html_substring: str = (
            f'<a href="https://differentiaedatabase.ca/differentia/{diff_id}" target="_blank">'
        )
        self.assertIn(expected_html_substring, html)

    def test_redirect_with_source_parameter(self):
        cantus_segment = make_fake_segment(id=4063)
        source = make_fake_source(segment=cantus_segment)
        source_id = source.id

        url = reverse("redirect-source-inventory")
        response = self.client.get(f"{url}?source={source_id}")
        self.assertRedirects(
            response, reverse("source-inventory", args=[source_id]), status_code=301
        )

    def test_redirect_without_source_parameter(self):
        url = reverse("redirect-source-inventory")
        # Omitting the source parameter to simulate a bad request
        response = self.client.get(url)
        self.assertEqual(response.status_code, 400)
        self.assertTemplateUsed(response, "400.html")


class SourceBrowseChantsViewTest(TestCase):
    def test_url_and_templates(self):
        cantus_segment = make_fake_segment(id=4063)
        source = make_fake_source(segment=cantus_segment)
        response = self.client.get(reverse("browse-chants", args=[source.id]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "base.html")
        self.assertTemplateUsed(response, "browse_chants.html")

    def test_published_vs_unpublished(self):
        cantus_segment = make_fake_segment(id=4063)

        published_source = make_fake_source(segment=cantus_segment, published=True)
        response_1 = self.client.get(
            reverse("browse-chants", args=[published_source.id])
        )
        self.assertEqual(response_1.status_code, 200)

        unpublished_source = make_fake_source(segment=cantus_segment, published=False)
        response_2 = self.client.get(
            reverse("browse-chants", args=[unpublished_source.id])
        )
        self.assertEqual(response_2.status_code, 403)

    def test_visibility_by_segment(self):
        cantus_segment = make_fake_segment(id=4063)
        cantus_source = make_fake_source(segment=cantus_segment, published=True)
        response_1 = self.client.get(reverse("browse-chants", args=[cantus_source.id]))
        self.assertEqual(response_1.status_code, 200)

        # The chant list ("Browse Chants") page should only be visitable
        # for sources in the CANTUS Database segment, as sources in the Bower
        # segment contain no chants
        bower_segment = make_fake_segment(id=4064)
        bower_source = make_fake_source(segment=bower_segment, published=True)
        response_1 = self.client.get(reverse("browse-chants", args=[bower_source.id]))
        self.assertEqual(response_1.status_code, 404)

    def test_filter_by_source(self):
        cantus_segment = make_fake_segment(id=4063)
        source = make_fake_source(segment=cantus_segment)
        another_source = make_fake_source(segment=cantus_segment)
        chant_in_source = Chant.objects.create(source=source)
        chant_in_another_source = Chant.objects.create(source=another_source)
        response = self.client.get(reverse("browse-chants", args=[source.id]))
        chants = response.context["chants"]
        self.assertIn(chant_in_source, chants)
        self.assertNotIn(chant_in_another_source, chants)

    def test_filter_by_feast(self):
        cantus_segment = make_fake_segment(id=4063)
        source = make_fake_source(segment=cantus_segment)
        feast = make_fake_feast()
        another_feast = make_fake_feast()
        chant_in_feast = Chant.objects.create(source=source, feast=feast)
        chant_in_another_feast = Chant.objects.create(
            source=source, feast=another_feast
        )
        response = self.client.get(
            reverse("browse-chants", args=[source.id]), {"feast": feast.id}
        )
        chants = response.context["chants"]
        self.assertIn(chant_in_feast, chants)
        self.assertNotIn(chant_in_another_feast, chants)

    def test_filter_by_genre(self):
        cantus_segment = make_fake_segment(id=4063)
        source = make_fake_source(segment=cantus_segment)
        genre = make_fake_genre()
        another_genre = make_fake_genre()
        chant_in_genre = Chant.objects.create(source=source, genre=genre)
        chant_in_another_genre = Chant.objects.create(
            source=source, genre=another_genre
        )
        response = self.client.get(
            reverse("browse-chants", args=[source.id]), {"genre": genre.id}
        )
        chants = response.context["chants"]
        self.assertIn(chant_in_genre, chants)
        self.assertNotIn(chant_in_another_genre, chants)

    def test_filter_by_folio(self):
        cantus_segment = make_fake_segment(id=4063)
        source = make_fake_source(segment=cantus_segment)
        chant_on_folio = Chant.objects.create(source=source, folio="001r")
        chant_on_another_folio = Chant.objects.create(source=source, folio="002r")
        response = self.client.get(
            reverse("browse-chants", args=[source.id]), {"folio": "001r"}
        )
        chants = response.context["chants"]
        self.assertIn(chant_on_folio, chants)
        self.assertNotIn(chant_on_another_folio, chants)

    def test_search_full_text(self):
        cantus_segment = make_fake_segment(id=4063)
        source = make_fake_source(segment=cantus_segment)
        chant = Chant.objects.create(
            source=source, manuscript_full_text=faker.sentence()
        )
        search_term = get_random_search_term(chant.manuscript_full_text)
        response = self.client.get(
            reverse("browse-chants", args=[source.id]), {"search_text": search_term}
        )
        self.assertIn(chant, response.context["chants"])

    def test_search_incipit(self):
        cantus_segment = make_fake_segment(id=4063)
        source = make_fake_source(segment=cantus_segment)
        chant = Chant.objects.create(
            source=source,
            incipit=faker.sentence(),
        )
        search_term = get_random_search_term(chant.incipit)
        response = self.client.get(
            reverse("browse-chants", args=[source.id]), {"search_text": search_term}
        )
        self.assertIn(chant, response.context["chants"])

    def test_search_full_text_std_spelling(self):
        cantus_segment = make_fake_segment(id=4063)
        source = make_fake_source(segment=cantus_segment)
        chant = Chant.objects.create(
            source=source,
            manuscript_full_text_std_spelling=faker.sentence(),
        )
        search_term = get_random_search_term(chant.manuscript_full_text_std_spelling)
        response = self.client.get(
            reverse("browse-chants", args=[source.id]), {"search_text": search_term}
        )
        self.assertIn(chant, response.context["chants"])

    def test_context_source(self):
        cantus_segment = make_fake_segment(id=4063)
        source = make_fake_source(segment=cantus_segment)
        response = self.client.get(reverse("browse-chants", args=[source.id]))
        self.assertEqual(source, response.context["source"])

    def test_context_folios(self):
        cantus_segment = make_fake_segment(id=4063)
        source = make_fake_source(segment=cantus_segment)
        Chant.objects.create(source=source, folio="001r")
        Chant.objects.create(source=source, folio="001r")
        Chant.objects.create(source=source, folio="001v")
        Chant.objects.create(source=source, folio="001v")
        Chant.objects.create(source=source, folio="002r")
        Chant.objects.create(source=source, folio="002v")
        response = self.client.get(reverse("browse-chants", args=[source.id]))
        # the element in "folios" should be unique and ordered in this way
        folios = response.context["folios"]
        self.assertEqual(list(folios), ["001r", "001v", "002r", "002v"])

    def test_context_feasts_with_folios(self):
        cantus_segment = make_fake_segment(id=4063)
        source = make_fake_source(segment=cantus_segment)
        feast_1 = make_fake_feast()
        feast_2 = make_fake_feast()
        Chant.objects.create(source=source, folio="001r", feast=feast_1)
        Chant.objects.create(source=source, folio="001r", feast=feast_1)
        Chant.objects.create(source=source, folio="001v", feast=feast_2)
        Chant.objects.create(source=source, folio="001v")
        Chant.objects.create(source=source, folio="001v", feast=feast_2)
        Chant.objects.create(source=source, folio="002r", feast=feast_1)
        response = self.client.get(reverse("browse-chants", args=[source.id]))
        # context "feasts_with_folios" is a list of tuples
        # it records the folios where the feast changes
        expected_result = [
            ("001r", feast_1.id, feast_1.name),
            ("001v", feast_2.id, feast_2.name),
            ("002r", feast_1.id, feast_1.name),
        ]
        self.assertEqual(response.context["feasts_with_folios"], expected_result)

    def test_redirect_with_source_parameter(self):
        cantus_segment = make_fake_segment(id=4063)
        source = make_fake_source(segment=cantus_segment)
        source_id = source.id

        url = reverse("redirect-chants")
        response = self.client.get(f"{url}?source={source_id}")
        self.assertRedirects(
            response, reverse("browse-chants", args=[source_id]), status_code=301
        )

    def test_redirect_without_source_parameter(self):
        url = reverse("redirect-chants")

        # Omitting the source parameter to simulate a bad request
        response = self.client.get(url)
        self.assertEqual(response.status_code, 400)
        self.assertTemplateUsed(response, "400.html")


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
        published_source = make_fake_source(
            published=True, shelfmark="published source"
        )
        private_source = make_fake_source(published=False, shelfmark="private source")
        response = self.client.get(reverse("source-list"))
        sources = response.context["sources"]
        self.assertIn(published_source, sources)
        self.assertNotIn(private_source, sources)

    def test_filter_by_segment(self):
        """The source list can be filtered by `segment`, `country`, `provenance`, `century`, and `full_source`"""
        cantus_segment = make_fake_segment(name="cantus")
        clavis_segment = make_fake_segment(name="clavis")
        chant_source = make_fake_source(
            segment=cantus_segment, shelfmark="chant source", published=True
        )
        seq_source = make_fake_source(
            segment=clavis_segment, shelfmark="sequence source", published=True
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

    def test_filter_by_country(self):
        hold_inst_austria = make_fake_institution(country="Austria")
        hold_inst_germany = make_fake_institution(country="Germany")
        austria_source = make_fake_source(
            holding_institution=hold_inst_austria,
            published=True,
            shelfmark="source from Austria",
        )
        germany_source = make_fake_source(
            holding_institution=hold_inst_germany,
            published=True,
            shelfmark="source from Germany",
        )
        no_country_source = make_fake_source(
            holding_institution=None,
            published=True,
            shelfmark="source with no country",
        )

        # Display sources from Austria only
        response = self.client.get(reverse("source-list"), {"country": "Austria"})
        sources = response.context["sources"]
        self.assertIn(austria_source, sources)
        self.assertNotIn(germany_source, sources)
        self.assertNotIn(no_country_source, sources)

        # Display sources from Germany only
        response = self.client.get(reverse("source-list"), {"country": "Germany"})
        sources = response.context["sources"]
        self.assertIn(germany_source, sources)
        self.assertNotIn(austria_source, sources)
        self.assertNotIn(no_country_source, sources)

        # Display sources with no country filter (all published sources)
        response = self.client.get(reverse("source-list"))
        sources = response.context["sources"]
        self.assertIn(austria_source, sources)
        self.assertIn(germany_source, sources)
        self.assertIn(no_country_source, sources)

    def test_filter_by_provenance(self):
        aachen = make_fake_provenance()
        albi = make_fake_provenance()
        aachen_source = make_fake_source(
            provenance=aachen,
            published=True,
            shelfmark="source originated in Aachen",
        )
        albi_source = make_fake_source(
            provenance=albi,
            published=True,
            shelfmark="source originated in Albi",
        )
        no_provenance_source = make_fake_source(
            published=True,
            provenance=None,
            shelfmark="source with empty provenance",
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

        ninth_century_source = make_fake_source(
            published=True,
            shelfmark="source",
        )
        ninth_century_source.century.set([ninth_century])

        ninth_century_first_half_source = make_fake_source(
            published=True,
            shelfmark="source",
        )
        ninth_century_first_half_source.century.set([ninth_century_first_half])

        multiple_century_source = make_fake_source(
            published=True,
            shelfmark="source",
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
        full_source = make_fake_source(
            full_source=True,
            published=True,
            shelfmark="full source",
        )
        fragment = make_fake_source(
            full_source=False,
            published=True,
            shelfmark="fragment",
        )
        unknown = make_fake_source(
            full_source=None,
            published=True,
            shelfmark="full_source field is empty",
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
        """The "general search" field searches in `title`, `shelfmark`, `description`, and `summary`"""
        source = make_fake_source(
            shelfmark=faker.sentence(),
            published=True,
        )
        search_term = get_random_search_term(source.shelfmark)
        response = self.client.get(reverse("source-list"), {"general": search_term})
        self.assertIn(source, response.context["sources"])

        # Test that postgres searches unaccented version of title
        unaccented_title = source.shelfmark
        accented_title = add_accents_to_string(unaccented_title)
        source.title = accented_title
        source.save()
        response = self.client.get(reverse("source-list"), {"general": search_term})
        self.assertIn(source, response.context["sources"])

    def test_search_by_shelfmark(self):
        hinst = make_fake_institution(name="Fake Institution", siglum="FA-Ke")
        source = make_fake_source(
            published=True, shelfmark="title", holding_institution=hinst
        )
        search_term = get_random_search_term(source.shelfmark)
        response = self.client.get(reverse("source-list"), {"general": search_term})
        self.assertIn(source, response.context["sources"])

        # Test that postgres searches unaccented version of shelfmark
        unaccented_siglum = source.shelfmark
        accented_siglum = add_accents_to_string(unaccented_siglum)
        source.siglum = accented_siglum
        source.save()
        response = self.client.get(reverse("source-list"), {"general": search_term})
        self.assertIn(source, response.context["sources"])

    def test_search_by_description(self):
        source = make_fake_source(
            description=faker.sentence(),
            published=True,
            shelfmark="title",
        )
        search_term = get_random_search_term(source.description)
        response = self.client.get(reverse("source-list"), {"general": search_term})
        self.assertIn(source, response.context["sources"])

        # Test that postgres searches unaccented version of description
        unaccented_description = source.description
        accented_description = add_accents_to_string(unaccented_description)
        source.title = accented_description
        source.save()
        response = self.client.get(reverse("source-list"), {"general": search_term})
        self.assertIn(source, response.context["sources"])

    def test_search_by_summary(self):
        source = make_fake_source(
            summary=faker.sentence(),
            published=True,
            shelfmark="title",
        )
        search_term = get_random_search_term(source.summary)
        response = self.client.get(reverse("source-list"), {"general": search_term})
        self.assertIn(source, response.context["sources"])

        # Test that postgres searches unaccented version of summary
        unaccented_summary = source.summary
        accented_summary = add_accents_to_string(unaccented_summary)
        source.title = accented_summary
        source.save()
        response = self.client.get(reverse("source-list"), {"general": search_term})
        self.assertIn(source, response.context["sources"])

    def test_search_by_indexing_notes(self):
        """The "indexing notes" field searches in `indexing_notes` and indexer/editor related fields"""
        source = make_fake_source(
            indexing_notes=faker.sentence(),
            published=True,
            shelfmark="title",
        )
        search_term = get_random_search_term(source.indexing_notes)
        response = self.client.get(reverse("source-list"), {"indexing": search_term})
        self.assertIn(source, response.context["sources"])

        # Test that postgres searches unaccented version of indexing_notes
        unaccented_indexing_notes = source.indexing_notes
        accented_indexing_notes = add_accents_to_string(unaccented_indexing_notes)
        source.shelfmark = accented_indexing_notes
        source.save()
        response = self.client.get(reverse("source-list"), {"general": search_term})
        self.assertIn(source, response.context["sources"])

    def test_ordering(self) -> None:
        """
        Order is currently available by country, city + institution name (parameter:
        "city_institution"), and siglum + shelfmark. Siglum + shelfmark is the default.
        """
        # Create a bunch of sources
        sources = []
        for _ in range(10):
            sources.append(make_fake_source())
        # Default ordering is by siglum and shelfmark, ascending
        with self.subTest("Default ordering"):
            response = self.client.get(reverse("source-list"))
            response_sources = response.context["sources"]
            expected_source_order = sorted(
                sources,
                key=lambda source: (
                    source.holding_institution.siglum,
                    source.shelfmark,
                ),
            )
            self.assertEqual(
                list(expected_source_order),
                list(response_sources),
            )
            response_reverse = self.client.get(reverse("source-list"), {"sort": "desc"})
            response_sources_reverse = response_reverse.context["sources"]
            self.assertEqual(
                list(reversed(expected_source_order)),
                list(response_sources_reverse),
            )
        with self.subTest("Order by country, ascending"):
            response = self.client.get(reverse("source-list"), {"order": "country"})
            response_sources = response.context["sources"]
            expected_source_order = sorted(
                sources, key=lambda source: source.holding_institution.country
            )
            self.assertEqual(
                list(expected_source_order),
                list(response_sources),
            )
            response_reverse = self.client.get(
                reverse("source-list"), {"order": "country", "sort": "desc"}
            )
            response_sources_reverse = response_reverse.context["sources"]
            self.assertEqual(
                list(reversed(expected_source_order)),
                list(response_sources_reverse),
            )
        with self.subTest("Order by city and institution name, ascending"):
            response = self.client.get(
                reverse("source-list"), {"order": "city_institution"}
            )
            response_sources = response.context["sources"]
            expected_source_order = sorted(
                sources,
                key=lambda source: (
                    source.holding_institution.city,
                    source.holding_institution.name,
                ),
            )
            self.assertEqual(
                list(expected_source_order),
                list(response_sources),
            )
            response_reverse = self.client.get(
                reverse("source-list"), {"order": "city_institution", "sort": "desc"}
            )
            response_sources_reverse = response_reverse.context["sources"]
            self.assertEqual(
                list(reversed(expected_source_order)),
                list(response_sources_reverse),
            )
