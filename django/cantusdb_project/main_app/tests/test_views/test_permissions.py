"""
Tests permissions for a number of other views.
"""

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db.models import Q

from main_app.models import Chant, Sequence, Source
from main_app.tests.make_fakes import (
    make_fake_source,
    make_fake_chant,
    make_fake_sequence,
)


class PermissionsTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        Group.objects.create(name="project manager")
        Group.objects.create(name="contributor")
        Group.objects.create(name="editor")

        for i in range(5):
            source = make_fake_source()
            for i in range(5):
                Chant.objects.create(source=source)
                Sequence.objects.create(source=source)

    def setUp(self):
        self.user = get_user_model().objects.create(email="test@test.com")
        self.user.set_password("pass")
        self.user.save()
        self.client = Client()

    def test_login(self):
        source = make_fake_source()
        chant = make_fake_chant()
        sequence = make_fake_sequence()

        # currently not logged in, should redirect

        # ChantCreateView
        response = self.client.get(
            reverse(
                "chant-create",
                args=[source.id],
            )
        )
        self.assertRedirects(response, f"/login/?next=/chant-create/{source.id}")

        # ChantDeleteView
        response = self.client.get(
            reverse(
                "chant-delete",
                args=[chant.id],
            )
        )
        self.assertRedirects(response, f"/login/?next=/chant/{chant.id}/delete")

        # SourceEditChantsView
        response = self.client.get(
            reverse(
                "source-edit-chants",
                args=[source.id],
            )
        )
        self.assertRedirects(response, f"/login/?next=/edit-chants/{source.id}")

        # SequenceEditView
        response = self.client.get(
            reverse(
                "sequence-edit",
                args=[sequence.id],
            )
        )
        self.assertRedirects(response, f"/login/?next=/edit-sequence/{sequence.id}")

        # SourceCreateView
        response = self.client.get(reverse("source-create"))
        self.assertRedirects(response, "/login/?next=/source-create/")

        # SourceEditView
        response = self.client.get(
            reverse(
                "source-edit",
                args=[source.id],
            )
        )
        self.assertRedirects(response, f"/login/?next=/edit-source/{source.id}")

        # SourceDeleteView
        response = self.client.get(
            reverse(
                "source-delete",
                args=[source.id],
            )
        )
        self.assertRedirects(response, f"/login/?next=/source/{source.id}/delete")

        # UserSourceListView
        response = self.client.get(reverse("my-sources"))
        self.assertRedirects(response, "/login/?next=/my-sources/")

        # UserListView
        response = self.client.get(reverse("user-list"))
        self.assertRedirects(response, "/login/?next=/users/")

    def test_permissions_project_manager(self):
        project_manager = Group.objects.get(name="project manager")
        project_manager.user_set.add(self.user)
        self.client.login(email="test@test.com", password="pass")

        # get random source, chant and sequence
        source = Source.objects.order_by("?").first()
        chant = Chant.objects.order_by("?").first()
        sequence = Sequence.objects.order_by("?").first()

        # ChantCreateView
        response = self.client.get(
            reverse(
                "chant-create",
                args=[source.id],
            )
        )
        self.assertEqual(response.status_code, 200)

        # ChantDeleteView
        response = self.client.get(
            reverse(
                "chant-delete",
                args=[chant.id],
            )
        )
        self.assertEqual(response.status_code, 200)

        # SourceEditChantsView
        response = self.client.get(
            reverse(
                "source-edit-chants",
                args=[source.id],
            )
        )
        self.assertEqual(response.status_code, 200)

        # SequenceEditView
        response = self.client.get(
            reverse(
                "sequence-edit",
                args=[sequence.id],
            )
        )
        self.assertEqual(response.status_code, 200)

        # SourceCreateView
        response = self.client.get(
            reverse(
                "source-create",
            )
        )
        self.assertEqual(response.status_code, 200)

        # SourceEditView
        response = self.client.get(
            reverse(
                "source-edit",
                args=[source.id],
            )
        )
        self.assertEqual(response.status_code, 200)

        # SourceDeleteView
        response = self.client.get(
            reverse(
                "source-delete",
                args=[source.id],
            )
        )
        self.assertEqual(response.status_code, 200)

        # ContentOverview
        response = self.client.get(reverse("content-overview"))
        self.assertEqual(response.status_code, 200)

    def test_permissions_contributor(self):
        contributor = Group.objects.get(name="contributor")
        contributor.user_set.add(self.user)
        self.client.login(email="test@test.com", password="pass")

        # a source assigned to the current user
        assigned_source = make_fake_source()
        self.user.sources_user_can_edit.add(assigned_source)
        for i in range(5):
            Chant.objects.create(source=assigned_source)
        chant_in_assigned_source = (
            Chant.objects.filter(source=assigned_source).order_by("?").first()
        )

        # a source created by the current user
        source_created_by_contributor = make_fake_source()
        source_created_by_contributor.created_by = self.user
        source_created_by_contributor.save()
        for i in range(5):
            Chant.objects.create(source=source_created_by_contributor)
        chant_in_source_created_by_contributor = (
            Chant.objects.filter(source=source_created_by_contributor)
            .order_by("?")
            .first()
        )

        # did not create the source, was not assigned the source
        restricted_source = (
            Source.objects.filter(~Q(created_by=self.user) & ~Q(id=assigned_source.id))
            .order_by("?")
            .first()
        )
        restricted_chant = (
            Chant.objects.filter(source=restricted_source).order_by("?").first()
        )

        # a random sequence
        sequence = Sequence.objects.order_by("?").first()

        # ChantCreateView
        # response = self.client.get(f"/chant-create/{restricted_source.id}")
        response = self.client.get(
            reverse(
                "chant-create",
                args=[restricted_source.id],
            )
        )
        self.assertEqual(response.status_code, 403)

        response = self.client.get(f"/chant-create/{source_created_by_contributor.id}")
        self.assertEqual(response.status_code, 200)

        response = self.client.get(f"/chant-create/{assigned_source.id}")
        self.assertEqual(response.status_code, 200)

        # ChantDeleteView
        response = self.client.get(f"/chant/{restricted_chant.id}/delete")
        self.assertEqual(response.status_code, 403)

        response = self.client.get(
            f"/chant/{chant_in_source_created_by_contributor.id}/delete"
        )
        self.assertEqual(response.status_code, 200)

        response = self.client.get(f"/chant/{chant_in_assigned_source.id}/delete")
        self.assertEqual(response.status_code, 200)

        # SourceEditChantsView
        response = self.client.get(f"/edit-chants/{restricted_source.id}")
        self.assertEqual(response.status_code, 403)

        response = self.client.get(f"/edit-chants/{source_created_by_contributor.id}")
        self.assertEqual(response.status_code, 200)

        response = self.client.get(f"/edit-chants/{assigned_source.id}")
        self.assertEqual(response.status_code, 200)

        # SequenceEditView
        response = self.client.get(f"/edit-sequence/{sequence.id}")
        self.assertEqual(response.status_code, 403)

        # SourceCreateView
        response = self.client.get("/source-create/")
        self.assertEqual(response.status_code, 200)

        # SourceEditView
        response = self.client.get(f"/edit-source/{restricted_source.id}")
        self.assertEqual(response.status_code, 403)

        response = self.client.get(f"/edit-source/{source_created_by_contributor.id}")
        self.assertEqual(response.status_code, 200)

        response = self.client.get(f"/edit-source/{assigned_source.id}")
        self.assertEqual(response.status_code, 403)

        # SourceDeleteView
        response = self.client.get(f"/source/{restricted_source.id}/delete")
        self.assertEqual(response.status_code, 403)

        response = self.client.get(f"/source/{source_created_by_contributor.id}/delete")
        self.assertEqual(response.status_code, 200)

        response = self.client.get(f"/source/{assigned_source.id}/delete")
        self.assertEqual(response.status_code, 403)

        # Content Overview
        response = self.client.get(reverse("content-overview"))
        self.assertEqual(response.status_code, 403)

    def test_permissions_editor(self):
        editor = Group.objects.get(name="editor")
        editor.user_set.add(self.user)
        self.client.login(email="test@test.com", password="pass")

        # a source assigned to the current user
        assigned_source = make_fake_source()
        self.user.sources_user_can_edit.add(assigned_source)
        for i in range(5):
            Chant.objects.create(source=assigned_source)
        chant_in_assigned_source = (
            Chant.objects.filter(source=assigned_source).order_by("?").first()
        )

        # a source created by the current user
        source_created_by_contributor = make_fake_source()
        source_created_by_contributor.created_by = self.user
        source_created_by_contributor.save()
        for i in range(5):
            Chant.objects.create(source=source_created_by_contributor)
        chant_in_source_created_by_contributor = (
            Chant.objects.filter(source=source_created_by_contributor)
            .order_by("?")
            .first()
        )

        # did not create the source, was not assigned the source
        restricted_source = (
            Source.objects.filter(~Q(created_by=self.user) & ~Q(id=assigned_source.id))
            .order_by("?")
            .first()
        )
        restricted_chant = (
            Chant.objects.filter(source=restricted_source).order_by("?").first()
        )

        # a random sequence
        sequence = Sequence.objects.order_by("?").first()

        # ChantCreateView
        response = self.client.get(f"/chant-create/{restricted_source.id}")
        self.assertEqual(response.status_code, 403)

        response = self.client.get(f"/chant-create/{source_created_by_contributor.id}")
        self.assertEqual(response.status_code, 200)

        response = self.client.get(f"/chant-create/{assigned_source.id}")
        self.assertEqual(response.status_code, 200)

        # ChantDeleteView
        response = self.client.get(f"/chant/{restricted_chant.id}/delete")
        self.assertEqual(response.status_code, 403)

        response = self.client.get(
            f"/chant/{chant_in_source_created_by_contributor.id}/delete"
        )
        self.assertEqual(response.status_code, 200)

        response = self.client.get(f"/chant/{chant_in_assigned_source.id}/delete")
        self.assertEqual(response.status_code, 200)

        # SourceEditChantsView
        response = self.client.get(f"/edit-chants/{restricted_source.id}")
        self.assertEqual(response.status_code, 403)

        response = self.client.get(f"/edit-chants/{source_created_by_contributor.id}")
        self.assertEqual(response.status_code, 200)

        response = self.client.get(f"/edit-chants/{assigned_source.id}")
        self.assertEqual(response.status_code, 200)

        # SequenceEditView
        response = self.client.get(f"/edit-sequence/{sequence.id}")
        self.assertEqual(response.status_code, 403)

        # SourceCreateView
        response = self.client.get("/source-create/")
        self.assertEqual(response.status_code, 200)

        # SourceEditView
        response = self.client.get(f"/edit-source/{restricted_source.id}")
        self.assertEqual(response.status_code, 403)

        response = self.client.get(f"/edit-source/{source_created_by_contributor.id}")
        self.assertEqual(response.status_code, 200)

        response = self.client.get(f"/edit-source/{assigned_source.id}")
        self.assertEqual(response.status_code, 200)

        # SourceDeleteView
        response = self.client.get(f"/source/{restricted_source.id}/delete")
        self.assertEqual(response.status_code, 403)

        response = self.client.get(f"/source/{source_created_by_contributor.id}/delete")
        self.assertEqual(response.status_code, 200)

        response = self.client.get(f"/source/{assigned_source.id}/delete")
        self.assertEqual(response.status_code, 200)

        # Content Overview
        response = self.client.get(reverse("content-overview"))
        self.assertEqual(response.status_code, 403)

    def test_permissions_default(self):
        self.client.login(email="test@test.com", password="pass")

        # get random source, chant and sequence
        source = Source.objects.order_by("?").first()
        chant = Chant.objects.order_by("?").first()
        sequence = Sequence.objects.order_by("?").first()

        # ChantCreateView
        response = self.client.get(f"/chant-create/{source.id}")
        self.assertEqual(response.status_code, 403)

        # ChantDeleteView
        response = self.client.get(f"/chant/{chant.id}/delete")
        self.assertEqual(response.status_code, 403)

        # SourceEditChantsView
        response = self.client.get(f"/edit-chants/{source.id}")
        self.assertEqual(response.status_code, 403)

        # SequenceEditView
        response = self.client.get(f"/edit-sequence/{sequence.id}")
        self.assertEqual(response.status_code, 403)

        # SourceCreateView
        response = self.client.get("/source-create/")
        self.assertEqual(response.status_code, 403)

        # SourceEditView
        response = self.client.get(f"/edit-source/{source.id}")
        self.assertEqual(response.status_code, 403)

        # SourceDeleteView
        response = self.client.get(f"/source/{source.id}/delete")
        self.assertEqual(response.status_code, 403)

        # Content Overview
        response = self.client.get(reverse("content-overview"))
        self.assertEqual(response.status_code, 403)
