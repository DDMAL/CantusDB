"""Tests for the pure cluster rules in main_app.cluster_structure.

These need no database: the module is deliberately model-free so the models, forms, admin
and views can all share one implementation of the rules.

run with `python -Wa manage.py test main_app.tests.test_cluster_structure`
"""

import json

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from main_app.cluster_structure import (
    MAX_SEGMENTS,
    compute_omitted_ranges,
    flatten_segments,
    normalize_segments,
    parse_cluster_payload,
)

BASE_TEXT = "Sanctus sanctus sanctus Dominus Deus Sabaoth"
BASE_TOKENS = BASE_TEXT.split()  # 6 tokens


class FakeTrope:
    """Stands in for a TropeElement — the module only ever reads `.text`."""

    def __init__(self, text: str) -> None:
        self.text = text


def core(start: int, end: int) -> dict:
    return {"start": start, "end": end}


class NormalizeSegmentsTest(SimpleTestCase):
    def test_fills_every_key_of_a_core_segment(self):
        """A partial input dict comes back as a fully-populated spec."""
        observed = normalize_segments(6, [core(0, 3)])
        self.assertEqual(
            observed, [{"start": 0, "end": 3, "element": None, "text": ""}]
        )

    def test_strips_inline_trope_text(self):
        observed = normalize_segments(6, [{"text": "  Perpetuo numine  "}])
        self.assertEqual(observed[0]["text"], "Perpetuo numine")

    def test_rejects_an_empty_list(self):
        """A cluster with no segments would flatten to an empty full text."""
        with self.assertRaises(ValidationError):
            normalize_segments(6, [])

    def test_rejects_more_than_max_segments(self):
        too_many = [{"text": "trope"} for _ in range(MAX_SEGMENTS + 1)]
        with self.assertRaises(ValidationError):
            normalize_segments(6, too_many)

    def test_accepts_exactly_max_segments(self):
        """The cap is inclusive — MAX_SEGMENTS itself is allowed."""
        allowed = [{"text": "trope"} for _ in range(MAX_SEGMENTS)]
        self.assertEqual(len(normalize_segments(6, allowed)), MAX_SEGMENTS)

    def test_rejects_a_non_object_segment(self):
        with self.assertRaises(ValidationError):
            normalize_segments(6, [1])

    def test_rejects_a_segment_with_no_shape(self):
        with self.assertRaises(ValidationError):
            normalize_segments(6, [{}])

    def test_rejects_a_segment_with_two_shapes(self):
        """A range and a trope in one segment is ambiguous, not a merge."""
        with self.assertRaises(ValidationError):
            normalize_segments(6, [{"start": 0, "end": 2, "text": "trope"}])
        with self.assertRaises(ValidationError):
            normalize_segments(
                6, [{"element": FakeTrope("trope"), "text": "also a trope"}]
            )

    def test_rejects_a_half_specified_range(self):
        with self.assertRaises(ValidationError):
            normalize_segments(6, [{"start": 0}])
        with self.assertRaises(ValidationError):
            normalize_segments(6, [{"end": 3}])

    def test_rejects_booleans_as_range_bounds(self):
        """JSON `true` decodes to True, which is an int in Python — don't read it as 1."""
        with self.assertRaises(ValidationError):
            normalize_segments(6, [{"start": True, "end": 3}])

    def test_rejects_an_out_of_bounds_range(self):
        for bad in [core(0, 7), core(-1, 3), core(3, 3), core(4, 2)]:
            with self.subTest(segment=bad):
                with self.assertRaises(ValidationError):
                    normalize_segments(6, [bad])

    def test_accepts_a_range_covering_the_whole_base_text(self):
        self.assertEqual(len(normalize_segments(6, [core(0, 6)])), 1)

    def test_merges_adjacent_contiguous_cores(self):
        """[2, 5) then [5, 8) is the same text as [2, 8) — collapse to one encoding."""
        observed = normalize_segments(10, [core(2, 5), core(5, 8)])
        self.assertEqual(len(observed), 1)
        self.assertEqual((observed[0]["start"], observed[0]["end"]), (2, 8))

    def test_merges_a_run_of_contiguous_cores(self):
        observed = normalize_segments(10, [core(0, 2), core(2, 4), core(4, 6)])
        self.assertEqual([(s["start"], s["end"]) for s in observed], [(0, 6)])

    def test_does_not_merge_cores_separated_by_a_trope(self):
        """Adjacency is positional: a trope between two ranges keeps them apart."""
        observed = normalize_segments(
            10, [core(2, 5), {"text": "trope"}, core(5, 8)]
        )
        self.assertEqual(len(observed), 3)

    def test_does_not_merge_non_contiguous_cores(self):
        observed = normalize_segments(10, [core(0, 2), core(4, 6)])
        self.assertEqual([(s["start"], s["end"]) for s in observed], [(0, 2), (4, 6)])

    def test_allows_a_repeated_range(self):
        """A repetendum: the same base phrase appears twice, which is not an error."""
        observed = normalize_segments(10, [core(0, 3), {"text": "v"}, core(0, 3)])
        self.assertEqual(
            [(s["start"], s["end"]) for s in observed if s["start"] is not None],
            [(0, 3), (0, 3)],
        )

    def test_allows_out_of_order_ranges(self):
        """Reordering: base coordinates need not ascend across the sequence."""
        observed = normalize_segments(10, [core(5, 8), core(0, 3)])
        self.assertEqual([(s["start"], s["end"]) for s in observed], [(5, 8), (0, 3)])


