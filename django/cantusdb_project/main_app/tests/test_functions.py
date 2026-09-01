from typing import Union, Optional
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TestCase
import requests
from requests.exceptions import SSLError, Timeout, HTTPError
from main_app.models.url_field import NormalizedURLField, NormalizedURLFormField
from main_app.models import (
    Chant,
    Source,
)
from main_app.tests import mock_cantusindex_data
from main_app.tests.make_fakes import (
    make_fake_chant,
    make_fake_sequence,
    make_fake_source,
)
from main_app.management.commands import update_cached_concordances
from main_app.signals import (
    generate_incipit,
    generate_chant_range,
    extract_volpiano_clef,
)
from cantusindex import (
    get_suggested_chants,
    get_json_from_ci_api,
    CANTUS_INDEX_DOMAIN,
    OLD_CANTUS_INDEX_DOMAIN,
    get_suggested_fulltext,
    get_merged_cantus_ids,
    get_ci_text_search,
)

# run with `python -Wa manage.py test main_app.tests.test_functions`
# the -Wa flag tells Python to display deprecation warnings


class MockResponse:
    def __init__(
        self,
        status_code: int,
        text: Optional[str],
        json: Union[dict, list, None],
        content: Optional[bytes],
        encoding: str = "utf-8",
        # >>> response = requests.get("https://cantusindex.uwaterloo.ca/json-nextchants/001010")
        # >>> response.encoding
        # 'utf-8'
    ):
        self.status_code = status_code
        self._json = json
        self.content = content
        self.encoding = encoding
        self.text = text

    def json(self):
        return self._json


def mock_requests_get(url: str, timeout: float) -> MockResponse:
    """Return a mock response. Used to patch calls to requests.get in tests below

    Args:
        url (str): a URL - a necessary argument for requests.get
        timeout (int): we pass timeout as an argument to requests.get in get_json_from_ci_api,
            so mock_requests_get is configured to accept this argument.

    Raises:
        ValueError: This function is configured to mock requests to specific URLs only, including
            - /json-nextchants/001010
        If a call to requests.get with a different URL is made while mock_requests_get
        is patching it, a NotImplementedError is raised.

    Returns:
        MockResponse: A mock response object
    """
    if timeout < 0.001:
        raise requests.exceptions.ConnectTimeout

    if not (CANTUS_INDEX_DOMAIN or OLD_CANTUS_INDEX_DOMAIN in url):
        raise NotImplementedError(
            f"mock_requests_get is only set up to mock calls to Cantus Index. "
            f"The protocol and domain of url {url} do not correspond to those of Cantus Index."
        )

    if f"{CANTUS_INDEX_DOMAIN}/json-nextchants/" in url:
        if url.endswith("/001010"):
            return MockResponse(
                status_code=200,
                content=mock_cantusindex_data.mock_json_nextchants_001010_content,
                text=mock_cantusindex_data.mock_json_nextchants_001010_text,
                json=mock_cantusindex_data.mock_json_nextchants_001010_json,
            )
        if url.endswith("/a07763"):
            # this Cantus ID has no suggested chants
            return MockResponse(
                status_code=200,
                content=mock_cantusindex_data.mock_json_nextchants_a07763_content,
                text=mock_cantusindex_data.mock_json_nextchants_a07763_text,
                json=None,
            )
        # imitating CI's behavior when a made-up Cantus ID is entered.
        return MockResponse(
            status_code=200,
            content=bytes('["Cantus ID is not valid"]', encoding="utf-8-sig"),
            text='["Cantus ID is not valid"]',
            json=["Cantus ID is not valid"],
        )
    if f"{CANTUS_INDEX_DOMAIN}/json-cid/" in url:
        if url.endswith("/008349"):
            return MockResponse(
                status_code=200,
                content=mock_cantusindex_data.mock_json_cid_008349_content,
                text=mock_cantusindex_data.mock_json_cid_008349_text,
                json=mock_cantusindex_data.mock_json_cid_008349_json,
            )
        if url.endswith("/006928"):
            return MockResponse(
                status_code=200,
                content=mock_cantusindex_data.mock_json_cid_006928_content,
                text=mock_cantusindex_data.mock_json_cid_006928_text,
                json=mock_cantusindex_data.mock_json_cid_006928_json,
            )
        if url.endswith("/008411c"):
            return MockResponse(
                status_code=200,
                content=mock_cantusindex_data.mock_json_cid_008411c_content,
                text=mock_cantusindex_data.mock_json_cid_008411c_text,
                json=mock_cantusindex_data.mock_json_cid_008411c_json,
            )
        if url.endswith("/008390"):
            return MockResponse(
                status_code=200,
                content=mock_cantusindex_data.mock_json_cid_008390_content,
                text=mock_cantusindex_data.mock_json_cid_008390_text,
                json=mock_cantusindex_data.mock_json_cid_008390_json,
            )
        if url.endswith("/007713"):
            return MockResponse(
                status_code=200,
                content=mock_cantusindex_data.mock_json_cid_007713_content,
                text=mock_cantusindex_data.mock_json_cid_007713_text,
                json=mock_cantusindex_data.mock_json_cid_007713_json,
            )
        if url.endswith("/909030"):
            return MockResponse(
                status_code=200,
                content=mock_cantusindex_data.mock_json_cid_909030_content,
                text=mock_cantusindex_data.mock_json_cid_909030_text,
                json=mock_cantusindex_data.mock_json_cid_909030_json,
            )
        # imitating CI's behavior when a made-up Cantus ID is entered.
        return MockResponse(
            status_code=500,
            content=None,
            text=None,
            json=None,
        )
    if f"{OLD_CANTUS_INDEX_DOMAIN}/json-text/" in url:
        if url.endswith("qui+est"):
            return MockResponse(
                status_code=200,
                content=mock_cantusindex_data.mock_get_ci_text_search_quiest_content,
                text=mock_cantusindex_data.mock_get_ci_text_search_quiest_text,
                json=None,
            )
        if url.endswith("123xyz"):
            return MockResponse(
                status_code=200,
                content=mock_cantusindex_data.mock_get_ci_text_search_123xyz_content,
                text=mock_cantusindex_data.mock_get_ci_text_search_123xyz_text,
                json=None,
            )
        if url.endswith("no_match"):
            return MockResponse(
                status_code=200,
                content=mock_cantusindex_data.mock_get_ci_text_search_no_match_content,
                text=mock_cantusindex_data.mock_get_ci_text_search_no_match_text,
                json=None,
            )
        return MockResponse(
            status_code=500,
            content=None,
            text=None,
            json=None,
        )
    if f"{OLD_CANTUS_INDEX_DOMAIN}/json-merged-chants" in url:
        return MockResponse(
            status_code=200,
            content=mock_cantusindex_data.mock_get_merged_cantus_ids_content,
            text=mock_cantusindex_data.mock_get_merged_cantus_ids_text,
            json=None,
        )

    raise NotImplementedError(
        f"mock_requests_get is only set up to imitate only the /json-nextchants/, "
        f"/json-cid/, and /json-text/ endpoints on Cantus Index. The path of the url "
        f"{url} does not match either of these endpoints."
    )


