"""
Tests for views in views/sequence.py
"""

from typing import Dict

from django.test import TestCase
from django.urls import reverse
from faker import Faker

from main_app.models import Sequence
from main_app.tests.make_fakes import (
    make_fake_sequence,
    make_fake_source,
    get_random_search_term,
    make_random_string,
)
from main_app.tests.mixins import CustomAccessTestMixin

# Create a Faker instance with locale set to Latin
faker = Faker("la")


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
        # the sequences in the list should be ordered by the "siglum" and "sequence" fields
        response = self.client.get(reverse("sequence-list"))
        sequences = response.context["sequences"]
        self.assertEqual(
            sequences.query.order_by,
            (
                "source__holding_institution__siglum",
                "source__shelfmark",
                "folio",
                "s_sequence",
            ),
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
        # create a published sequence source and some sequence in it
        source = make_fake_source(
            published=True,
            shelfmark="a sequence source",
        )
        sequence = make_fake_sequence(siglum=make_random_string(6), source=source)
        search_term = get_random_search_term(sequence.siglum)
        # request the page, search for the siglum
        response = self.client.get(reverse("sequence-list"), {"siglum": search_term})
        # the sequence should be present in the results
        self.assertIn(sequence, response.context["sequences"])

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
