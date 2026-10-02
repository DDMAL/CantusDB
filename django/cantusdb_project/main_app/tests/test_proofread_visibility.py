"""
Unproofread volpiano and full texts are hidden from anonymous users on every
page and export, and shown to logged-in users (#1100). The first attempt at
this (#1121) was reverted because some surfaces still leaked hidden fields, so
each surface is checked here against the same chant.
"""

import csv
import io
import json

from django.conf import settings
from django.test import TestCase
from django.urls import reverse

from main_app.management.commands import update_cached_concordances
from main_app.models import Chant
from main_app.proofread_visibility import hide_unproofread
from main_app.tests.make_fakes import (
    PROOFREAD,
    make_fake_chant,
    make_fake_segment,
    make_fake_source,
    make_fake_user,
)

# The incipit is generated from the first five words of the standardized
# spelling, so the words checked for come after those.
STD_MARK = "stdmarkword"
MS_MARK = "msmarkword"
STD_TEXT = f"Ave gratia plena dominus tecum {STD_MARK}"
MS_TEXT = f"Aue gratia plena dominus tecum {MS_MARK}"
# "1---" is a clef; `generate_volpiano_notes` leaves the notes searched below.
VOLPIANO = "1---defgab"
NOTES = "defgab"
CANTUS_ID = "991100"


def make_hidden_chant(**kwargs) -> Chant:
    """A chant in a published source whose volpiano and full texts are unproofread."""
    return make_fake_chant(
        source=make_fake_source(published=True),
        cantus_id=CANTUS_ID,
        manuscript_full_text_std_spelling=STD_TEXT,
        manuscript_full_text=MS_TEXT,
        manuscript_syllabized_full_text=None,
        volpiano=VOLPIANO,
        **kwargs,
    )


class HideUnproofreadTest(TestCase):
    def test_blanks_unticked_and_never_set_fields(self):
        chant = make_hidden_chant(manuscript_full_text_std_proofread=None)
        hide_unproofread(chant)
        self.assertIsNone(chant.manuscript_full_text_std_spelling)
        self.assertIsNone(chant.manuscript_full_text)
        self.assertIsNone(chant.volpiano)
        self.assertIsNone(chant.volpiano_notes)

    def test_keeps_proofread_fields(self):
        chant = make_hidden_chant(**PROOFREAD)
        hide_unproofread(chant)
        self.assertEqual(chant.manuscript_full_text_std_spelling, STD_TEXT)
        self.assertEqual(chant.manuscript_full_text, MS_TEXT)
        self.assertEqual(chant.volpiano, VOLPIANO)