class UpdateCachedConcordancesCommandTest(TestCase):
    def test_concordances_structure(self):
        chant: Chant = make_fake_chant(cantus_id="123456")
        concordances: list = update_cached_concordances.get_concordances()

        with self.subTest(test="Ensure get_concordances returns list"):
            self.assertIsInstance(concordances, list)

        single_concordance = concordances[0]
        with self.subTest(test="Ensure each concordance is a dict"):
            self.assertIsInstance(single_concordance, dict)

        expected_keys = (
            "siglum",
            "srclink",
            "chantlink",
            "folio",
            "sequence",
            "incipit",
            "feast",
            "genre",
            "office",
            "position",
            "cantus_id",
            "image",
            "mode",
            "full_text",
            "melody",
            "db",
        )
        concordance_keys = single_concordance.keys()
        for key in expected_keys:
            with self.subTest(key=key):
                self.assertIn(key, concordance_keys)
        with self.subTest(test="Ensure no unexpected keys present"):
            self.assertEqual(len(concordance_keys), len(expected_keys))

    def test_published_vs_unpublished(self):
        published_source: Source = make_fake_source(published=True)
        published_chant: Chant = make_fake_chant(
            source=published_source,
            manuscript_full_text_std_spelling="chant in a published source",
        )
        unpublished_source: Source = make_fake_source(published=False)
        unpublished_chant: Chant = make_fake_chant(
            source=unpublished_source,
            manuscript_full_text_std_spelling="chant in an unpublished source",
        )

        concordances: list = update_cached_concordances.get_concordances()
        self.assertEqual(len(concordances), 1)

        single_concordance: dict = concordances[0]
        expected_fulltext: str = published_chant.manuscript_full_text_std_spelling
        observed_fulltext: str = single_concordance["full_text"]
        self.assertEqual(expected_fulltext, observed_fulltext)

    def test_concordances_values(self):
        chant: Chant = make_fake_chant()

        concordances: list = update_cached_concordances.get_concordances()
        single_concordance: dict = concordances[0]

        expected_items: tuple = (
            ("siglum", chant.source.siglum),
            ("srclink", f"https://cantusdatabase.org/source/{chant.source.id}/"),
            ("chantlink", f"https://cantusdatabase.org/chant/{chant.id}/"),
            ("folio", chant.folio),
            ("sequence", chant.c_sequence),
            ("incipit", chant.incipit),
            ("feast", chant.feast.name),
            ("genre", chant.genre.name),
            ("office", chant.service.name),
            ("position", chant.position),
            ("cantus_id", chant.cantus_id),
            ("image", chant.image_link),
            ("mode", chant.mode),
            ("full_text", chant.manuscript_full_text_std_spelling),
            ("melody", chant.volpiano),
            ("db", "CD"),
        )

        for key, value in expected_items:
            observed_value: Union[str, int, None] = single_concordance[key]
            with self.subTest(key=key):
                self.assertEqual(observed_value, value)


