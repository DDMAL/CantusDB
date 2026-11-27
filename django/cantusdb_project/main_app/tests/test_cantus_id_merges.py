from datetime import date
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase, override_settings
from reversion.models import Version  # type: ignore[import-untyped]

from main_app.cantus_id_merges import read_merges, replace_merged_cantus_ids
from main_app.models import Chant, Sequence, Source
from main_app.tests.make_fakes import make_fake_chant, make_fake_sequence

FETCH = "main_app.cantus_id_merges.get_merged_cantus_ids"
SINCE = date(2026, 11, 25)

MERGES = [
    # before the start date: left for the editors
    {"old": "000100", "new": "000200", "date": "2025-06-01"},
    # since the start date
    {"old": "000300", "new": "000400", "date": "2026-11-25"},
    {"old": "000500", "new": "000600", "date": "2026-12-02"},
    # merged again, both since the start date: 000700 → 000800 → 000900
    {"old": "000700", "new": "000800", "date": "2026-12-01"},
    {"old": "000800", "new": "000900", "date": "2026-12-03"},
    # merged into two IDs: needs a person
    {"old": "g01114", "new": "g00717", "date": "2026-12-01"},
    {"old": "g01114", "new": "g05858", "date": "2026-12-02"},
    # no usable date
    {"old": "001000", "new": "001100", "date": "0000-00-00"},
]


class ReadMergesSinceTest(SimpleTestCase):
    def test_keeps_only_merges_since_the_date(self):
        merges = read_merges(MERGES, since=SINCE)
        self.assertEqual(
            sorted(merges), ["000300", "000500", "000700", "000800", "g01114"]
        )

    def test_without_a_date_keeps_every_merge(self):
        self.assertIn("000100", read_merges(MERGES))
        self.assertIn("001000", read_merges(MERGES))


@override_settings(
    CANTUS_ID_MERGES_SINCE=SINCE, CANTUS_ID_MERGES_INCLUDE_SEQUENCES=False
)
class ReplaceMergedCantusIdsTest(TestCase):
    def run_replace(self, events=MERGES):
        with patch(FETCH, return_value=events):
            return replace_merged_cantus_ids()

    def test_replaces_only_merges_since_the_start_date(self):
        recent = make_fake_chant(cantus_id="000300")
        chained = make_fake_chant(cantus_id="000700")
        old = make_fake_chant(cantus_id="000100")
        undated = make_fake_chant(cantus_id="001000")

        result = self.run_replace()

        for chant, expected in [
            (recent, "000400"),
            (chained, "000900"),
            (old, "000100"),
            (undated, "001000"),
        ]:
            chant.refresh_from_db()
            self.assertEqual(chant.cantus_id, expected)
        self.assertEqual(
            sorted((r["cantus_id"], r["new_cantus_id"]) for r in result["replaced"]),
            [("000300", "000400"), ("000700", "000900")],
        )
        self.assertIsNone(result["error"])

    def test_id_merged_into_two_is_left_for_a_person(self):
        chant = make_fake_chant(cantus_id="g01114")
        result = self.run_replace()
        chant.refresh_from_db()
        self.assertEqual(chant.cantus_id, "g01114")
        self.assertEqual([r["id"] for r in result["needs_decision"]], [chant.id])
        self.assertEqual(result["replaced"], [])

    def test_old_two_way_merges_are_reported_for_review(self):
        # both merges are older than the start date, but a person still has
        # to choose, so the record is listed every week until it's fixed
        events = MERGES + [
            {"old": "002000", "new": "002100", "date": "2024-01-01"},
            {"old": "002000", "new": "002200", "date": "2024-02-01"},
        ]
        chant = make_fake_chant(cantus_id="002000")
        result = self.run_replace(events)
        chant.refresh_from_db()
        self.assertEqual(chant.cantus_id, "002000")
        self.assertEqual([r["id"] for r in result["needs_decision"]], [chant.id])
        self.assertIn("002100, 002200", result["needs_decision"][0]["note"])

    def test_a_recent_merge_of_a_two_way_id_is_not_applied(self):
        # merged into one ID before the start date and another one since:
        # it isn't replaced with the recent one, it's listed
        events = MERGES + [
            {"old": "003000", "new": "003100", "date": "2024-01-01"},
            {"old": "003000", "new": "003200", "date": "2026-12-01"},
        ]
        chant = make_fake_chant(cantus_id="003000")
        result = self.run_replace(events)
        chant.refresh_from_db()
        self.assertEqual(chant.cantus_id, "003000")
        self.assertEqual([r["id"] for r in result["needs_decision"]], [chant.id])
        self.assertEqual(result["replaced"], [])

    def test_a_merge_into_a_two_way_id_is_listed_not_applied(self):
        # 004000 → g01114 (recent), and g01114 was merged two ways
        events = MERGES + [
            {"old": "004000", "new": "g01114", "date": "2026-12-04"},
        ]
        chant = make_fake_chant(cantus_id="004000")
        result = self.run_replace(events)
        chant.refresh_from_db()
        self.assertEqual(chant.cantus_id, "004000")
        listed = {r["id"]: r for r in result["needs_decision"]}
        self.assertIn(chant.id, listed)
        self.assertIn(
            "g01114 was merged into more than one ID", listed[chant.id]["note"]
        )

    def test_sequences_are_left_out_unless_turned_on(self):
        sequence = make_fake_sequence(cantus_id="000300")
        self.run_replace()
        sequence.refresh_from_db()
        self.assertEqual(sequence.cantus_id, "000300")

        with self.settings(CANTUS_ID_MERGES_INCLUDE_SEQUENCES=True):
            result = self.run_replace()
        sequence.refresh_from_db()
        self.assertEqual(sequence.cantus_id, "000400")
        self.assertEqual(result["replaced"][0]["kind"], "sequence")

    def test_each_record_gets_its_own_before_and_after_revision(self):
        chant = make_fake_chant(cantus_id="000500")
        self.run_replace()
        versions = list(Version.objects.get_for_object(chant).order_by("pk"))
        self.assertEqual(len(versions), 2)
        self.assertEqual(versions[0].field_dict["cantus_id"], "000500")
        self.assertEqual(versions[1].field_dict["cantus_id"], "000600")
        for version in versions:
            self.assertEqual(version.revision.version_set.count(), 1)
            self.assertIn("#2197", version.revision.comment)

    def test_leaves_last_modified_dates_alone(self):
        chant = make_fake_chant(cantus_id="000500")
        chant_date = Chant.objects.get(pk=chant.pk).date_updated
        source_date = Source.objects.get(pk=chant.source_id).date_updated
        self.run_replace()
        self.assertEqual(Chant.objects.get(pk=chant.pk).date_updated, chant_date)
        self.assertEqual(
            Source.objects.get(pk=chant.source_id).date_updated, source_date
        )

    def test_running_again_changes_nothing_more(self):
        make_fake_chant(cantus_id="000300")
        self.run_replace()
        self.assertEqual(self.run_replace()["replaced"], [])

    def test_cantus_index_unavailable(self):
        chant = make_fake_chant(cantus_id="000300")
        result = self.run_replace(events=None)
        chant.refresh_from_db()
        self.assertEqual(chant.cantus_id, "000300")
        self.assertIn("Couldn't get", result["error"])


class MergeSettingsTest(SimpleTestCase):
    def test_sequences_are_included_by_default(self):
        # Debra asked for sequences too, from the same date (#2197)
        from django.conf import settings

        self.assertTrue(settings.CANTUS_ID_MERGES_INCLUDE_SEQUENCES)
        self.assertEqual(settings.CANTUS_ID_MERGES_SINCE, SINCE)
