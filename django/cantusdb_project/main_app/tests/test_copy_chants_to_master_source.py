"""Tests for the copy_chants_to_master_source management command.

The command copies chants from two student-work sources (1000260, 1000208)
into the Kaiatonsera master source (1000289), stripping the leading 'K' from
each folio. Five (source, folio range) groups are defined in the command; see
_build_groups in the command file for the canonical definitions.
"""

import io
from dataclasses import dataclass

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from main_app.management.commands.copy_chants_to_master_source import (
    MASTER_SOURCE_ID,
    STUDENT_SOURCE_208,
    STUDENT_SOURCE_260,
)
from main_app.models import Chant, Source
from main_app.tests.make_fakes import (
    make_fake_chant,
    make_fake_feast,
    make_fake_genre,
    make_fake_service,
    make_fake_source,
    make_fake_user,
)
from users.models import User

COMMAND = "copy_chants_to_master_source"


@dataclass
class Fixture:
    chant_a: Chant
    chant_b: Chant
    proofread_user: User
    total: int


class CopyChantToMasterSourceTest(TestCase):

    @classmethod
    def setUpTestData(cls) -> None:
        cls.feast = make_fake_feast()
        cls.genre = make_fake_genre()
        cls.service = make_fake_service()
        cls.master = make_fake_source(id=MASTER_SOURCE_ID)
        cls.src_260 = make_fake_source(id=STUDENT_SOURCE_260)
        cls.src_208 = make_fake_source(id=STUDENT_SOURCE_208)

    def _shared(self) -> dict:
        return dict(feast=self.feast, genre=self.genre, service=self.service)

    def _run(self, **kwargs) -> io.StringIO:
        out = io.StringIO()
        call_command(COMMAND, stdout=out, **kwargs)
        return out

    def _build_full_fixture(self) -> Fixture:
        """Build the full multi-group fixture used by the happy-path tests.

        Group 1 contains a two-chant next_chant chain with proofread_by on the
        tail. Groups 2–5 each get one boundary-pinned exemplar. The total chant
        count is derived from the created list, so adding or removing a chant
        here doesn't require updating a hardcoded number elsewhere.
        """
        shared = self._shared()
        created: list[Chant] = []

        # Group 1 (src_260, K005–K028). chant_b is built before chant_a because
        # chant_a.next_chant=chant_b needs the target row to exist first.
        chant_b = make_fake_chant(
            source=self.src_260, folio="K005", c_sequence=2, **shared
        )
        created.append(chant_b)
        proofread_user = make_fake_user()
        chant_b.proofread_by.add(proofread_user)

        chant_a = make_fake_chant(
            source=self.src_260,
            folio="K005",
            c_sequence=1,
            next_chant=chant_b,
            **shared,
        )
        created.append(chant_a)
        created.append(
            make_fake_chant(source=self.src_260, folio="K010", c_sequence=1, **shared)
        )

        # Group 2 (src_208, K039–K053)
        created.append(
            make_fake_chant(source=self.src_208, folio="K039", c_sequence=1, **shared)
        )
        # Group 3 (src_260, K053 seq≥5–K067)
        created.append(
            make_fake_chant(source=self.src_260, folio="K053", c_sequence=5, **shared)
        )
        # Group 4 (src_260, K082–K090)
        created.append(
            make_fake_chant(source=self.src_260, folio="K082", c_sequence=1, **shared)
        )
        # Group 5 (src_208, K090 seq≥7–K108)
        created.append(
            make_fake_chant(source=self.src_208, folio="K090", c_sequence=7, **shared)
        )

        return Fixture(
            chant_a=chant_a,
            chant_b=chant_b,
            proofread_user=proofread_user,
            total=len(created),
        )

    def _build_one_per_group(self) -> int:
        """Minimal fixture: one boundary chant per group. Returns chant count."""
        shared = self._shared()
        chants = [
            make_fake_chant(source=self.src_260, folio="K005", c_sequence=1, **shared),
            make_fake_chant(source=self.src_208, folio="K039", c_sequence=1, **shared),
            make_fake_chant(source=self.src_260, folio="K053", c_sequence=5, **shared),
            make_fake_chant(source=self.src_260, folio="K082", c_sequence=1, **shared),
            make_fake_chant(source=self.src_208, folio="K090", c_sequence=7, **shared),
        ]
        return len(chants)

    # ---------------- happy path and existing guard coverage ----------------

    def test_happy_path_copies_and_transforms(self) -> None:
        fix = self._build_full_fixture()
        before = Chant.objects.filter(source_id=MASTER_SOURCE_ID).count()

        self._run(expected_total=fix.total)

        orig_b_pk = fix.chant_b.pk
        fix.chant_a.refresh_from_db()
        fix.chant_b.refresh_from_db()
        self.assertEqual(fix.chant_a.source_id, STUDENT_SOURCE_260)
        self.assertEqual(fix.chant_a.folio, "K005")
        self.assertEqual(fix.chant_a.next_chant_id, fix.chant_b.pk)

        self.assertEqual(
            Chant.objects.filter(source_id=MASTER_SOURCE_ID).count(), before + fix.total
        )

        copy_b = Chant.objects.get(source_id=MASTER_SOURCE_ID, folio="005", c_sequence=2)
        self.assertNotEqual(copy_b.pk, orig_b_pk)
        self.assertEqual(copy_b.source_id, MASTER_SOURCE_ID)
        self.assertEqual(copy_b.folio, "005")
        # Guards against the prefetch-cache regression fixed in commit c31732a0:
        # .set() reads the prefetch cache and skips the insert — must be .add().
        self.assertIn(fix.proofread_user, copy_b.proofread_by.all())

        # next_chant must rebind to the copy of chant_b, not the original donor row.
        copy_a = Chant.objects.get(source_id=MASTER_SOURCE_ID, folio="005", c_sequence=1)
        self.assertEqual(copy_a.next_chant_id, copy_b.pk)

        # copy_b is the tail of the chain — its next_chant stays None.
        self.assertIsNone(copy_b.next_chant_id)

    def test_dry_run_writes_nothing(self) -> None:
        self._build_full_fixture()
        before = Chant.objects.filter(source_id=MASTER_SOURCE_ID).count()

        # --dry-run must not require --expected-total.
        self._run(dry_run=True)

        self.assertEqual(Chant.objects.filter(source_id=MASTER_SOURCE_ID).count(), before)

    def test_expected_total_mismatch_blocks(self) -> None:
        fix = self._build_full_fixture()
        before = Chant.objects.filter(source_id=MASTER_SOURCE_ID).count()

        with self.assertRaises(CommandError):
            self._run(expected_total=fix.total + 1)
        self.assertEqual(Chant.objects.filter(source_id=MASTER_SOURCE_ID).count(), before)

        with self.assertRaisesRegex(CommandError, "--expected-total is required"):
            self._run()

        self._run(expected_total=fix.total)
        self.assertEqual(
            Chant.objects.filter(source_id=MASTER_SOURCE_ID).count(), before + fix.total
        )

    def test_master_collision_blocks(self) -> None:
        shared = self._shared()
        # Pre-seed the master slot that Group 1's K005/1 chant would map to.
        make_fake_chant(source=self.master, folio="005", c_sequence=1, **shared)
        total = self._build_one_per_group()

        before = Chant.objects.filter(source_id=MASTER_SOURCE_ID).count()
        out = io.StringIO()
        with self.assertRaises(CommandError):
            call_command(COMMAND, expected_total=total, stdout=out)

        self.assertEqual(Chant.objects.filter(source_id=MASTER_SOURCE_ID).count(), before)
        # The collision listing uses the stripped folio, so "folio='005'" only
        # appears in the COLLISION line. The per-group summary prints the
        # original "folio='K005'", which would match a looser "005" assertion.
        self.assertIn("COLLISION", out.getvalue())
        self.assertIn("folio='005'", out.getvalue())

    def test_cross_copy_collision_blocks(self) -> None:
        # Groups 2 and 3 overlap at K053 seq 5:
        #   Group 2 (src_208): folio >= K039, < K054 — includes K053
        #   Group 3 (src_260): folio = K053, c_seq >= 5
        # Both strip K → master slot (053, 5).
        shared = self._shared()
        created = [
            make_fake_chant(source=self.src_208, folio="K053", c_sequence=5, **shared),
            make_fake_chant(source=self.src_260, folio="K053", c_sequence=5, **shared),
            make_fake_chant(source=self.src_260, folio="K005", c_sequence=1, **shared),
            make_fake_chant(source=self.src_260, folio="K082", c_sequence=1, **shared),
            make_fake_chant(source=self.src_208, folio="K090", c_sequence=7, **shared),
        ]
        total = len(created)

        before = Chant.objects.filter(source_id=MASTER_SOURCE_ID).count()
        with self.assertRaises(CommandError):
            self._run(expected_total=total)
        self.assertEqual(Chant.objects.filter(source_id=MASTER_SOURCE_ID).count(), before)

    # ---------------- guards not covered by the original tests ----------------

    def test_bad_folio_blocks(self) -> None:
        # "K00Z" lies in Group 1's range (K005 <= K00Z < K029) but fails the
        # ^K\d{3}[A-Za-z]?$ regex (only two digits after K). Expected_total
        # matches so the bad-folio guard is the one that fires.
        shared = self._shared()
        make_fake_chant(source=self.src_260, folio="K00Z", c_sequence=1, **shared)

        before = Chant.objects.filter(source_id=MASTER_SOURCE_ID).count()
        with self.assertRaisesRegex(CommandError, r"do not match"):
            self._run(expected_total=1)
        self.assertEqual(Chant.objects.filter(source_id=MASTER_SOURCE_ID).count(), before)

    def test_master_source_not_found_blocks(self) -> None:
        # Drop the master source; the lookup at the top of handle() should fail
        # before any writes happen. --expected-total is passed only to satisfy
        # the earlier required-flag check.
        Source.objects.filter(id=MASTER_SOURCE_ID).delete()

        with self.assertRaisesRegex(CommandError, "Master source"):
            self._run(expected_total=0)

    def test_next_chant_at_group_boundary_stays_none(self) -> None:
        # Chant Y lives on src_260 at folio "K003", outside Group 1's range
        # (K005–K028). Chant X is inside Group 1 and points to Y. After copy,
        # X_copy.next_chant must be None because Y was never copied.
        shared = self._shared()
        chant_y = make_fake_chant(
            source=self.src_260, folio="K003", c_sequence=1, **shared
        )
        chant_x = make_fake_chant(
            source=self.src_260,
            folio="K005",
            c_sequence=1,
            next_chant=chant_y,
            **shared,
        )

        self._run(expected_total=1)

        copy_x = Chant.objects.get(source_id=MASTER_SOURCE_ID, folio="005", c_sequence=1)
        self.assertIsNone(copy_x.next_chant_id)
        # Original X still points at Y; the original chain is untouched.
        chant_x.refresh_from_db()
        self.assertEqual(chant_x.next_chant_id, chant_y.pk)