class IncipitSignalTest(TestCase):
    # testing an edge case in generate_incipit, within main_app/signals.py.
    # Some other tests involving this function can be found
    # in ChantModelTest and SequenceModelTest.
    def test_generate_incipit(self):
        complete_fulltext: str = "one two three four five six seven"
        expected_incipit_1: str = "one two three four five"
        observed_incipit_1: str = generate_incipit(complete_fulltext)
        with self.subTest(test="full-length fulltext"):
            self.assertEqual(observed_incipit_1, expected_incipit_1)
        short_fulltext: str = "one*"
        expected_incipit_2 = "one*"
        observed_incipit_2 = generate_incipit(short_fulltext)
        with self.subTest(test="fulltext that's already a short incipit"):
            self.assertEqual(observed_incipit_2, expected_incipit_2)


class ChantRangeSignalTest(TestCase):
    # testing generate_chant_range, within main_app/signals.py.
    # Input is a raw volpiano string; normalization and clef extraction both
    # happen inside generate_chant_range.
    def test_lowest_and_highest_notes(self):
        self.assertEqual(generate_chant_range("cdefg"), "1-c-g-4")

    def test_order_of_notes_does_not_matter(self):
        # the range depends on pitch extremes, not on where they appear
        self.assertEqual(generate_chant_range("gfedc"), "1-c-g-4")
        self.assertEqual(generate_chant_range("edcgf"), "1-c-g-4")

    def test_single_note(self):
        self.assertEqual(generate_chant_range("f"), "1-f-f-4")

    def test_no_notes_returns_empty_string(self):
        self.assertEqual(generate_chant_range(""), "")

    def test_low_g_is_below_a(self):
        # "9" (low G) is the lowest note character, ranking below "a"
        self.assertEqual(generate_chant_range("9abc"), "1-9-c-4")

    def test_b_is_j_not_i(self):
        # "i" is skipped in volpiano; a span from A ("h") to C ("k")
        # crosses B ("j") and must treat "k" as the highest note
        self.assertEqual(generate_chant_range("hjk"), "1-h-k-4")

    def test_full_gamut(self):
        # "9" is the lowest pitch character; the gamut runs "9" to "s"
        self.assertEqual(generate_chant_range("9abcdefghjklmnopqrs"), "1-9-s-4")

    def test_eight_is_not_treated_as_a_note(self):
        # "8" is not a recognized volpiano pitch (see VOLPIANO_PITCH_ORDER).
        # generate_volpiano_notes strips only "1"-"7", so a stray "8" survives
        # normalization and would otherwise sort below every real note and
        # silently widen the ambitus.
        self.assertEqual(generate_chant_range("1---c--d--8--e--f--g---4"), "1-c-g-4")

    def test_volpiano_of_only_an_eight_yields_no_range(self):
        # Guards the worst case: a bogus range derived from junk would be
        # written once and then never overwritten, becoming permanent.
        self.assertEqual(generate_chant_range("1---8---4"), "")

    def test_end_to_end_from_raw_volpiano(self):
        # liquescents (upper-case) lower-case to the same pitch, consecutive
        # duplicates collapse, and clefs/barlines are stripped before the
        # range is computed
        self.assertEqual(generate_chant_range("1---cD--Ef--g---4"), "1-c-g-4")

    def test_end_to_end_low_g_liquescent(self):
        # ")" is the low-G liquescent, normalized to "9"
        self.assertEqual(generate_chant_range("1---)abc---4"), "1-9-c-4")

    def test_end_to_end_melodyless_volpiano(self):
        # a volpiano with only clef and barlines yields no notes, hence no range
        self.assertEqual(generate_chant_range("1---3---4"), "")

    def test_non_pitch_characters_are_ignored(self):
        # real volpiano fields contain dirty data (stray punctuation, whitespace,
        # typos) that survives normalization; the range must span real pitches
        # only, never crash. "w" here is a typo mid-melody, not a high note.
        self.assertEqual(generate_chant_range("c|d]e\nf*g"), "1-c-g-4")
        self.assertEqual(generate_chant_range("fghwg"), "1-f-h-4")

    def test_only_junk_returns_empty_string(self):
        self.assertEqual(generate_chant_range("|[]*\n\r"), "")