class ProofreadVisibilityTest(TestCase):
    """Each test checks one surface, anonymously and then logged in."""

    @classmethod
    def setUpTestData(cls):
        # The Browse Chants page needs the Cantus segment to exist.
        make_fake_segment(id=settings.CANTUS_SEGMENT_ID, name="CANTUS Database")
        cls.user = make_fake_user()
        cls.chant = make_hidden_chant()

    def login(self):
        self.client.force_login(self.user)

    def assert_hidden_in(self, content: str):
        for value in (STD_MARK, MS_MARK, VOLPIANO):
            self.assertNotIn(value, content)

    def assert_shown_in(self, content: str):
        for value in (STD_MARK, MS_MARK, VOLPIANO):
            self.assertIn(value, content)

    def test_chant_detail_page(self):
        url = reverse("chant-detail", args=[self.chant.id])
        self.assert_hidden_in(self.client.get(url).content.decode())
        self.login()
        content = self.client.get(url).content.decode()
        self.assert_shown_in(content)
        self.assertIn("(not proofread)", content)

    def test_chant_detail_json(self):
        url = reverse("chant-detail", args=[self.chant.id])
        chant = self.client.get(url, HTTP_ACCEPT="application/json").json()["chant"]
        self.assertIsNone(chant["volpiano"])
        self.assertIsNone(chant["manuscript_full_text"])
        self.assertIsNone(chant["manuscript_full_text_std_spelling"])
        self.login()
        chant = self.client.get(url, HTTP_ACCEPT="application/json").json()["chant"]
        self.assertEqual(chant["volpiano"], VOLPIANO)

    def test_melody_preview_skips_hidden_text(self):
        Chant.objects.filter(id=self.chant.id).update(
            volpiano_proofread=True, manuscript_full_text_std_proofread=True
        )
        response = self.client.get(reverse("chant-detail", args=[self.chant.id]))
        preview = str(response.context["syllabized_text_with_melody"])
        self.assertNotIn(MS_MARK, preview)

    def test_no_proofread_label_on_proofread_fields(self):
        Chant.objects.filter(id=self.chant.id).update(**PROOFREAD)
        self.login()
        response = self.client.get(reverse("chant-detail", args=[self.chant.id]))
        self.assertNotIn("(not proofread)", response.content.decode())

    def test_chant_search_keyword(self):
        params = {"keyword": MS_MARK, "op": "contains"}
        response = self.client.get(reverse("chant-search"), params)
        self.assertEqual(len(response.context["chants"]), 0)
        self.login()
        response = self.client.get(reverse("chant-search"), params)
        self.assertEqual(len(response.context["chants"]), 1)

    def test_chant_search_results(self):
        params = {"cantus_id": CANTUS_ID}
        response = self.client.get(reverse("chant-search"), params)
        self.assertIsNone(response.context["chants"][0].volpiano)
        self.assert_hidden_in(response.content.decode())

    def test_chant_search_melody_filter(self):
        params = {"cantus_id": CANTUS_ID, "melodies": "true"}
        response = self.client.get(reverse("chant-search"), params)
        self.assertEqual(len(response.context["chants"]), 0)
        self.login()
        response = self.client.get(reverse("chant-search"), params)
        self.assertEqual(len(response.context["chants"]), 1)

    def test_source_search_without_melodies_includes_hidden_melodies(self):
        url = reverse("chant-search-ms", args=[self.chant.source.id])
        response = self.client.get(url, {"melodies": "false"})
        self.assertEqual(len(response.context["chants"]), 1)
        response = self.client.get(url, {"melodies": "true"})
        self.assertEqual(len(response.context["chants"]), 0)
        self.login()
        response = self.client.get(url, {"melodies": "false"})
        self.assertEqual(len(response.context["chants"]), 0)

    def test_browse_chants(self):
        url = reverse("browse-chants", args=[self.chant.source.id])
        self.assert_hidden_in(self.client.get(url).content.decode())
        response = self.client.get(url, {"search_text": STD_MARK})
        self.assertEqual(len(response.context["chants"]), 0)
        self.login()
        response = self.client.get(url, {"search_text": STD_MARK})
        self.assertEqual(len(response.context["chants"]), 1)

    def test_chants_by_cantus_id(self):
        url = reverse("chant-by-cantus-id", args=[CANTUS_ID])
        self.assertIsNone(self.client.get(url).context["chants"][0].volpiano)
        self.login()
        self.assertEqual(self.client.get(url).context["chants"][0].volpiano, VOLPIANO)

    def test_csv_export(self):
        url = reverse("csv-export", args=[self.chant.source.id])
        self.assert_hidden_in(self.client.get(url).content.decode())
        self.login()
        rows = list(csv.DictReader(io.StringIO(self.client.get(url).content.decode())))
        self.assertEqual(rows[0]["volpiano"], VOLPIANO)
        self.assertEqual(rows[0]["fulltext_ms"], MS_TEXT)

    def test_ajax_melody_list(self):
        url = reverse("ajax-melody", args=[CANTUS_ID])
        self.assertEqual(self.client.get(url).json()["concordance_count"], 0)
        self.login()
        self.assertEqual(self.client.get(url).json()["concordance_count"], 1)

    def test_ajax_melody_search(self):
        params = {"notes": NOTES, "anywhere": "false", "transpose": "false"}
        url = reverse("ajax-melody-search")
        self.assertEqual(self.client.get(url, params).json()["result_count"], 0)
        self.login()
        self.assertEqual(self.client.get(url, params).json()["result_count"], 1)

    def test_json_melody_export(self):
        url = reverse("json-melody-export", args=[CANTUS_ID])
        self.assertEqual(self.client.get(url).json(), [])
        Chant.objects.filter(id=self.chant.id).update(volpiano_proofread=True)
        (melody,) = self.client.get(url).json()
        self.assertEqual(melody["volpiano"], VOLPIANO)
        self.assertIsNone(melody["fulltext"])

    def test_json_cid_export(self):
        url = reverse("json-cid-export", args=[CANTUS_ID])
        chant = self.client.get(url).json()["chants"][0]["chant"]
        self.assertEqual(chant["full_text"], "")
        self.assertEqual(chant["melody"], "")

    def test_json_node_export(self):
        url = reverse("json-node-export", args=[self.chant.id])
        self.assert_hidden_in(self.client.get(url).content.decode())
        self.login()
        self.assert_shown_in(self.client.get(url).content.decode())

    def test_cached_concordances(self):
        concordances = update_cached_concordances.get_concordances()
        self.assert_hidden_in(json.dumps(concordances))