class FlattenSegmentsTest(SimpleTestCase):
    def test_whole_base_text_round_trips(self):
        """The invariant the tokenisation has to satisfy."""
        segments = normalize_segments(len(BASE_TOKENS), [core(0, len(BASE_TOKENS))])
        self.assertEqual(flatten_segments(BASE_TOKENS, segments), BASE_TEXT)

    def test_interleaves_a_trope_between_two_cores(self):
        segments = normalize_segments(
            len(BASE_TOKENS),
            [core(0, 3), {"text": "Perpetuo numine"}, core(3, 6)],
        )
        self.assertEqual(
            flatten_segments(BASE_TOKENS, segments),
            "Sanctus sanctus sanctus Perpetuo numine Dominus Deus Sabaoth",
        )

    def test_omits_an_unreferenced_range(self):
        segments = normalize_segments(len(BASE_TOKENS), [core(0, 3), core(5, 6)])
        self.assertEqual(
            flatten_segments(BASE_TOKENS, segments), "Sanctus sanctus sanctus Sabaoth"
        )

    def test_repeats_a_range(self):
        segments = normalize_segments(
            len(BASE_TOKENS), [core(4, 6), {"text": "trope"}, core(4, 6)]
        )
        self.assertEqual(
            flatten_segments(BASE_TOKENS, segments), "Deus Sabaoth trope Deus Sabaoth"
        )

    def test_reorders_ranges(self):
        segments = normalize_segments(len(BASE_TOKENS), [core(3, 6), core(0, 3)])
        self.assertEqual(
            flatten_segments(BASE_TOKENS, segments),
            "Dominus Deus Sabaoth Sanctus sanctus sanctus",
        )

    def test_reads_a_catalogued_tropes_own_text(self):
        segments = normalize_segments(
            len(BASE_TOKENS), [core(0, 1), {"element": FakeTrope("Ad laudem tuam")}]
        )
        self.assertEqual(
            flatten_segments(BASE_TOKENS, segments), "Sanctus Ad laudem tuam"
        )

    def test_normalises_whitespace_inside_a_trope(self):
        segments = normalize_segments(
            len(BASE_TOKENS), [{"element": FakeTrope("Ad  laudem\n tuam")}]
        )
        self.assertEqual(flatten_segments(BASE_TOKENS, segments), "Ad laudem tuam")