class VolpianoClefTest(TestCase):
    # testing extract_volpiano_clef and the clef half of generate_chant_range.
    # The clef is copied from the melody so a range renders on the same staff
    # as the chant it describes, rather than being hardcoded to the G clef.
    def test_g_clef_is_read_from_the_melody(self):
        self.assertEqual(extract_volpiano_clef("1---c--d---4"), "1")

    def test_f_clef_is_read_from_the_melody(self):
        self.assertEqual(extract_volpiano_clef("2---c--d---4"), "2")

    def test_leading_separators_are_skipped(self):
        self.assertEqual(extract_volpiano_clef("---2---c--d---4"), "2")

    def test_missing_clef_falls_back_to_g_clef(self):
        self.assertEqual(extract_volpiano_clef("cdefg"), "1")

    def test_empty_volpiano_falls_back_to_g_clef(self):
        self.assertEqual(extract_volpiano_clef(""), "1")

    def test_non_clef_leading_character_falls_back_to_g_clef(self):
        # "3" is a barline, not a clef
        self.assertEqual(extract_volpiano_clef("3---c--d---4"), "1")

    def test_repeated_clef_is_not_a_clef_change(self):
        # The same clef restated mid-melody still describes one staff.
        self.assertEqual(extract_volpiano_clef("1---c--d---1---e--f---4"), "1")

    def test_clef_change_returns_none(self):
        # Volpiano allows the clef to change mid-melody. The same letter then
        # denotes a different pitch on either side of the change, so no single
        # clef describes the whole ambitus.
        self.assertIsNone(extract_volpiano_clef("1---c--d---2---e--f---4"))

    def test_clef_change_yields_no_range(self):
        # Better to derive nothing than a confidently wrong ambitus. A human
        # can enter the range for these by hand.
        self.assertEqual(generate_chant_range("1---c--d---2---e--f---4"), "")

    def test_range_carries_the_f_clef_through(self):
        self.assertEqual(generate_chant_range("2---c--d--e---4"), "2-c-e-4")

    def test_range_defaults_to_g_clef_when_melody_has_none(self):
        self.assertEqual(generate_chant_range("---c--d--e---"), "1-c-e-4")


