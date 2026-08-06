"""Model tests for troped-chant clusters.

The rules themselves are tested without a database in test_cluster_structure.py; these
cover what only the ORM can show — the frozen base text, the cached flat text, and cascade
and PROTECT behaviour.

run with `python -Wa manage.py test main_app.tests.test_chant_cluster`
"""

import json
from typing import Any

from django.core.exceptions import ValidationError
from django.db.models import ProtectedError
from django.test import TestCase

from main_app.cluster_structure import parse_cluster_payload
from main_app.models import Chant, ChantCluster, ClusterSegment, TropeElement
from main_app.tests.make_fakes import (
    make_fake_chant,
    make_fake_chant_cluster,
    make_fake_trope_element,
)

BASE_TEXT = "Sanctus sanctus sanctus Dominus Deus Sabaoth"


def core(start: int, end: int) -> dict[str, Any]:
    return {"start": start, "end": end, "element": None, "text": ""}


def inline(text: str) -> dict[str, Any]:
    return {"start": None, "end": None, "element": None, "text": text}


def catalogued(element: TropeElement) -> dict[str, Any]:
    return {"start": None, "end": None, "element": element, "text": ""}


class ChantClusterModelTest(TestCase):
    def make_cluster(self, **kwargs: Any) -> ChantCluster:
        return make_fake_chant_cluster(base_text=BASE_TEXT, **kwargs)

    def test_base_tokens_are_the_index_space(self):
        cluster = self.make_cluster()
        self.assertEqual(cluster.base_token_count, 6)
        self.assertEqual(cluster.base_tokens[0], "Sanctus")

    def test_set_structure_assigns_dense_order_from_zero(self):
        cluster = self.make_cluster()
        cluster.set_structure([core(0, 3), inline("Perpetuo numine"), core(3, 6)])
        self.assertEqual(
            list(cluster.segments.values_list("order", flat=True)), [0, 1, 2]
        )

    def test_set_structure_caches_the_flat_text_on_the_chant(self):
        """The cache is what display and search read, so it must be written on save."""
        cluster = self.make_cluster()
        cluster.set_structure([core(0, 3), inline("Perpetuo numine"), core(3, 6)])
        cluster.chant.refresh_from_db()
        self.assertEqual(
            cluster.chant.manuscript_full_text_std_spelling,
            "Sanctus sanctus sanctus Perpetuo numine Dominus Deus Sabaoth",
        )

    def test_whole_base_text_flattens_back_to_the_base_text(self):
        """The round-trip invariant, through the database this time."""
        cluster = self.make_cluster()
        cluster.set_structure([core(0, 6)])
        self.assertEqual(cluster.flatten(), BASE_TEXT)

    def test_set_structure_replaces_rather_than_appends(self):
        cluster = self.make_cluster()
        cluster.set_structure([core(0, 3), inline("first")])
        cluster.set_structure([core(0, 6)])
        self.assertEqual(cluster.segments.count(), 1)
        self.assertEqual(cluster.flatten(), BASE_TEXT)

    def test_set_structure_canonicalises_contiguous_cores(self):
        """Canonicalisation is a whole-cluster job, so it belongs to this write path."""
        cluster = self.make_cluster()
        cluster.set_structure([core(0, 2), core(2, 4), core(4, 6)])
        self.assertEqual(cluster.segments.count(), 1)
        segment = cluster.segments.get()
        self.assertEqual((segment.start, segment.end), (0, 6))

    def test_set_structure_rejects_a_bad_list_without_touching_the_stored_one(self):
        """A rejected payload must leave the cluster exactly as it was."""
        cluster = self.make_cluster()
        cluster.set_structure([core(0, 6)])
        with self.assertRaises(ValidationError):
            cluster.set_structure([core(0, 99)])
        self.assertEqual(cluster.segments.count(), 1)
        self.assertEqual(cluster.flatten(), BASE_TEXT)

    def test_repeated_range_renders_twice(self):
        """A repetendum — the reason segments are a sequence, not an edit script."""
        cluster = self.make_cluster()
        cluster.set_structure([core(4, 6), inline("trope"), core(4, 6)])
        self.assertEqual(cluster.flatten(), "Deus Sabaoth trope Deus Sabaoth")

    def test_reordered_ranges_render_in_segment_order(self):
        cluster = self.make_cluster()
        cluster.set_structure([core(3, 6), core(0, 3)])
        self.assertEqual(
            cluster.flatten(), "Dominus Deus Sabaoth Sanctus sanctus sanctus"
        )

    def test_omitted_ranges_are_derived_from_the_segments(self):
        cluster = self.make_cluster()
        cluster.set_structure([core(0, 2), inline("trope"), core(4, 6)])
        self.assertEqual(cluster.omitted_ranges, [(2, 4)])

    def test_a_repeated_range_does_not_inflate_a_cantus_id_count(self):
        """The base Cantus ID lives on the cluster, so splitting or repeating base text
        cannot change how many instances of that ID exist."""
        chant = make_fake_chant(cantus_id="g04828")
        cluster = make_fake_chant_cluster(
            chant=chant, base_text=BASE_TEXT, base_cantus_id="g04828"
        )
        cluster.set_structure([core(0, 3), inline("t"), core(0, 3), inline("u")])
        self.assertEqual(Chant.objects.filter(cantus_id="g04828").count(), 1)
        self.assertEqual(
            ChantCluster.objects.filter(base_cantus_id="g04828").count(), 1
        )

    def test_base_text_is_frozen_while_segments_exist(self):
        """Segment ranges are indices into it, so editing it would shift them silently."""
        cluster = self.make_cluster()
        cluster.set_structure([core(0, 6)])
        stored = ChantCluster.objects.get(pk=cluster.pk)
        stored.base_text = "A completely different base text"
        with self.assertRaises(ValidationError):
            stored.save()

    def test_base_text_may_change_once_the_segments_are_gone(self):
        """Deleting the segments is how a cluster is deliberately re-anchored."""
        cluster = self.make_cluster()
        cluster.set_structure([core(0, 6)])
        cluster.segments.all().delete()
        stored = ChantCluster.objects.get(pk=cluster.pk)
        stored.base_text = "Alia verba omnino"
        stored.save()
        stored.refresh_from_db()
        self.assertEqual(stored.base_text, "Alia verba omnino")

    def test_a_blank_base_text_is_rejected(self):
        chant = make_fake_chant()
        with self.assertRaises(ValidationError):
            ChantCluster(chant=chant, base_cantus_id="g1", base_text="   ").save()

    def test_hash_base_text_ignores_whitespace_differences(self):
        """Cosmetic reflowing upstream must not read as content drift."""
        self.assertEqual(
            ChantCluster.hash_base_text("Sanctus  sanctus"),
            ChantCluster.hash_base_text("Sanctus sanctus"),
        )

    def test_hash_base_text_changes_with_content(self):
        self.assertNotEqual(
            ChantCluster.hash_base_text("Sanctus sanctus"),
            ChantCluster.hash_base_text("Sanctus sanctus sanctus"),
        )

    def test_segments_are_deleted_with_the_cluster(self):
        cluster = self.make_cluster()
        cluster.set_structure([core(0, 3), inline("trope")])
        cluster.delete()
        self.assertEqual(ClusterSegment.objects.count(), 0)

    def test_cluster_is_deleted_with_its_chant(self):
        cluster = self.make_cluster()
        cluster.set_structure([core(0, 6)])
        cluster.chant.delete()
        self.assertEqual(ChantCluster.objects.count(), 0)
        self.assertEqual(ClusterSegment.objects.count(), 0)

    def test_as_payload_round_trips_through_the_submit_path(self):
        """What a client receives for an edit is what it would send for the same state.

        Goes the whole way an edit does — serialise, parse, apply — so a mismatch between
        what `as_payload` emits and what `parse_cluster_payload` accepts shows up here
        rather than as a silently mangled cluster.
        """
        element = make_fake_trope_element(cantus_id="g04828:01", text="Ad laudem tuam")
        cluster = self.make_cluster()
        cluster.set_structure(
            [core(0, 3), catalogued(element), inline("Novum tropus"), core(3, 6)]
        )
        expected_text = cluster.flatten()

        payload = parse_cluster_payload(json.dumps(cluster.as_payload()))
        reapplied = ChantCluster.apply_payload(cluster.chant, payload)

        self.assertEqual(reapplied.flatten(), expected_text)
        self.assertEqual(reapplied.as_payload(), cluster.as_payload())
        # The trope was already catalogued, so the round trip must not have made another.
        self.assertEqual(TropeElement.objects.count(), 1)


