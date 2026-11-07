"""
Tests for views in views/sequence.py
"""

from typing import Any, Dict

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from faker import Faker

from main_app.models import Institution, Sequence
from main_app.tests.make_fakes import (
    make_cantus_fallback_institutions,
    make_fake_sequence,
    make_fake_source,
    make_fake_institution,
    get_random_search_term,
)
from main_app.tests.mixins import CustomAccessTestMixin

# Create a Faker instance with locale set to Latin
faker = Faker("la")


def sequence_in(
    institution: Institution | None,
    shelfmark: str,
    folio: str = "001r",
    **kwargs: Any,
) -> Sequence:
    """Make a published source held by `institution` and one sequence in it."""
    return make_fake_sequence(
        source=make_fake_source(
            published=True, shelfmark=shelfmark, holding_institution=institution
        ),
        folio=folio,
        **kwargs,
    )


def with_s_sequence(sequence: Sequence, s_sequence: str) -> Sequence:
    """Give `sequence` a known position on its folio.

    `make_fake_sequence` assigns a random one, which cannot settle a tie.
    """
    Sequence.objects.filter(id=sequence.id).update(s_sequence=s_sequence)
    sequence.s_sequence = s_sequence
    return sequence


class SequencePermissionsTestCase(CustomAccessTestMixin, TestCase):
    sequences: Dict[str, Sequence]

    @classmethod
    def setUpTestData(cls) -> None:
        super().setUpTestData()
        published_source = make_fake_source(published=True)
        published_seq = make_fake_sequence(source=published_source)
        editor_assigned_source = make_fake_source(
            published=False, current_editors=[cls.users["editor"]]
        )
        editor_assigned_seq = make_fake_sequence(source=editor_assigned_source)
        user_assigned_source = make_fake_source(
            published=False, current_editors=[cls.users["user"]]
        )
        user_assigned_seq = make_fake_sequence(source=user_assigned_source)
        unassigned_source = make_fake_source(published=False)
        unassigned_seq = make_fake_sequence(source=unassigned_source)
        cls.sequences = {
            "published_seq": published_seq,
            "editor_assigned_seq": editor_assigned_seq,
            "user_assigned_seq": user_assigned_seq,
            "unassigned_seq": unassigned_seq,
        }