class ChantRangeAutofillSignalTest(TestCase):
    # testing the derivation wiring in update_volpiano_fields (signals.py):
    # whenever a chant has volpiano, saving it recomputes chant_range from that
    # volpiano and overwrites whatever was stored. A stored range that disagrees
    # with the melody is an error, not ground truth. See #2081 / #1176.
    def test_blank_range_is_filled_from_volpiano(self):
        chant = make_fake_chant(volpiano="1---c--d--e--f--g---4", chant_range="")
        self.assertEqual(chant.chant_range, "1-c-g-4")

    def test_existing_range_is_overwritten(self):
        # the headline behaviour: the melody wins over a hand-entered value even
        # when the melody itself did not change on this save
        chant = make_fake_chant(volpiano="1---c--d--e--f--g---4", chant_range="1-a-b-4")
        self.assertEqual(chant.chant_range, "1-c-g-4")

    def test_unproofread_volpiano_still_overwrites(self):
        # Derivation is deliberately not conditioned on volpiano_proofread: an
        # unverified melody is still a better description of the ambitus than a
        # range typed by hand.
        chant = make_fake_chant(
            volpiano="1---c--d--e--f--g---4",
            chant_range="1-a-b-4",
            volpiano_proofread=False,
        )
        self.assertEqual(chant.chant_range, "1-c-g-4")

    def test_range_is_recomputed_when_volpiano_is_edited(self):
        # chant_range is derived data: editing the melody makes the stored range
        # stale, so it follows the new volpiano. ("k"-"m" sit above "c"-"d" in
        # the volpiano gamut; note that "a" is near the BOTTOM of that gamut.)
        chant = make_fake_chant(volpiano="1---c--d---4", chant_range="")
        self.assertEqual(chant.chant_range, "1-c-d-4")
        chant.volpiano = "1---k--l--m---4"
        chant.save()
        chant.refresh_from_db()
        self.assertEqual(chant.chant_range, "1-k-m-4")

    def test_hand_entered_range_is_recomputed_when_volpiano_is_edited(self):
        chant = make_fake_chant(volpiano="1---c--d---4", chant_range="1-a-b-4")
        self.assertEqual(chant.chant_range, "1-c-d-4")
        chant.volpiano = "1---k--l--m---4"
        chant.save()
        chant.refresh_from_db()
        self.assertEqual(chant.chant_range, "1-k-m-4")

    def test_range_is_corrected_by_a_save_that_does_not_touch_the_melody(self):
        # A mismatch introduced behind the ORM's back (or predating this feature)
        # is repaired by the next save of any kind — the range is derived data,
        # so it does not need the melody to have changed to be recomputed.
        chant = make_fake_chant(volpiano="1---c--d---4", chant_range="")
        Chant.objects.filter(pk=chant.pk).update(chant_range="1-a-b-4")
        chant.refresh_from_db()
        chant.manuscript_full_text_std_spelling = "edited elsewhere"
        chant.save()
        chant.refresh_from_db()
        self.assertEqual(chant.chant_range, "1-c-d-4")

    def test_clef_change_alone_recomputes_the_range(self):
        # Editing only the clef leaves the notes identical, so the old
        # change-detection approach missed it. Deriving unconditionally means the
        # range's clef now follows the melody's.
        chant = make_fake_chant(volpiano="1---c--d---4", chant_range="")
        self.assertEqual(chant.chant_range, "1-c-d-4")
        chant.volpiano = "2---c--d---4"
        chant.save()
        chant.refresh_from_db()
        self.assertEqual(chant.chant_range, "2-c-d-4")

    def test_no_volpiano_leaves_range_untouched(self):
        chant = make_fake_chant(volpiano=None, chant_range="1-a-b-4")
        self.assertEqual(chant.chant_range, "1-a-b-4")

    def test_preexisting_values_are_overwritten_at_creation(self):
        # A range supplied at creation gives way to the derived "1-c-g-4",
        # whatever form it took: a plainly wrong ambitus, an uppercase
        # (liquescent) extreme, a malformed value, or whitespace-only content.
        volpiano = "1---c--d--e--f--g---4"
        preexisting_ranges = {
            "plainly wrong ambitus": "1-a-b-4",
            "uppercase liquescent extreme": "1-c-G-4",
            "malformed (missing dash)": "1c-g-4",
            "whitespace only": " ",
        }
        for label, stored in preexisting_ranges.items():
            with self.subTest(case=label):
                chant = make_fake_chant(volpiano=volpiano, chant_range=stored)
                self.assertEqual(chant.chant_range, "1-c-g-4")

    def test_none_and_empty_are_both_filled_when_volpiano_present(self):
        # Both blank representations get filled from the melody.
        for blank in (None, ""):
            with self.subTest(blank=repr(blank)):
                chant = make_fake_chant(volpiano="1---c--d---4", chant_range=blank)
                self.assertEqual(chant.chant_range, "1-c-d-4")

    def test_none_and_empty_are_both_preserved_without_volpiano(self):
        for blank in (None, ""):
            with self.subTest(blank=repr(blank)):
                chant = make_fake_chant(volpiano=None, chant_range=blank)
                self.assertEqual(chant.chant_range, blank)

    def test_junk_only_volpiano_leaves_blank_range_blank(self):
        # A volpiano whose only surviving characters are non-pitches (stray
        # punctuation) yields no range, and must not write "" churn or crash.
        chant = make_fake_chant(volpiano="1---|[]*---4", chant_range="")
        self.assertEqual(chant.chant_range, "")

    def test_underivable_range_leaves_a_stored_value_alone(self):
        # The one case where a stored range survives a chant that has volpiano:
        # the melody yields nothing to derive from, so it says nothing about the
        # ambitus and blanking the stored value would only destroy information.
        # A mid-melody clef change and a pitchless volpiano are the two ways in.
        underivable = {
            "clef change": "1---c--2---c---4",
            "no recognized pitches": "1---|[]*---4",
        }
        for label, volpiano in underivable.items():
            with self.subTest(case=label):
                chant = make_fake_chant(volpiano=volpiano, chant_range="1-a-b-4")
                self.assertEqual(chant.chant_range, "1-a-b-4")

    def test_stale_blank_instance_does_not_blank_the_stored_range(self):
        # The signal reads instance.volpiano and never instance.chant_range, so a
        # save whose in-memory range is blank still writes the derived value
        # rather than propagating the blank.
        chant = make_fake_chant(volpiano="1---c--d---4", chant_range="1-a-b-4")
        chant.chant_range = ""  # blank in memory only
        chant.save(update_fields=["volpiano"])
        chant.refresh_from_db()
        self.assertEqual(chant.chant_range, "1-c-d-4")

    def test_autofill_is_idempotent(self):
        chant = make_fake_chant(volpiano="1---c--d--e---4", chant_range="")
        self.assertEqual(chant.chant_range, "1-c-e-4")
        for _ in range(3):
            chant.save()
            chant.refresh_from_db()
            self.assertEqual(chant.chant_range, "1-c-e-4")

    def test_autofill_touches_only_chant_range(self):
        # Filling a blank range must not disturb any other field on the chant.
        fulltext = "originalus fulltextus"
        chant = make_fake_chant(
            volpiano="1---c--d---4",
            chant_range="",
            manuscript_full_text_std_spelling=fulltext,
        )
        self.assertEqual(chant.chant_range, "1-c-d-4")  # the fill happened
        self.assertEqual(chant.manuscript_full_text_std_spelling, fulltext)