class TropeElementModelTest(TestCase):
    def test_cantus_id_is_unique(self):
        """Required-and-unique, so there can be no ID-less rows to defeat deduplication."""
        make_fake_trope_element(cantus_id="g04828:01")
        # BaseModel.save() runs full_clean(), so uniqueness surfaces as a ValidationError
        # before the database constraint is reached.
        with self.assertRaises(ValidationError):
            make_fake_trope_element(cantus_id="g04828:01")

    def test_one_trope_is_shared_by_many_chants(self):
        """The point of a separate table: no per-chant copies of a trope's text."""
        element = make_fake_trope_element(cantus_id="g04828:01", text="Ad laudem tuam")
        for _ in range(3):
            cluster = make_fake_chant_cluster(base_text=BASE_TEXT)
            cluster.set_structure([core(0, 3), catalogued(element)])
        self.assertEqual(TropeElement.objects.count(), 1)
        self.assertEqual(element.clustersegment_set.count(), 3)

    def test_a_referenced_trope_cannot_be_deleted(self):
        """PROTECT: a shared trope must not vanish from under the clusters using it."""
        element = make_fake_trope_element()
        cluster = make_fake_chant_cluster(base_text=BASE_TEXT)
        cluster.set_structure([core(0, 3), catalogued(element)])
        with self.assertRaises(ProtectedError):
            element.delete()

    def test_apply_payload_creates_a_missing_trope_row(self):
        chant = make_fake_chant()
        ChantCluster.apply_payload(
            chant,
            {
                "base_cantus_id": "g04828",
                "base_text": BASE_TEXT,
                "segments": [
                    {
                        "start": None,
                        "end": None,
                        "element": "g04828:09",
                        "text": "",
                        "element_text": "Perpetuo numine",
                    }
                ],
            },
        )
        element = TropeElement.objects.get(cantus_id="g04828:09")
        self.assertEqual(element.text, "Perpetuo numine")

    def test_apply_payload_never_overwrites_an_existing_tropes_text(self):
        """Editing one chant must not rewrite a trope everywhere else it appears."""
        make_fake_trope_element(cantus_id="g04828:09", text="Catalogued text")
        chant = make_fake_chant()
        ChantCluster.apply_payload(
            chant,
            {
                "base_cantus_id": "g04828",
                "base_text": BASE_TEXT,
                "segments": [
                    {
                        "start": None,
                        "end": None,
                        "element": "g04828:09",
                        "text": "",
                        "element_text": "A client's rewrite",
                    }
                ],
            },
        )
        self.assertEqual(
            TropeElement.objects.get(cantus_id="g04828:09").text, "Catalogued text"
        )