class SequenceListViewTest(SequencePermissionsTestCase):
    def test_url_and_templates(self):
        response = self.client.get(reverse("sequence-list"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "base.html")
        self.assertTemplateUsed(response, "sequence_list.html")

    def test_ordering(self):
        # The list sorts by the heading each row displays — the source's current
        # institution siglum and shelfmark — then by folio and sequence number.
        # Every source without a usable institution siglum displays as "Cantus",
        # so all four of those cases belong under "C" rather than after every
        # siglum (#2025).
        b_seq = sequence_in(make_fake_institution(siglum="B-Br"), "MS 1")
        z_seq = sequence_in(make_fake_institution(siglum="Z-Zz"), "MS 1")
        cantus_seqs = [
            sequence_in(institution, f"MS {number}")
            for number, institution in enumerate(
                make_cantus_fallback_institutions().values(), start=1
            )
        ]
        d_first_shelfmark = sequence_in(make_fake_institution(siglum="D-Bs"), "MS 1")
        d_second_shelfmark = sequence_in(make_fake_institution(siglum="D-Bs"), "MS 2")
        # Same heading and folio as `d_first_shelfmark`, so only `s_sequence`
        # separates the three.
        d_same_folio_third = with_s_sequence(
            make_fake_sequence(source=d_first_shelfmark.source, folio="001r"), "03"
        )
        d_same_folio_second = with_s_sequence(
            make_fake_sequence(source=d_first_shelfmark.source, folio="001r"), "02"
        )
        with_s_sequence(d_first_shelfmark, "01")
        d_later_folio = make_fake_sequence(
            source=d_first_shelfmark.source, folio="002v"
        )
        expected = [
            b_seq,
            *cantus_seqs,
            d_first_shelfmark,
            d_same_folio_second,
            d_same_folio_third,
            d_later_folio,
            d_second_shelfmark,
            z_seq,
        ]

        response = self.client.get(reverse("sequence-list"))

        observed = [
            sequence
            for sequence in response.context["sequences"]
            if sequence in expected
        ]
        self.assertEqual(observed, expected)
        self.assertEqual(
            [sequence.source.short_heading for sequence in cantus_seqs],
            ["Cantus MS 1", "Cantus MS 2", "Cantus MS 3", "Cantus MS 4"],
        )

    def test_search_incipit(self):
        # create a published sequence source and some sequence in it
        source = make_fake_source(
            published=True,
            shelfmark="a sequence source",
        )
        sequence = make_fake_sequence(
            title=faker.sentence(),
            source=source,
        )
        search_term = get_random_search_term(sequence.incipit)
        # request the page, search for the incipit
        response = self.client.get(reverse("sequence-list"), {"incipit": search_term})
        # the sequence should be present in the results
        self.assertIn(sequence, response.context["sequences"])

    def test_search_shelfmark(self):
        # The "siglum" search box matches the source's current composed heading
        # (institution siglum + shelfmark), which is what the list displays.
        source = make_fake_source(
            published=True,
            shelfmark="a sequence source",
        )
        sequence = make_fake_sequence(source=source)
        search_term = get_random_search_term(source.shelfmark)
        # request the page, search for part of the shelfmark
        response = self.client.get(reverse("sequence-list"), {"siglum": search_term})
        # the sequence should be present in the results
        self.assertIn(sequence, response.context["sequences"])

    def test_search_uses_composed_siglum_not_legacy_column(self):
        # `Sequence.siglum` is a frozen legacy column; searching should match the
        # source's current institution siglum + shelfmark, never that stale
        # value (#2025).
        institution = make_fake_institution(siglum="gb-ob")
        source = make_fake_source(
            published=True,
            shelfmark="Laud Misc. 299",
            holding_institution=institution,
        )
        sequence = make_fake_sequence(siglum="ZZ-stale 000", source=source)

        with self.subTest("matches the current institution siglum"):
            response = self.client.get(reverse("sequence-list"), {"siglum": "gb-ob"})
            self.assertIn(sequence, response.context["sequences"])

        with self.subTest("does not match the frozen legacy column"):
            response = self.client.get(reverse("sequence-list"), {"siglum": "ZZ-stale"})
            self.assertNotIn(sequence, response.context["sequences"])

    def test_search_matches_cantus_fallback(self):
        # Every source without a usable institution siglum displays (and is
        # searched) as "Cantus <shelfmark>", mirroring
        # `Source.compose_short_heading`.
        institutions = make_cantus_fallback_institutions()
        sequences = {
            description: sequence_in(institution, f"MS {number}")
            for number, (description, institution) in enumerate(
                institutions.items(), start=1
            )
        }

        for number, (description, sequence) in enumerate(sequences.items(), start=1):
            with self.subTest(institution=description):
                heading = f"Cantus MS {number}"
                self.assertEqual(sequence.source.short_heading, heading)

                response = self.client.get(
                    reverse("sequence-list"), {"siglum": heading}
                )

                self.assertEqual(list(response.context["sequences"]), [sequence])

    def test_search_cantus_id(self):
        # create a published sequence source and some sequence in it
        source = make_fake_source(published=True, shelfmark="a sequence source")
        # faker generates a fake cantus id, in the form of two letters followed by five digits
        sequence = make_fake_sequence(cantus_id=faker.bothify("??#####"), source=source)
        search_term = get_random_search_term(sequence.cantus_id)
        # request the page, search for the incipit
        response = self.client.get(reverse("sequence-list"), {"cantus_id": search_term})
        # the sequence should be present in the results
        self.assertIn(sequence, response.context["sequences"])

    def test_permissions(self) -> None:
        with self.subTest("Visible to anonymous user"):
            resp = self.client.get(reverse("sequence-list"))
            sequences = resp.context["sequences"]
            self.assertCountEqual(sequences, [self.sequences["published_seq"]])
        with self.subTest("Visible to superuser"):
            self.client.force_login(self.users["superuser"])
            resp = self.client.get(reverse("sequence-list"))
            sequences = resp.context["sequences"]
            self.assertCountEqual(sequences, list(self.sequences.values()))
        with self.subTest("Visible to global viewer"):
            self.client.force_login(self.users["global viewer"])
            resp = self.client.get(reverse("sequence-list"))
            sequences = resp.context["sequences"]
            self.assertCountEqual(sequences, list(self.sequences.values()))
        with self.subTest("Visible to editor"):
            self.client.force_login(self.users["editor"])
            resp = self.client.get(reverse("sequence-list"))
            sequences = resp.context["sequences"]
            self.assertCountEqual(
                sequences,
                [
                    self.sequences["published_seq"],
                    self.sequences["editor_assigned_seq"],
                ],
            )
        with self.subTest("Visible to user"):
            self.client.force_login(self.users["user"])
            resp = self.client.get(reverse("sequence-list"))
            sequences = resp.context["sequences"]
            self.assertCountEqual(
                sequences,
                [self.sequences["published_seq"], self.sequences["user_assigned_seq"]],
            )
        with self.subTest("Visible to expired global viewer"):
            self.client.force_login(self.users["expired global viewer"])
            resp = self.client.get(reverse("sequence-list"))
            sequences = resp.context["sequences"]
            self.assertCountEqual(sequences, [self.sequences["published_seq"]])


class SequenceDetailViewTest(SequencePermissionsTestCase):
    def test_url_and_templates(self):
        sequence = make_fake_sequence()
        response = self.client.get(reverse("sequence-detail", args=[sequence.id]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "base.html")
        self.assertTemplateUsed(response, "sequence_detail.html")

    def test_concordances(self):
        sequence = make_fake_sequence()
        sequence_with_same_cantus_id = make_fake_sequence(cantus_id=sequence.cantus_id)
        response = self.client.get(reverse("sequence-detail", args=[sequence.id]))
        concordances = response.context["concordances"]
        self.assertIn(sequence_with_same_cantus_id, concordances)

    def test_concordances_ordering(self):
        # Concordances are ordered by the heading each row displays — the
        # source's current siglum and shelfmark — not the frozen
        # `Sequence.siglum` column (#2025). Every source without a usable
        # institution siglum displays as "Cantus", so all four of those cases
        # belong under "C" rather than after every siglum. Created out of order
        # to prove the ordering isn't just insertion order.
        cantus_id = "900000"
        first = sequence_in(
            make_fake_institution(siglum="A-Wn"), "MS 1", cantus_id=cantus_id
        )
        last = sequence_in(
            make_fake_institution(siglum="D-Bs"), "MS 1", cantus_id=cantus_id
        )
        second = sequence_in(
            make_fake_institution(siglum="A-Wn"), "MS 2", cantus_id=cantus_id
        )
        cantus_concordances = [
            sequence_in(institution, f"MS {number}", cantus_id=cantus_id)
            for number, institution in enumerate(
                make_cantus_fallback_institutions().values(), start=1
            )
        ]

        response = self.client.get(reverse("sequence-detail", args=[first.id]))

        concordances = list(response.context["concordances"])
        self.assertEqual(concordances, [first, second, *cantus_concordances, last])
        self.assertEqual(
            [sequence.source.short_heading for sequence in cantus_concordances],
            ["Cantus MS 1", "Cantus MS 2", "Cantus MS 3", "Cantus MS 4"],
        )

    def test_detail_displays_composed_siglum(self):
        # The "Siglum" field shows the source's current composed heading, not the
        # frozen `Sequence.siglum` column (#2025).
        institution = make_fake_institution(siglum="gb-ob")
        source = make_fake_source(
            published=True,
            shelfmark="Laud Misc. 299",
            holding_institution=institution,
        )
        sequence = make_fake_sequence(siglum="ZZ-stale 000", source=source)
        response = self.client.get(reverse("sequence-detail", args=[sequence.id]))
        html = response.content.decode()
        self.assertIn("gb-ob Laud Misc. 299", html)
        self.assertNotIn("ZZ-stale 000", html)

    def test_sequence_without_cantus_id(self):
        sequence = make_fake_sequence()
        sequence.cantus_id = None
        sequence.save()
        response = self.client.get(reverse("sequence-detail", args=[sequence.id]))
        html = str(response.content)
        # Since sequence's cantus_id is None, there should be no table of
        # concordances displayed, and we shouldn't display "None" anywhere
        self.assertNotIn("Concordances", html)
        self.assertNotIn("None", html)
        # This is just to ensure that `html`, `response`, etc. are working
        # correctly, i.e. that the `self.assertNotIn`s above are not passing
        # for an unrelated reason
        self.assertIn("Siglum", html)

    def test_permissions(self) -> None:
        self.run_request_permissions_test(
            url=reverse("sequence-detail", args=[self.sequences["published_seq"].id]),
            get_allowed_users=[
                "anonymous user",
                "user",
                "superuser",
                "editor",
                "global viewer",
            ],
            post_allowed_users=[],
            test_name="published sequence",
        )
        self.run_request_permissions_test(
            url=reverse(
                "sequence-detail", args=[self.sequences["editor_assigned_seq"].id]
            ),
            get_allowed_users=["superuser", "editor", "global viewer"],
            post_allowed_users=[],
            test_name="editor assigned sequence",
        )
        self.run_request_permissions_test(
            url=reverse(
                "sequence-detail", args=[self.sequences["user_assigned_seq"].id]
            ),
            get_allowed_users=["superuser", "user", "global viewer"],
            post_allowed_users=[],
            test_name="user assigned sequence",
        )
        self.run_request_permissions_test(
            url=reverse("sequence-detail", args=[self.sequences["unassigned_seq"].id]),
            get_allowed_users=["superuser", "global viewer"],
            post_allowed_users=[],
            test_name="unassigned sequence",
        )


class SequenceEditViewTest(SequencePermissionsTestCase):
    default_user = "superuser"

    def test_context(self):
        sequence = make_fake_sequence()
        response = self.client.get(reverse("sequence-edit", args=[sequence.id]))
        self.assertEqual(sequence, response.context["object"])

    def test_source_dropdown_does_not_scale_queries(self):
        """The source dropdown must not run one query per Source (#2039)."""
        sequence = make_fake_sequence()
        url = reverse("sequence-edit", args=[sequence.id])

        # Warm per-process caches (content types, permissions) so the two
        # measured requests below differ only by the number of sources.
        self.client.get(url)

        with CaptureQueriesContext(connection) as baseline:
            self.client.get(url)

        for _ in range(10):
            make_fake_source()

        with CaptureQueriesContext(connection) as with_more_sources:
            self.client.get(url)

        self.assertEqual(len(with_more_sources), len(baseline))

    def test_url_and_templates(self):
        sequence = make_fake_sequence()

        response = self.client.get(reverse("sequence-edit", args=[sequence.id]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "sequence_edit.html")

        response = self.client.get(reverse("sequence-edit", args=[sequence.id + 100]))
        self.assertEqual(response.status_code, 404)
        self.assertTemplateUsed(response, "404.html")

    def test_update_sequence(self):
        sequence = make_fake_sequence()
        sequence_id = str(sequence.id)
        response = self.client.post(
            reverse("sequence-edit", args=[sequence_id]),
            {"title": "test", "source": sequence.source.id},
        )
        self.assertEqual(response.status_code, 302)
        sequence.refresh_from_db()
        self.assertEqual(sequence.title, "test")

    def test_permissions(self) -> None:
        self.run_request_permissions_test(
            url=reverse("sequence-edit", args=[self.sequences["published_seq"].id]),
            get_allowed_users=["superuser"],
            post_allowed_users=["superuser"],
            test_name="published sequence",
        )
        self.run_request_permissions_test(
            url=reverse(
                "sequence-edit", args=[self.sequences["editor_assigned_seq"].id]
            ),
            get_allowed_users=["superuser", "editor"],
            post_allowed_users=["superuser", "editor"],
            test_name="editor assigned sequence",
        )
        self.run_request_permissions_test(
            url=reverse("sequence-edit", args=[self.sequences["user_assigned_seq"].id]),
            get_allowed_users=["superuser", "user"],
            post_allowed_users=["superuser", "user"],
            test_name="user assigned sequence",
        )
        self.run_request_permissions_test(
            url=reverse("sequence-edit", args=[self.sequences["unassigned_seq"].id]),
            get_allowed_users=["superuser"],
            post_allowed_users=["superuser"],
            test_name="unassigned sequence",
        )