class SequenceRangeAutofillSignalTest(TestCase):
    # volpiano and chant_range are both declared on BaseChant, so sequences carry
    # them too. on_sequence_save now runs the same derivation as on_chant_save
    # (#2081 / #1176); before that it skipped update_volpiano_fields entirely.
    def test_range_is_derived_from_volpiano(self):
        sequence = make_fake_sequence()
        sequence.volpiano = "1---c--d--e---4"
        sequence.save()
        sequence.refresh_from_db()
        self.assertEqual(sequence.chant_range, "1-c-e-4")

    def test_existing_range_is_overwritten(self):
        sequence = make_fake_sequence()
        sequence.volpiano = "1---c--d--e---4"
        sequence.chant_range = "1-a-b-4"
        sequence.save()
        sequence.refresh_from_db()
        self.assertEqual(sequence.chant_range, "1-c-e-4")

    def test_no_volpiano_leaves_range_untouched(self):
        sequence = make_fake_sequence()
        sequence.chant_range = "1-a-b-4"
        sequence.save()
        sequence.refresh_from_db()
        self.assertEqual(sequence.chant_range, "1-a-b-4")

    def test_volpiano_notes_and_intervals_are_populated(self):
        # These two melody-search fields were never written for sequences either.
        sequence = make_fake_sequence()
        sequence.volpiano = "1---c--d--e---4"
        sequence.save()
        sequence.refresh_from_db()
        self.assertEqual(sequence.volpiano_notes, "cde")
        self.assertEqual(sequence.volpiano_intervals, "11")