class ClusterSegmentModelTest(TestCase):
    def setUp(self) -> None:
        self.cluster = make_fake_chant_cluster(base_text=BASE_TEXT)

    def test_rejects_a_segment_with_no_shape(self):
        with self.assertRaises(ValidationError):
            ClusterSegment(cluster=self.cluster, order=0).save()

    def test_rejects_a_segment_with_two_shapes(self):
        with self.assertRaises(ValidationError):
            ClusterSegment(
                cluster=self.cluster, order=0, start=0, end=2, text="also a trope"
            ).save()

    def test_rejects_an_out_of_bounds_range(self):
        with self.assertRaises(ValidationError):
            ClusterSegment(cluster=self.cluster, order=0, start=0, end=99).save()

    def test_is_core_distinguishes_the_shapes(self):
        self.cluster.set_structure([core(0, 3), inline("trope")])
        first, second = list(self.cluster.segments.all())
        self.assertTrue(first.is_core)
        self.assertFalse(second.is_core)

    def test_resolved_text_of_a_core_is_its_base_span(self):
        self.cluster.set_structure([core(0, 3)])
        self.assertEqual(
            self.cluster.segments.get().resolved_text, "Sanctus sanctus sanctus"
        )

    def test_resolved_text_of_a_catalogued_trope_is_the_shared_rows_text(self):
        element = make_fake_trope_element(text="Ad laudem tuam")
        self.cluster.set_structure([catalogued(element)])
        self.assertEqual(self.cluster.segments.get().resolved_text, "Ad laudem tuam")