class ComputeOmittedRangesTest(SimpleTestCase):
    def test_full_coverage_omits_nothing(self):
        segments = normalize_segments(6, [core(0, 6)])
        self.assertEqual(compute_omitted_ranges(6, segments), [])

    def test_reports_a_gap_in_the_middle(self):
        segments = normalize_segments(6, [core(0, 2), core(4, 6)])
        self.assertEqual(compute_omitted_ranges(6, segments), [(2, 4)])

    def test_reports_gaps_at_both_ends(self):
        segments = normalize_segments(6, [core(2, 4)])
        self.assertEqual(compute_omitted_ranges(6, segments), [(0, 2), (4, 6)])

    def test_a_repeat_does_not_create_a_phantom_gap(self):
        """Coverage is a set of indices, so referencing a range twice is still covered."""
        segments = normalize_segments(6, [core(0, 6), {"text": "t"}, core(0, 6)])
        self.assertEqual(compute_omitted_ranges(6, segments), [])

    def test_a_trope_only_cluster_omits_the_whole_base_text(self):
        segments = normalize_segments(6, [{"text": "trope"}])
        self.assertEqual(compute_omitted_ranges(6, segments), [(0, 6)])


class ParseClusterPayloadTest(SimpleTestCase):
    def payload(self, **overrides) -> str:
        data = {
            "base_cantus_id": "g04828",
            "base_text": BASE_TEXT,
            "segments": [core(0, 3), {"text": "Perpetuo numine"}, core(3, 6)],
        }
        data.update(overrides)
        return json.dumps(data)

    def test_returns_none_for_a_blank_field(self):
        """A chant with no cluster is the common case, not an error."""
        self.assertIsNone(parse_cluster_payload(""))
        self.assertIsNone(parse_cluster_payload("   "))

    def test_parses_a_well_formed_payload(self):
        observed = parse_cluster_payload(self.payload())
        self.assertEqual(observed["base_cantus_id"], "g04828")
        self.assertEqual(observed["base_text"], BASE_TEXT)
        self.assertEqual(len(observed["segments"]), 3)

    def test_normalises_base_text_whitespace(self):
        observed = parse_cluster_payload(
            self.payload(base_text="  Sanctus   sanctus\nsanctus  ")
        )
        self.assertEqual(observed["base_text"], "Sanctus sanctus sanctus")

    def test_rejects_malformed_json(self):
        with self.assertRaises(ValidationError):
            parse_cluster_payload("not json")

    def test_rejects_a_non_object_payload(self):
        with self.assertRaises(ValidationError):
            parse_cluster_payload("[1, 2]")

    def test_rejects_a_missing_base_text(self):
        with self.assertRaises(ValidationError):
            parse_cluster_payload(self.payload(base_text="   "))

    def test_rejects_non_list_segments(self):
        with self.assertRaises(ValidationError):
            parse_cluster_payload(self.payload(segments={"not": "a list"}))

    def test_rejects_a_range_beyond_the_base_text(self):
        """Bounds are checked against the payload's own base text, not a stored one."""
        with self.assertRaises(ValidationError):
            parse_cluster_payload(self.payload(segments=[core(0, 99)]))

    def test_moves_a_catalogued_tropes_text_out_of_the_inline_slot(self):
        """A cantus_id plus text is one shape, not two: the text is the trope's own."""
        observed = parse_cluster_payload(
            self.payload(
                segments=[{"cantus_id": "g04828:01", "text": "Perpetuo numine"}]
            )
        )
        segment = observed["segments"][0]
        self.assertEqual(segment["element"], "g04828:01")
        self.assertEqual(segment["element_text"], "Perpetuo numine")
        self.assertEqual(segment["text"], "")

    def test_rejects_a_catalogued_trope_without_its_text(self):
        """The text is needed to catalogue a trope that has no local row yet."""
        with self.assertRaises(ValidationError):
            parse_cluster_payload(self.payload(segments=[{"cantus_id": "g04828:01"}]))

    def test_keeps_an_inline_trope_in_the_text_slot(self):
        observed = parse_cluster_payload(
            self.payload(segments=[{"text": "Novum tropus"}])
        )
        segment = observed["segments"][0]
        self.assertIsNone(segment["element"])
        self.assertEqual(segment["text"], "Novum tropus")