class CantusIndexFunctionsTest(TestCase):
    def test_get_suggested_chants(self) -> None:
        expected_number_of_suggestions: int = 5
        with patch("requests.get", mock_requests_get):
            suggested_chants = get_suggested_chants(cantus_id="001010")

        initial_suggested_chant = suggested_chants[0]

        with self.subTest(test="Ensure returned object is a list of dicts"):
            self.assertIsInstance(suggested_chants, list)
            self.assertIsInstance(initial_suggested_chant, dict)

        with self.subTest(
            test=f"Ensure no more than {expected_number_of_suggestions} suggestions returned"
        ):
            self.assertLessEqual(len(suggested_chants), expected_number_of_suggestions)

        with self.subTest(
            test="Ensure suggested chants are ordered by number of occurrences"
        ):
            for i in range(expected_number_of_suggestions - 1):
                suggested_chant = suggested_chants[i]
                following_suggested_chant = suggested_chants[i + 1]
                self.assertGreaterEqual(
                    suggested_chant["occurrences"],
                    following_suggested_chant["occurrences"],
                )

        with patch("requests.get", mock_requests_get):
            suggested_chants_nonexistent_cantus_id = get_suggested_chants(
                "NotACantusID"
            )
        with self.subTest(test="Ensure None returned in case of nonexistent Cantus ID"):
            self.assertIsNone(suggested_chants_nonexistent_cantus_id)

        with patch("requests.get", mock_requests_get):
            suggested_chants_rare_cantus_id = get_suggested_chants(cantus_id="a07763")
        with self.subTest(
            test="Ensure None is returned in case of Cantus ID without suggestions"
        ):
            self.assertIsNone(suggested_chants_rare_cantus_id)

    def test_get_json_from_ci_api(self) -> None:
        with patch("requests.get", mock_requests_get):
            json_nextchants_response = get_json_from_ci_api(
                path="/json-nextchants/001010"
            )
        with self.subTest(
            test="Ensure properly handles /nextchants/<cantus_id> endpoint"
        ):
            self.assertIsInstance(json_nextchants_response, list)
            first_nextchant = json_nextchants_response[0]
            self.assertIsInstance(first_nextchant, dict)

        with patch("requests.get", mock_requests_get):
            json_cid_response = get_json_from_ci_api(path="/json-cid/008349")
        observed_json_cid_keys = json_cid_response.keys()
        expected_json_cid_keys = ("info", "chants")
        with self.subTest(
            test="Ensure properly handles /json-cid/<cantus_id> endpoint"
        ):
            self.assertIsInstance(json_cid_response, dict)
            for key in expected_json_cid_keys:
                self.assertIn(key, observed_json_cid_keys)

        with patch("requests.get", mock_requests_get):
            response_short_timeout = get_json_from_ci_api(
                path="/some/path", timeout=0.0001
            )
        with self.subTest(test="Ensure returns None when requests.get times out"):
            self.assertIsNone(response_short_timeout)

        with patch("requests.get", mock_requests_get):
            response_nonexistent_cantus_id = get_json_from_ci_api(
                path="/json-cid/notACantusID"
            )
        with self.subTest(
            test="Ensure returns None when response status code is not 200"
        ):
            self.assertIsNone(response_nonexistent_cantus_id)

        with self.subTest(
            test="Ensure raises ValueError when path lacks leading slash"
        ):
            self.assertRaises(
                ValueError, get_json_from_ci_api, "path/lacking/a/leading/slash"
            )

        def raise_connection_error(*args, **kwargs):
            raise requests.exceptions.ConnectionError

        with patch("requests.get", raise_connection_error):
            response_connection_error = get_json_from_ci_api(path="/json-cids")
        with self.subTest(
            test="Ensure returns None when requests.get raises a connection error"
        ):
            self.assertIsNone(response_connection_error)

        malformed_json_response = MockResponse(
            status_code=200,
            text="this is not valid json",
            json=None,
            content=b"this is not valid json",
        )

        def json_raises_value_error():
            raise ValueError("Expecting value")

        malformed_json_response.json = json_raises_value_error
        with patch("requests.get", lambda *args, **kwargs: malformed_json_response):
            response_malformed_json = get_json_from_ci_api(path="/json-cids")
        with self.subTest(
            test="Ensure returns None when Cantus Index returns malformed JSON"
        ):
            self.assertIsNone(response_malformed_json)

    def test_get_suggested_fulltext(self) -> None:
        with self.subTest("Test CantusID with full text"):
            with patch("requests.get", mock_requests_get):
                fulltext = get_suggested_fulltext("008349")
            self.assertEqual(
                fulltext,
                "Nocte surgentes vigilemus omnes semper in psalmis meditemur atque viribus totis domino canamus dulciter hymnos | Ut pio regi pariter canentes cum suis sanctis mereamur aulam ingredi caeli simul et beatam ducere vitam | Praestet hoc nobis deitas beata patris ac nati pariterque sancti spiritus cujus resonat per omnem gloria mundum | Amen",
            )

        with self.subTest("Test invalid CantusID"):
            with patch("requests.get", mock_requests_get):
                fulltext = get_suggested_fulltext("999999")
            self.assertIsNone(fulltext)

    def test_get_merged_cantus_ids(self) -> None:
        with self.subTest("Test valid response"):
            with patch("requests.get", mock_requests_get):
                results = get_merged_cantus_ids()
            self.assertIsInstance(results, list)
            self.assertEqual(len(results), 20)
            self.assertEqual(results[0]["old"], "g00831")
            self.assertEqual(results[0]["new"], "920023")
            self.assertEqual(results[0]["date"], "0000-00-00")

        with self.subTest("Test server error"):
            mock_response = MockResponse(
                status_code=500,
                text=None,
                json=None,
                content=None,
            )
            with patch("requests.get", return_value=mock_response):
                results = get_merged_cantus_ids()
            self.assertIsNone(results)

        with self.subTest("Test timeout"):
            with patch("requests.get", side_effect=Timeout):
                results = get_merged_cantus_ids()
            self.assertRaises(Timeout)
            self.assertIsNone(results)

        with self.subTest("Test SSLError"):
            with patch("requests.get", side_effect=SSLError):
                results = get_merged_cantus_ids()
            self.assertRaises(SSLError)
            self.assertIsNone(results)

        with self.subTest("Test HTTPError"):
            with patch("requests.get", side_effect=HTTPError):
                results = get_merged_cantus_ids()
            self.assertRaises(HTTPError)
            self.assertIsNone(results)

    def test_get_ci_text_search(self) -> None:
        with self.subTest("Test valid search term"):
            with patch("requests.get", mock_requests_get):
                results = get_ci_text_search("qui+est")
            self.assertIsInstance(results, list)
            self.assertEqual(len(results), 50)
            self.assertEqual(results[0]["cid"], "001774")
            self.assertEqual(
                results[0]["fulltext"],
                "Caro et sanguis non revelavit tibi sed pater meus qui est in caelis",
            )
            self.assertEqual(results[1]["cid"], "002191")
            self.assertEqual(
                results[1]["fulltext"],
                "Dicebat Jesus turbis Judaeorum et principibus sacerdotum qui est ex deo verba dei audit responderunt Judaei et dixerunt ei nonne bene dicimus nos quia Samaritanus es tu et daemonium habes respondit Jesus ego daemonium non habeo sed honorifico patrem meum et vos inhonorastis me",
            )

        with self.subTest("Test invalid search term"):
            with patch("requests.get", mock_requests_get):
                results = get_ci_text_search("123xyz")
            self.assertIsNone(results)

        with self.subTest("Test server error"):
            mock_response = MockResponse(
                status_code=500,
                text=None,
                json=None,
                content=None,
            )
            with patch("requests.get", return_value=mock_response):
                results = get_ci_text_search("server_error")
            self.assertIsNone(results)

        with self.subTest("Test SSLError"):
            with patch("requests.get", side_effect=SSLError):
                results = get_ci_text_search("SSLError")
            self.assertRaises(SSLError)
            self.assertIsNone(results)

        with self.subTest("Test Timeout"):
            with patch("requests.get", side_effect=Timeout):
                results = get_ci_text_search("Timeout")
            self.assertRaises(Timeout)
            self.assertIsNone(results)

        with self.subTest("Test HTTPError"):
            with patch("requests.get", side_effect=HTTPError):
                results = get_ci_text_search("HTTPError")
            self.assertRaises(HTTPError)
            self.assertIsNone(results)


class NormalizedURLFormFieldTest(TestCase):
    def setUp(self):
        self.field = NormalizedURLFormField(required=False)

    def test_spaces_encoded(self):
        result = self.field.clean("https://example.com/Folio 92r.jpg")
        self.assertEqual(
            result,
            "https://example.com/Folio%2092r.jpg",
        )

    def test_already_encoded_unchanged(self):
        url = "https://example.com/Folio%2092r.jpg"
        self.assertEqual(self.field.clean(url), url)

    def test_leading_trailing_whitespace_stripped(self):
        result = self.field.clean("  https://example.com/image.jpg  ")
        self.assertEqual(result, "https://example.com/image.jpg")

    def test_spaces_in_query_string_encoded(self):
        result = self.field.clean("https://example.com/search?q=some query")
        self.assertEqual(result, "https://example.com/search?q=some%20query")

    def test_invalid_url_rejected(self):
        with self.assertRaises(ValidationError):
            self.field.clean("not a url at all")

    def test_empty_string_returns_empty(self):
        self.assertEqual(self.field.clean(""), "")


class NormalizedURLModelFieldTest(TestCase):
    """Covers code paths that skip forms (admin, management commands, ORM)."""

    def setUp(self):
        self.field = NormalizedURLField(blank=True, null=True)

    def test_to_python_encodes_spaces(self):
        self.assertEqual(
            self.field.to_python("https://example.com/Folio 92r.jpg"),
            "https://example.com/Folio%2092r.jpg",
        )

    def test_get_prep_value_encodes_spaces(self):
        # Exercised on direct .save() even without full_clean().
        self.assertEqual(
            self.field.get_prep_value("https://example.com/Folio 92r.jpg"),
            "https://example.com/Folio%2092r.jpg",
        )

    def test_deconstruct_reports_as_plain_urlfield(self):
        # Keeps makemigrations from generating a no-op migration.
        _, path, _, _ = self.field.deconstruct()
        self.assertEqual(path, "django.db.models.URLField")

    def test_formfield_returns_normalizing_form_field(self):
        self.assertIsInstance(self.field.formfield(), NormalizedURLFormField)


class ImageLinkSpaceEncodingIntegrationTest(TestCase):
    """End-to-end coverage: saving a model whose image_link
    contains spaces must succeed and persist the URL with spaces encoded."""

    def test_chant_with_spaced_image_link_saves(self) -> None:
        # Mirrors the management-command path from #1868: a direct .save(),
        # which BaseModel.save() routes through full_clean()/URLValidator.
        chant = make_fake_chant()
        chant.image_link = "https://example.com/Folio 92r.jpg"
        chant.save()
        chant.refresh_from_db()
        self.assertEqual(chant.image_link, "https://example.com/Folio%2092r.jpg")

    def test_source_with_spaced_image_link_saves(self) -> None:
        source = make_fake_source()
        source.image_link = "https://example.com/image gallery.jpg"
        source.save()
        source.refresh_from_db()
        self.assertEqual(source.image_link, "https://example.com/image%20gallery.jpg")

    def test_save_does_not_raise_on_spaces(self) -> None:
        # Without the fix this raises ValidationError ("Enter a valid URL"),
        # which is exactly the failure reported in #1868.
        chant = make_fake_chant()
        chant.image_link = "https://example.com/a b c.jpg"
        try:
            chant.save()
        except ValidationError:
            self.fail("Saving a chant with spaces in image_link should not raise.")
