"""
Test views in views/source.py
"""

import random
import re

from faker import Faker
from typing import Dict

from django.conf import settings
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.core.exceptions import ObjectDoesNotExist
from django.contrib.auth import get_user_model

from main_app.models import Source, Chant, Differentia, SourceIdentifier, SourceURL
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
    make_fake_user,
)
from main_app.tests.mixins import HTMLContentsTestMixin, CustomAccessTestMixin
from main_app.views.source import SourceListView
from users.models import User as UserAnnotation

# Create a Faker instance with locale set to Latin
faker = Faker("la")


class CsvExportLinkTestMixin:
    """
    A mixin for pages that link to a source's CSV export.
    """

    def assertCsvExportLinkHasNoDownloadAttribute(
        self, html: str, source_id: int
    ) -> None:
        """
        Assert the page's CSV export link carries no ``download`` attribute.

        ``csv_export`` names the downloaded file via ``Content-Disposition``; a
        client-side ``download`` attribute on the link would override it.

        :param html: The rendered HTML of the page containing the link.
        :param source_id: The ID of the source the export link points to.
        """
        # Scope the assertion to the export anchor rather than the whole page.
        csv_url = reverse("csv-export", args=[source_id])
        match = re.search(rf'<a\b[^>]*href="{re.escape(csv_url)}"[^>]*>', html)
        anchor_tag = match.group(0) if match else ""
        self.assertTrue(anchor_tag, "CSV export link not found in the response")
        # `\sdownload\b` matches the attribute with or without a value, but not
        # attribute names that merely contain the word, e.g. `data-download-name`.
        self.assertNotRegex(anchor_tag, r"\sdownload\b")


class SourcePermissionsTestCase(CustomAccessTestMixin, TestCase):
    sources: Dict[str, Source]
    view_name: str

    @classmethod
    def setUpTestData(cls) -> None:
        super().setUpTestData()
        cls.sources = {
            "published_source": make_fake_source(),
            "unassigned_source": make_fake_source(published=False),
            "user_assigned_source": make_fake_source(
                current_editors=[cls.users["user"]],
                published=False,
            ),
            "editor_assigned_source": make_fake_source(
                current_editors=[cls.users["editor"]], published=False
            ),
        }

    def _run_get_permissions_test(self) -> None:
        self.run_request_permissions_test(
            url=reverse(self.view_name, args=[self.sources["published_source"].id]),
            get_allowed_users=[
                "anonymous user",
                "user",
                "editor",
                "superuser",
                "global viewer",
            ],
            post_allowed_users=[],
            test_name="Published source",
        )
        self.run_request_permissions_test(
            url=reverse(self.view_name, args=[self.sources["unassigned_source"].id]),
            get_allowed_users=["superuser", "global viewer"],
            post_allowed_users=[],
            test_name="Unassigned source",
        )
        self.run_request_permissions_test(
            url=reverse(self.view_name, args=[self.sources["user_assigned_source"].id]),
            get_allowed_users=["user", "superuser", "global viewer"],
            post_allowed_users=[],
            test_name="User assigned source",
        )
        self.run_request_permissions_test(
            url=reverse(
                self.view_name, args=[self.sources["editor_assigned_source"].id]
            ),
            get_allowed_users=["editor", "superuser", "global viewer"],
            post_allowed_users=[],
            test_name="Editor assigned source",
        )


class SourceCreateViewTest(TestCase):
    user: UserAnnotation

    @classmethod
    def setUpTestData(cls) -> None:
        cls.user = make_fake_user()
        # A source created will automatically be assigned
        # to the CANTUS Database segment. We need to
        # ensure that such a segment exists.
        make_fake_segment(name="CANTUS Database")

    def setUp(self) -> None:
        self.client.force_login(self.user)

    def test_permissions(self) -> None:
        with self.subTest("Anonymous user"):
            self.client.logout()
            response = self.client.get(reverse("source-create"))
            self.assertEqual(response.status_code, 302)
            self.assertRedirects(
                response,
                f"{reverse('login')}?next={reverse('source-create')}",
            )
        with self.subTest("Authenticated user"):
            self.client.force_login(self.user)
            response = self.client.get(reverse("source-create"))
            self.assertEqual(response.status_code, 200)

    def test_url_and_templates(self) -> None:
        response = self.client.get(reverse("source-create"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "source_create.html")

    def test_create_source(self) -> None:
        response = self.client.post(
            reverse("source-create"),
            {
                "shelfmark": "test-shelfmark",  # shelfmark is a required field
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

    def test_segment_m2m_excludes_benedicamus_domino(self) -> None:
        # "Benedicamus Domino" is a chant-level project designation, not a
        # source segment, so it should not be offered here (see #2131).
        make_fake_segment(
            name="Benedicamus Domino", id=settings.BENEDICAMUS_DOMINO_SEGMENT_ID
        )
        response = self.client.get(reverse("source-create"))
        segment_ids = (
            response.context["form"]
            .fields["segment_m2m"]
            .queryset.values_list("id", flat=True)
        )
        self.assertNotIn(settings.BENEDICAMUS_DOMINO_SEGMENT_ID, segment_ids)


class SourceEditViewTest(CsvExportLinkTestMixin, CustomAccessTestMixin, TestCase):
    default_user = "editor"
    sources: Dict[str, Source]

    @classmethod
    def setUpTestData(cls) -> None:
        super().setUpTestData()
        cls.sources = {
            "unassigned_source": make_fake_source(),
            "user_assigned_source": make_fake_source(
                current_editors=[cls.users["user"]]
            ),
            "editor_assigned_source": make_fake_source(
                current_editors=[cls.users["editor"]]
            ),
            "user_created_source": make_fake_source(
                current_editors=[cls.users["user"]]
            ),
        }
        cls.sources["user_created_source"].created_by = cls.users["user"]
        cls.sources["user_created_source"].save()

    def test_permissions(self) -> None:
        self.run_request_permissions_test(
            url=reverse("source-edit", args=[self.sources["unassigned_source"].id]),
            get_allowed_users=["superuser"],
            post_allowed_users=["superuser"],
            test_name="Unassigned source",
        )
        self.run_request_permissions_test(
            url=reverse("source-edit", args=[self.sources["user_assigned_source"].id]),
            get_allowed_users=["superuser"],
            post_allowed_users=["superuser"],
            test_name="User assigned source",
        )
        self.run_request_permissions_test(
            url=reverse(
                "source-edit", args=[self.sources["editor_assigned_source"].id]
            ),
            get_allowed_users=["editor", "superuser"],
            post_allowed_users=["editor", "superuser"],
            test_name="Editor assigned source",
        )
        self.run_request_permissions_test(
            url=reverse("source-edit", args=[self.sources["user_created_source"].id]),
            get_allowed_users=["user", "superuser"],
            post_allowed_users=["user", "superuser"],
            test_name="User created source",
        )

    def test_context(self) -> None:
        source = self.sources["editor_assigned_source"]
        response = self.client.get(reverse("source-edit", args=[source.id]))
        self.assertEqual(source, response.context["object"])

    def test_url_and_templates(self) -> None:
        source = self.sources["editor_assigned_source"]
        response = self.client.get(reverse("source-edit", args=[source.id]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "source_edit.html")

        response = self.client.get(reverse("source-edit", args=[source.id + 100]))
        self.assertEqual(response.status_code, 404)
        self.assertTemplateUsed(response, "404.html")

    def test_csv_export_link_uses_response_filename(self) -> None:
        source = self.sources["editor_assigned_source"]
        response = self.client.get(reverse("source-edit", args=[source.id]))

        self.assertCsvExportLinkHasNoDownloadAttribute(
            response.content.decode("utf-8"), source.id
        )

    def test_edit_source(self) -> None:
        source = self.sources["editor_assigned_source"]
        response = self.client.post(
            reverse("source-edit", args=[source.id]),
            {
                "shelfmark": "test-shelfmark",  # shelfmark is a required field,
                "source_completeness": "1",  # required field
                "production_method": "1",  # required field
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse("source-detail", args=[source.id]))
        source.refresh_from_db()
        self.assertEqual(source.shelfmark, "test-shelfmark")

    def test_segment_m2m_excludes_benedicamus_domino(self) -> None:
        # "Benedicamus Domino" is a chant-level project designation, not a
        # source segment, so it should not be offered here (see #2131).
        make_fake_segment(
            name="Benedicamus Domino", id=settings.BENEDICAMUS_DOMINO_SEGMENT_ID
        )
        source = self.sources["editor_assigned_source"]
        response = self.client.get(reverse("source-edit", args=[source.id]))
        segment_ids = (
            response.context["form"]
            .fields["segment_m2m"]
            .queryset.values_list("id", flat=True)
        )
        self.assertNotIn(settings.BENEDICAMUS_DOMINO_SEGMENT_ID, segment_ids)


class SourceSubmitForProofreadingViewTest(CustomAccessTestMixin, TestCase):
    default_user = "editor"
    sources: Dict[str, Source]

    @classmethod
    def setUpTestData(cls) -> None:
        super().setUpTestData()
        cls.sources = {
            "unassigned_source": make_fake_source(),
            "user_assigned_source": make_fake_source(
                current_editors=[cls.users["user"]]
            ),
            "editor_assigned_source": make_fake_source(
                current_editors=[cls.users["editor"]]
            ),
            "user_created_source": make_fake_source(
                current_editors=[cls.users["user"], cls.users["editor"]],
                published=False,
            ),
        }
        cls.sources["user_created_source"].created_by = cls.users["user"]
        cls.sources["user_created_source"].save()

    def test_permissions(self) -> None:
        self.run_request_permissions_test(
            url=reverse(
                "source-submit-for-proofreading",
                args=[self.sources["unassigned_source"].id],
            ),
            get_allowed_users=["superuser"],
            post_allowed_users=["superuser"],
            test_name="Unassigned source",
        )
        self.run_request_permissions_test(
            url=reverse(
                "source-submit-for-proofreading",
                args=[self.sources["user_assigned_source"].id],
            ),
            get_allowed_users=["user", "superuser"],
            post_allowed_users=["user", "superuser"],
            test_name="User assigned source",
        )
        self.run_request_permissions_test(
            url=reverse(
                "source-submit-for-proofreading",
                args=[self.sources["editor_assigned_source"].id],
            ),
            get_allowed_users=["editor", "superuser"],
            post_allowed_users=["editor", "superuser"],
            test_name="Editor assigned source",
        )
        self.run_request_permissions_test(
            url=reverse(
                "source-submit-for-proofreading",
                args=[self.sources["user_created_source"].id],
            ),
            get_allowed_users=["user", "editor", "superuser"],
            post_allowed_users=["user", "editor", "superuser"],
            test_name="User created source",
        )

    def test_submit_locks_editing_for_creator(self) -> None:
        source = self.sources["user_created_source"]
        self.client.force_login(user=self.users["user"])
        response = self.client.post(
            reverse("source-submit-for-proofreading", args=[source.id])
        )
        self.assertRedirects(response, reverse("source-detail", args=[source.id]))
        source.refresh_from_db()
        self.assertEqual(source.source_status, Source.PROOFREAD_PENDING_STATUS)

        # the creator can no longer edit the source, but can still view it
        edit_response = self.client.get(reverse("source-edit", args=[source.id]))
        self.assertEqual(edit_response.status_code, 403)
        detail_response = self.client.get(reverse("source-detail", args=[source.id]))
        self.assertEqual(detail_response.status_code, 200)

        # an editor assigned to the source can still edit it to proofread
        self.client.force_login(user=self.users["editor"])
        editor_edit_response = self.client.get(reverse("source-edit", args=[source.id]))
        self.assertEqual(editor_edit_response.status_code, 200)

    def test_submit_records_submitting_user(self) -> None:
        source = self.sources["user_created_source"]
        self.client.force_login(user=self.users["user"])
        self.client.post(reverse("source-submit-for-proofreading", args=[source.id]))
        source.refresh_from_db()
        self.assertEqual(source.last_updated_by, self.users["user"])

    def test_submit_bumps_date_updated(self) -> None:
        # "My sources" orders by `-date_updated`, so a submitted source has to
        # float to the top of the queue it is meant to create.
        source = self.sources["user_created_source"]
        before = source.date_updated
        self.client.force_login(user=self.users["user"])
        self.client.post(reverse("source-submit-for-proofreading", args=[source.id]))
        source.refresh_from_db()
        self.assertGreater(source.date_updated, before)

    def test_editor_can_submit(self) -> None:
        source = self.sources["editor_assigned_source"]
        self.client.force_login(user=self.users["editor"])
        response = self.client.post(
            reverse("source-submit-for-proofreading", args=[source.id])
        )
        self.assertRedirects(response, reverse("source-detail", args=[source.id]))
        source.refresh_from_db()
        self.assertEqual(source.source_status, Source.PROOFREAD_PENDING_STATUS)

    def test_assigned_non_creator_can_submit(self) -> None:
        # An indexer is routinely assigned to a source someone else created;
        # #1962 asks for whoever is working on it to be able to hand it over.
        source = self.sources["user_assigned_source"]
        self.assertNotEqual(source.created_by, self.users["user"])
        self.client.force_login(user=self.users["user"])
        response = self.client.post(
            reverse("source-submit-for-proofreading", args=[source.id])
        )
        self.assertRedirects(response, reverse("source-detail", args=[source.id]))
        source.refresh_from_db()
        self.assertEqual(source.source_status, Source.PROOFREAD_PENDING_STATUS)

    def test_submitter_keeps_view_access_to_unpublished_source(self) -> None:
        source = self.sources["user_created_source"]
        self.assertFalse(source.published)
        self.client.force_login(user=self.users["user"])
        self.client.post(reverse("source-submit-for-proofreading", args=[source.id]))
        self.assertEqual(
            self.client.get(reverse("source-detail", args=[source.id])).status_code, 200
        )
        # ...and the source really is hidden from everyone else.
        self.client.logout()
        self.assertNotEqual(
            self.client.get(reverse("source-detail", args=[source.id])).status_code, 200
        )

    def test_detail_page_hides_edit_link_once_locked(self) -> None:
        source = self.sources["user_created_source"]
        self.client.force_login(user=self.users["user"])
        detail_url = reverse("source-detail", args=[source.id])
        self.assertTrue(self.client.get(detail_url).context["user_can_edit_source"])
        self.client.post(reverse("source-submit-for-proofreading", args=[source.id]))
        self.assertFalse(self.client.get(detail_url).context["user_can_edit_source"])

    def test_locked_source_cannot_be_resubmitted_by_non_editor(self) -> None:
        # The submitter loses edit access on submit, so they must not be able
        # to keep reposting and rewriting the source's audit fields.
        source = self.sources["user_created_source"]
        self.client.force_login(user=self.users["user"])
        url = reverse("source-submit-for-proofreading", args=[source.id])
        self.client.post(url)
        source.refresh_from_db()
        submitted_by, submitted_at = source.last_updated_by, source.date_updated

        response = self.client.post(url)
        self.assertEqual(response.status_code, 403)
        source.refresh_from_db()
        self.assertEqual(source.last_updated_by, submitted_by)
        self.assertEqual(source.date_updated, submitted_at)

    def test_editor_can_resubmit_locked_source(self) -> None:
        source = self.sources["user_created_source"]
        self.client.force_login(user=self.users["user"])
        url = reverse("source-submit-for-proofreading", args=[source.id])
        self.client.post(url)

        self.client.force_login(user=self.users["editor"])
        self.assertRedirects(
            self.client.post(url), reverse("source-detail", args=[source.id])
        )

    def test_submit_locks_chant_editing(self) -> None:
        # #1962 asks for the submitter's edit access to be removed. Chant
        # entry is the bulk of what an indexer does, so a lock that covered
        # only the source record would leave them able to add, retext and
        # delete every chant after being told editing was locked.
        source = self.sources["user_created_source"]
        chant = make_fake_chant(source=source)
        self.client.force_login(user=self.users["user"])
        self.client.post(reverse("source-submit-for-proofreading", args=[source.id]))

        locked_urls = {
            "chant-create": reverse("chant-create", args=[source.id]),
            "source-edit-chants": reverse("source-edit-chants", args=[source.pk]),
            "chant-delete": reverse("chant-delete", args=[chant.id]),
            "source-edit-syllabification": reverse(
                "source-edit-syllabification", args=[chant.id]
            ),
        }
        for name, url in locked_urls.items():
            with self.subTest(f"creator locked out of {name}"):
                self.assertEqual(self.client.get(url).status_code, 403)
        with self.subTest("creator locked out of the bulk chant edit"):
            # A GET here is the readable Browse Chants page; only the POST
            # that saves the bulk-edit formset is an edit.
            self.assertEqual(
                self.client.post(
                    reverse("browse-chants", args=[source.id])
                ).status_code,
                403,
            )

        # an editor picking the source up for proofreading keeps chant access
        self.client.force_login(user=self.users["editor"])
        for name, url in locked_urls.items():
            with self.subTest(f"editor still reaches {name}"):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_submit_hides_chant_edit_links_on_detail_page(self) -> None:
        source = self.sources["user_created_source"]
        make_fake_chant(source=source)
        self.client.force_login(user=self.users["user"])
        detail_url = reverse("source-detail", args=[source.id])
        self.assertTrue(self.client.get(detail_url).context["user_can_edit_chants"])
        self.client.post(reverse("source-submit-for-proofreading", args=[source.id]))
        response = self.client.get(detail_url)
        self.assertFalse(response.context["user_can_edit_chants"])
        self.assertNotContains(response, reverse("chant-create", args=[source.id]))

    def test_submit_locks_sequence_editing(self) -> None:
        # Bower-segment sources hold sequences rather than chants, and the
        # same lock has to reach them.
        sequence = make_fake_sequence()
        source = sequence.source
        source.current_editors.set([self.users["user"], self.users["editor"]])
        source.created_by = self.users["user"]
        source.published = False
        source.save()
        edit_url = reverse("sequence-edit", args=[sequence.id])

        self.client.force_login(user=self.users["user"])
        self.assertEqual(self.client.get(edit_url).status_code, 200)
        self.client.post(reverse("source-submit-for-proofreading", args=[source.id]))
        self.assertEqual(self.client.get(edit_url).status_code, 403)

        self.client.force_login(user=self.users["editor"])
        self.assertEqual(self.client.get(edit_url).status_code, 200)

    def test_assigned_non_creator_can_reach_the_submit_button(self) -> None:
        # The edit page's button is behind assigned-and-(editor-or-creator),
        # so an assigned indexer who did not create the source cannot open the
        # page holding it. The rule is "any assigned user may submit", so the
        # button has to live somewhere they can actually get to.
        source = self.sources["user_assigned_source"]
        self.assertNotEqual(source.created_by, self.users["user"])
        self.client.force_login(user=self.users["user"])

        self.assertEqual(
            self.client.get(reverse("source-edit", args=[source.id])).status_code, 403
        )
        detail = self.client.get(reverse("source-detail", args=[source.id]))
        self.assertEqual(detail.status_code, 200)
        self.assertTrue(detail.context["user_can_submit_for_proofreading"])
        self.assertContains(
            detail, reverse("source-submit-for-proofreading", args=[source.id])
        )
        # `{# #}` only comments out a single line; a multi-line one renders as
        # page text, which this template has leaked before (see #2238).
        self.assertNotContains(detail, "{#")

    def test_detail_page_hides_submit_button_once_locked(self) -> None:
        source = self.sources["user_created_source"]
        self.client.force_login(user=self.users["user"])
        detail_url = reverse("source-detail", args=[source.id])
        submit_url = reverse("source-submit-for-proofreading", args=[source.id])
        self.assertTrue(
            self.client.get(detail_url).context["user_can_submit_for_proofreading"]
        )
        self.client.post(submit_url)
        response = self.client.get(detail_url)
        self.assertFalse(response.context["user_can_submit_for_proofreading"])
        self.assertNotContains(response, submit_url)

    def test_detail_page_hides_submit_button_from_unassigned_user(self) -> None:
        source = self.sources["unassigned_source"]
        self.client.force_login(user=self.users["user"])
        detail = self.client.get(reverse("source-detail", args=[source.id]))
        self.assertFalse(detail.context["user_can_submit_for_proofreading"])

    def test_submitting_through_edit_form_saves_pending_edits(self) -> None:
        # The button lives inside the edit form; submitting also locks the
        # source, so corrections dropped here could never be redone.
        source = self.sources["user_created_source"]
        self.client.force_login(user=self.users["user"])
        response = self.client.post(
            reverse("source-edit", args=[source.id]),
            {
                "shelfmark": "edited-then-submitted",
                "source_completeness": "1",
                "production_method": "1",
                "submit_for_proofreading": "1",
            },
        )
        self.assertRedirects(response, reverse("source-detail", args=[source.id]))
        source.refresh_from_db()
        self.assertEqual(source.shelfmark, "edited-then-submitted")
        self.assertEqual(source.source_status, Source.PROOFREAD_PENDING_STATUS)


class SourceDetailViewTest(CsvExportLinkTestMixin, SourcePermissionsTestCase):
    view_name = "source-detail"

    def test_permissions(self) -> None:
        self._run_get_permissions_test()

    def test_url_and_templates(self) -> None:
        source = make_fake_source()
        response = self.client.get(reverse("source-detail", args=[source.id]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "base.html")
        self.assertTemplateUsed(response, "source_detail.html")

    def test_add_image_links_entry_is_superuser_only(self) -> None:
        """The edit-options card's "Add image links" entry is superuser-only.

        ``SourceAddImageLinksView`` is gated on ``is_superuser``, but the card
        it lives in is gated on the broader ``user_can_edit_chants``. An editor
        who can edit chants must not see a link that would 403 them.
        """
        source = self.sources["editor_assigned_source"]
        detail_url = reverse("source-detail", args=[source.id])
        image_links_url = reverse("source-add-image-links", args=[source.id])
        with self.subTest("Superuser sees the link"):
            self.client.force_login(self.users["superuser"])
            self.assertContains(self.client.get(detail_url), image_links_url)
        with self.subTest("Editor with edit access does not see the link"):
            self.client.force_login(self.users["editor"])
            response = self.client.get(detail_url)
            # The edit-options card renders for the editor...
            self.assertContains(response, reverse("chant-create", args=[source.id]))
            # ...but the superuser-only image-links entry is absent.
            self.assertNotContains(response, image_links_url)

    def test_csv_export_link_uses_response_filename(self) -> None:
        source = make_fake_source()
        response = self.client.get(reverse("source-detail", args=[source.id]))

        self.assertCsvExportLinkHasNoDownloadAttribute(
            response.content.decode("utf-8"), source.id
        )

    def test_context_chant_folios(self) -> None:
        # create a source and several chants in it
        source = make_fake_source()
        make_fake_chant(source=source, folio="001r")
        make_fake_chant(source=source, folio="001r")
        make_fake_chant(source=source, folio="001v")
        make_fake_chant(source=source, folio="001v")
        make_fake_chant(source=source, folio="002r")
        make_fake_chant(source=source, folio="002v")
        # request the page
        response = self.client.get(reverse("source-detail", args=[source.id]))
        # the element in "folios" should be unique and ordered in this way
        folios = response.context["folios"]
        self.assertEqual(list(folios), ["001r", "001v", "002r", "002v"])

    def test_context_sequence_folios(self) -> None:
        # create a sequence source and several sequences in it
        bower_segment = make_fake_segment(id=4064, name="Bower Sequence Database")
        source = make_fake_source(
            shelfmark="a sequence source", published=True, segment=[bower_segment]
        )
        make_fake_sequence(source=source, folio="001r")
        make_fake_sequence(source=source, folio="001r")
        make_fake_sequence(source=source, folio="001v")
        make_fake_sequence(source=source, folio="001v")
        make_fake_sequence(source=source, folio="002r")
        make_fake_sequence(source=source, folio="002v")
        # request the page
        response = self.client.get(reverse("source-detail", args=[source.id]))
        # the element in "folios" should be unique and ordered in this way
        folios = response.context["folios"]
        self.assertEqual(list(folios), ["001r", "001v", "002r", "002v"])
        # the folios should be ordered by the "folio" field
        self.assertEqual(folios.query.order_by, ("folio",))

    def test_context_sequences(self) -> None:
        # create a sequence source and several sequences in it
        source = make_fake_source(
            segment=[make_fake_segment(id=4064, name="Bower Sequence Database")],
            shelfmark="a sequence source",
            published=True,
        )
        sequence = make_fake_sequence(source=source)
        # request the page
        response = self.client.get(reverse("source-detail", args=[source.id]))
        # the sequence should be in the list of sequences
        self.assertIn(sequence, response.context["sequences"])
        # the list of sequences should be ordered by the "sequence" field
        self.assertEqual(response.context["sequences"].query.order_by, ("s_sequence",))

    def test_chant_list_link(self) -> None:
        cantus_segment = make_fake_segment(id=4063)
        cantus_source = make_fake_source(segment=[cantus_segment])
        # Add a chant so the source has content and link should appear
        make_fake_chant(source=cantus_source)
        chant_list_link = reverse("browse-chants", args=[cantus_source.id])

        cantus_source_response = self.client.get(
            reverse("source-detail", args=[cantus_source.id])
        )
        cantus_source_html = str(cantus_source_response.content)
        self.assertIn(chant_list_link, cantus_source_html)

        # Sources without chants should not show the link
        source_no_chants = make_fake_source(segment=[cantus_segment])
        no_chants_response = self.client.get(
            reverse("source-detail", args=[source_no_chants.id])
        )
        no_chants_html = str(no_chants_response.content)
        no_chants_link = reverse("browse-chants", args=[source_no_chants.id])
        self.assertNotIn(no_chants_link, no_chants_html)

    def test_json_response(self) -> None:
        source = make_fake_source()
        response = self.client.get(
            reverse(
                "source-detail",
                args=[source.id],
            ),
            headers={"Accept": "application/json"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/json")
        self.assertEqual(response.json()["source"]["id"], source.id)

    def test_provenance_notes_displayed(self) -> None:
        notes = "test_provenance_notes_value"
        source = make_fake_source(provenance_notes=notes)
        response = self.client.get(reverse("source-detail", args=[source.id]))
        html = response.content.decode("utf-8")
        self.assertIn("Provenance notes:", html)
        self.assertIn(notes, html)

    def test_provenance_notes_not_displayed_when_empty(self) -> None:
        source = make_fake_source(provenance_notes="")
        response = self.client.get(reverse("source-detail", args=[source.id]))
        html = response.content.decode("utf-8")
        self.assertNotIn("Provenance notes:", html)

    def test_notation_displayed_without_link(self) -> None:
        # Regression for #1995: clicking the notation link 500'd, so it was disabled.
        source = make_fake_source()
        notation = source.notation.first()
        response = self.client.get(reverse("source-detail", args=[source.id]))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode("utf-8")
        self.assertIn("Notation:", html)
        self.assertIn(notation.name, html)
        self.assertNotIn(reverse("notation-detail", args=[notation.id]), html)
        self.assertNotIn("(Bower)", html)

    def test_notation_bower_label(self) -> None:
        bower_segment = make_fake_segment(
            id=settings.BOWER_SEGMENT_ID, name="Bower Sequence Database"
        )
        source = make_fake_source(segment=[bower_segment])
        notation = source.notation.first()
        response = self.client.get(reverse("source-detail", args=[source.id]))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode("utf-8")
        self.assertIn("Notation (Bower):", html)
        self.assertIn(notation.name, html)
        self.assertNotIn(reverse("notation-detail", args=[notation.id]), html)

    def test_image_link_displayed_when_no_source_links(self) -> None:
        source = make_fake_source(image_link="https://example.com/images")
        response = self.client.get(reverse("source-detail", args=[source.id]))
        html = str(response.content)
        self.assertIn("https://example.com/images", html)
        self.assertIn("View images on external site", html)

    def test_image_link_hidden_when_external_images_source_link_exists(self) -> None:
        source = make_fake_source(image_link="https://example.com/images")
        SourceURL.objects.create(
            source=source,
            url="https://example.com/external",
            url_type=SourceURL.URLTypes.EXTERNAL_IMAGES,
        )
        response = self.client.get(reverse("source-detail", args=[source.id]))
        html = str(response.content)
        # The SourceURL supersedes the legacy field: its link renders and the
        # legacy image_link does not, so the gallery link appears exactly once.
        self.assertIn("https://example.com/external", html)
        self.assertNotIn("https://example.com/images", html)
        self.assertEqual(html.count("View images on external site"), 1)

    def test_external_images_branch_does_not_leak_template_comment(self) -> None:
        # Regression test: the EXTERNAL_IMAGES branch's explanatory comment must
        # use {% comment %}, not a multi-line {# #} — Django only strips {# #}
        # on a single line, so a multi-line one renders verbatim to the user.
        source = make_fake_source(image_link="")
        SourceURL.objects.create(
            source=source,
            url="https://example.com/external",
            url_type=SourceURL.URLTypes.EXTERNAL_IMAGES,
        )
        response = self.client.get(reverse("source-detail", args=[source.id]))
        html = response.content.decode("utf-8")
        self.assertIn("View images on external site", html)
        self.assertNotIn("Same label as the legacy", html)
        self.assertNotIn("{#", html)

    def test_image_link_displayed_when_only_non_image_source_link_exists(self) -> None:
        source = make_fake_source(image_link="https://example.com/images")
        SourceURL.objects.create(
            source=source,
            url="https://example.com/iiif/manifest.json",
            url_type=SourceURL.URLTypes.IIIF_MANIFEST,
        )
        response = self.client.get(reverse("source-detail", args=[source.id]))
        html = str(response.content)
        self.assertIn("https://example.com/images", html)
        self.assertIn("View images on external site", html)

    def test_image_link_not_displayed_when_empty(self) -> None:
        source = make_fake_source(image_link="")
        response = self.client.get(reverse("source-detail", args=[source.id]))
        html = str(response.content)
        self.assertNotIn("View images on external site", html)
        # The property is a template boolean; a blank image_link must not leak "" through.
        self.assertIs(source.show_legacy_image_link, False)

    def test_iiif_manifest_link_renders_viewer(self) -> None:
        # Guards the template's url_type comparison: if it stops matching
        # IIIF_MANIFEST, this link silently degrades to the generic {% else %}
        # branch instead of the Universal Viewer.
        source = make_fake_source(image_link="")
        SourceURL.objects.create(
            source=source,
            url="https://example.com/iiif/manifest.json",
            url_type=SourceURL.URLTypes.IIIF_MANIFEST,
        )
        response = self.client.get(reverse("source-detail", args=[source.id]))
        html = response.content.decode("utf-8")
        self.assertIn("viewer/uv.html", html)
        self.assertIn("#?manifest=https://example.com/iiif/manifest.json", html)
        self.assertIn("View in IIIF Viewer", html)
        # The generic branch renders the url_type display name instead.
        self.assertNotIn("IIIF Manifest</a>", html)

    def test_non_iiif_source_link_renders_generic_label(self) -> None:
        source = make_fake_source(image_link="")
        SourceURL.objects.create(
            source=source,
            url="https://example.com/catalogue/record",
            url_type=SourceURL.URLTypes.HOST_INSTITUTION_RECORD,
        )
        response = self.client.get(reverse("source-detail", args=[source.id]))
        html = response.content.decode("utf-8")
        self.assertIn("https://example.com/catalogue/record", html)
        self.assertIn("Host Institution Record", html)
        self.assertNotIn("viewer/uv.html", html)


class SourceInventoryViewTest(HTMLContentsTestMixin, SourcePermissionsTestCase):
    view_name = "source-inventory"

    def test_permissions(self) -> None:
        self._run_get_permissions_test()

    def test_url_and_templates(self):
        source = make_fake_source()
        make_fake_chant(source=source)
        response = self.client.get(reverse("source-inventory", args=[source.id]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "full_inventory.html")

    def test_no_chants_returns_404(self):
        # Test that sources without chants return 404
        source_no_chants = make_fake_source(published=True)
        response = self.client.get(
            reverse("source-inventory", args=[source_no_chants.id])
        )
        self.assertEqual(response.status_code, 404)

    def test_chant_source_queryset(self):
        chant_source = make_fake_source()
        chant = make_fake_chant(source=chant_source)
        response = self.client.get(reverse("source-inventory", args=[chant_source.id]))
        self.assertEqual(chant_source, response.context["source"])
        self.assertIn(chant, response.context["chants"])

    def test_sequence_source_queryset(self):
        seq_source = make_fake_source(
            segment=[make_fake_segment(id=4064, name="Clavis Sequentiarium")],
            shelfmark="a sequence source",
            published=True,
        )
        sequence = make_fake_sequence(source=seq_source)
        response = self.client.get(reverse("source-inventory", args=[seq_source.id]))
        self.assertEqual(seq_source, response.context["source"])
        self.assertIn(sequence, response.context["chants"])

    def test_shelfmark_column(self):
        shelfmark = "Sigl-01"
        source = make_fake_source(published=True, shelfmark=shelfmark)
        make_fake_chant(source=source)
        response = self.client.get(reverse("source-inventory", args=[source.id]))
        expected_html_substring = (
            f'<td title="{source.heading}">{source.short_heading}</td>'
        )
        self.assertContains(response, expected_html_substring, html=True)

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
        bower_segment = make_fake_segment(id=4064, name="Bower Sequence Database")
        source = make_fake_source(published=True, segment=[bower_segment])
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
        bower_segment = make_fake_segment(id=4064, name="Bower Sequence Database")
        source = make_fake_source(published=True, segment=[bower_segment])
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
        expected_html_substring: str = (
            f'<a href="https://differentiaedatabase.ca/differentia/{diff_id}" target="_blank">'
        )
        self.assertParsedContains(response, expected_html_substring)

    def test_redirect_with_source_parameter(self):
        cantus_segment = make_fake_segment(id=4063)
        source = make_fake_source(segment=[cantus_segment])
        source_id = source.id
        make_fake_chant(source=source)

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


class SourceBrowseChantsViewTest(CsvExportLinkTestMixin, SourcePermissionsTestCase):
    view_name = "browse-chants"

    def test_permissions(self) -> None:
        self.run_request_permissions_test(
            url=reverse(self.view_name, args=[self.sources["unassigned_source"].id]),
            get_allowed_users=["superuser", "global viewer"],
            post_allowed_users=["superuser"],
            test_name="Unassigned source",
        )
        self.run_request_permissions_test(
            url=reverse(self.view_name, args=[self.sources["user_assigned_source"].id]),
            get_allowed_users=["user", "superuser", "global viewer"],
            post_allowed_users=["user", "superuser"],
            test_name="User assigned source",
        )
        self.run_request_permissions_test(
            url=reverse(
                self.view_name, args=[self.sources["editor_assigned_source"].id]
            ),
            get_allowed_users=["editor", "superuser", "global viewer"],
            post_allowed_users=["editor", "superuser"],
            test_name="Editor assigned source",
        )

    def test_url_and_templates(self):
        cantus_segment = make_fake_segment(id=4063)
        source = make_fake_source(segment=[cantus_segment])
        make_fake_chant(source=source)
        response = self.client.get(reverse("browse-chants", args=[source.id]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "base.html")
        self.assertTemplateUsed(response, "browse_chants.html")

    def test_csv_export_link_uses_response_filename(self):
        cantus_segment = make_fake_segment(id=4063)
        source = make_fake_source(segment=[cantus_segment])
        make_fake_chant(source=source)
        response = self.client.get(reverse("browse-chants", args=[source.id]))

        self.assertCsvExportLinkHasNoDownloadAttribute(
            response.content.decode("utf-8"), source.id
        )

    def test_chant_rows_have_anchor_ids(self):
        # SourceEditChantsView.get_success_url redirects to `#chant-<pk>` after an
        # edit, so each row must carry the matching anchor or the user lands at
        # the top of the list instead of on the chant they edited (#1433).
        cantus_segment = make_fake_segment(id=4063)
        source = make_fake_source(segment=[cantus_segment])
        chant = make_fake_chant(source=source)
        response = self.client.get(reverse("browse-chants", args=[source.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'id="chant-{chant.id}"')

    def test_external_images_link_prefers_source_url(self):
        # This page renders a single images link and does not render
        # source_links, so it must follow the SourceURL that supersedes
        # image_link rather than showing the stale legacy URL.
        cantus_segment = make_fake_segment(id=4063)
        source = make_fake_source(
            segment=[cantus_segment], image_link="https://example.com/legacy-images"
        )
        make_fake_chant(source=source)
        SourceURL.objects.create(
            source=source,
            url="https://example.com/source-url-images",
            url_type=SourceURL.URLTypes.EXTERNAL_IMAGES,
        )
        response = self.client.get(reverse("browse-chants", args=[source.id]))
        html = response.content.decode("utf-8")
        self.assertIn("https://example.com/source-url-images", html)
        self.assertNotIn("https://example.com/legacy-images", html)

    def test_external_images_link_falls_back_to_legacy_field(self):
        cantus_segment = make_fake_segment(id=4063)
        source = make_fake_source(
            segment=[cantus_segment], image_link="https://example.com/legacy-images"
        )
        make_fake_chant(source=source)
        response = self.client.get(reverse("browse-chants", args=[source.id]))
        html = response.content.decode("utf-8")
        self.assertIn("https://example.com/legacy-images", html)
        self.assertIn("View images on external site", html)

    def test_visibility_by_segment(self):
        cantus_segment = make_fake_segment(id=4063)
        cantus_source = make_fake_source(segment=[cantus_segment], published=True)
        # Add a chant so the source has content
        make_fake_chant(source=cantus_source)
        response_1 = self.client.get(reverse("browse-chants", args=[cantus_source.id]))
        self.assertEqual(response_1.status_code, 200)

        # Sources without chants should return 404
        bower_segment = make_fake_segment(id=4064)
        bower_source = make_fake_source(segment=[bower_segment], published=True)
        response_1 = self.client.get(reverse("browse-chants", args=[bower_source.id]))
        self.assertEqual(response_1.status_code, 404)

    def test_non_cantus_segment_source_appears_in_dropdown(self):
        # A source outside the CantusDatabase segment must appear in the sources dropdown so it can be marked as selected.
        make_fake_segment(id=4063)
        other_segment = make_fake_segment(id=9999)
        non_cantus_source = make_fake_source(segment=[other_segment], published=True)
        make_fake_chant(source=non_cantus_source)
        response = self.client.get(
            reverse("browse-chants", args=[non_cantus_source.id])
        )
        self.assertEqual(response.status_code, 200)
        sources_in_context = response.context["sources"]
        self.assertIn(non_cantus_source, sources_in_context)

    def test_no_chants_returns_404(self):
        # Test that sources without chants return 404
        cantus_segment = make_fake_segment(id=4063)
        source_no_chants = make_fake_source(segment=[cantus_segment], published=True)
        response = self.client.get(reverse("browse-chants", args=[source_no_chants.id]))
        self.assertEqual(response.status_code, 404)

    def test_filter_by_source(self):
        cantus_segment = make_fake_segment(id=4063)
        source = make_fake_source(segment=[cantus_segment])
        another_source = make_fake_source(segment=[cantus_segment])
        chant_in_source = make_fake_chant(source=source)
        chant_in_another_source = make_fake_chant(source=another_source)
        response = self.client.get(reverse("browse-chants", args=[source.id]))
        chants = response.context["chants"]
        self.assertIn(chant_in_source, chants)
        self.assertNotIn(chant_in_another_source, chants)

    def test_filter_by_feast(self):
        cantus_segment = make_fake_segment(id=4063)
        source = make_fake_source(segment=[cantus_segment])
        feast = make_fake_feast()
        another_feast = make_fake_feast()
        chant_in_feast = make_fake_chant(source=source, feast=feast)
        chant_in_another_feast = make_fake_chant(source=source, feast=another_feast)
        response = self.client.get(
            reverse("browse-chants", args=[source.id]), {"feast": feast.id}
        )
        chants = response.context["chants"]
        self.assertIn(chant_in_feast, chants)
        self.assertNotIn(chant_in_another_feast, chants)

    def test_filter_by_genre(self):
        cantus_segment = make_fake_segment(id=4063)
        source = make_fake_source(segment=[cantus_segment])
        genre = make_fake_genre()
        another_genre = make_fake_genre()
        chant_in_genre = make_fake_chant(source=source, genre=genre)
        chant_in_another_genre = make_fake_chant(source=source, genre=another_genre)
        response = self.client.get(
            reverse("browse-chants", args=[source.id]), {"genre": genre.id}
        )
        chants = response.context["chants"]
        self.assertIn(chant_in_genre, chants)
        self.assertNotIn(chant_in_another_genre, chants)

    def test_filter_by_folio(self):
        cantus_segment = make_fake_segment(id=4063)
        source = make_fake_source(segment=[cantus_segment])
        chant_on_folio = make_fake_chant(source=source, folio="001r")
        chant_on_another_folio = make_fake_chant(source=source, folio="002r")
        response = self.client.get(
            reverse("browse-chants", args=[source.id]), {"folio": "001r"}
        )
        chants = response.context["chants"]
        self.assertIn(chant_on_folio, chants)
        self.assertNotIn(chant_on_another_folio, chants)

    def test_search_full_text(self):
        cantus_segment = make_fake_segment(id=4063)
        source = make_fake_source(segment=[cantus_segment])
        chant = make_fake_chant(source=source, manuscript_full_text=faker.sentence())
        search_term = get_random_search_term(chant.manuscript_full_text)
        response = self.client.get(
            reverse("browse-chants", args=[source.id]), {"search_text": search_term}
        )
        self.assertIn(chant, response.context["chants"])

    def test_search_incipit(self):
        cantus_segment = make_fake_segment(id=4063)
        source = make_fake_source(segment=[cantus_segment])
        chant = make_fake_chant(
            source=source,
            manuscript_full_text_std_spelling=faker.sentence(),
        )
        search_term = get_random_search_term(chant.incipit)
        response = self.client.get(
            reverse("browse-chants", args=[source.id]), {"search_text": search_term}
        )
        self.assertIn(chant, response.context["chants"])

    def test_search_full_text_std_spelling(self):
        cantus_segment = make_fake_segment(id=4063)
        source = make_fake_source(segment=[cantus_segment])
        chant = make_fake_chant(
            source=source,
            manuscript_full_text_std_spelling=faker.sentence(),
        )
        search_term = get_random_search_term(chant.manuscript_full_text_std_spelling)
        response = self.client.get(
            reverse("browse-chants", args=[source.id]), {"search_text": search_term}
        )
        self.assertIn(chant, response.context["chants"])

    def test_search_proofread(self):
        cantus_segment = make_fake_segment(id=4063)
        source = make_fake_source(segment=[cantus_segment])
        chant_std_proofread = make_fake_chant(
            source=source,
            manuscript_full_text_std_proofread=True,
            manuscript_full_text_proofread=False,
            volpiano_proofread=False,
        )
        chant_ft_proofread = make_fake_chant(
            source=source,
            manuscript_full_text_std_proofread=False,
            manuscript_full_text_proofread=True,
            volpiano_proofread=False,
        )
        chant_volpiano_proofread = make_fake_chant(
            source=source,
            manuscript_full_text_std_proofread=False,
            manuscript_full_text_proofread=False,
            volpiano_proofread=True,
        )
        response = self.client.get(
            reverse("browse-chants", args=[source.id]),
        )
        self.assertIn(chant_std_proofread, response.context["chants"])
        self.assertIn(chant_ft_proofread, response.context["chants"])
        self.assertIn(chant_volpiano_proofread, response.context["chants"])

        response = self.client.get(
            reverse("browse-chants", args=[source.id]),
            {"manuscript_full_text_std_proofread": True},
        )
        self.assertIn(chant_std_proofread, response.context["chants"])
        self.assertNotIn(chant_ft_proofread, response.context["chants"])
        self.assertNotIn(chant_volpiano_proofread, response.context["chants"])

        response = self.client.get(
            reverse("browse-chants", args=[source.id]),
            {"manuscript_full_text_std_proofread": False},
        )
        self.assertNotIn(chant_std_proofread, response.context["chants"])
        self.assertIn(chant_ft_proofread, response.context["chants"])
        self.assertIn(chant_volpiano_proofread, response.context["chants"])

        response = self.client.get(
            reverse("browse-chants", args=[source.id]),
            {"manuscript_full_text_proofread": True},
        )
        self.assertNotIn(chant_std_proofread, response.context["chants"])
        self.assertIn(chant_ft_proofread, response.context["chants"])
        self.assertNotIn(chant_volpiano_proofread, response.context["chants"])

        response = self.client.get(
            reverse("browse-chants", args=[source.id]),
            {"manuscript_full_text_proofread": False},
        )
        self.assertIn(chant_std_proofread, response.context["chants"])
        self.assertNotIn(chant_ft_proofread, response.context["chants"])
        self.assertIn(chant_volpiano_proofread, response.context["chants"])

        response = self.client.get(
            reverse("browse-chants", args=[source.id]),
            {"volpiano_proofread": True},
        )
        self.assertNotIn(chant_std_proofread, response.context["chants"])
        self.assertNotIn(chant_ft_proofread, response.context["chants"])
        self.assertIn(chant_volpiano_proofread, response.context["chants"])

        response = self.client.get(
            reverse("browse-chants", args=[source.id]),
            {"volpiano_proofread": False},
        )
        self.assertIn(chant_std_proofread, response.context["chants"])
        self.assertIn(chant_ft_proofread, response.context["chants"])
        self.assertNotIn(chant_volpiano_proofread, response.context["chants"])

    def test_context_source(self):
        cantus_segment = make_fake_segment(id=4063)
        source = make_fake_source(segment=[cantus_segment])
        make_fake_chant(source=source)
        response = self.client.get(reverse("browse-chants", args=[source.id]))
        self.assertEqual(source, response.context["source"])

    def test_context_folios(self):
        cantus_segment = make_fake_segment(id=4063)
        source = make_fake_source(segment=[cantus_segment])
        make_fake_chant(source=source, folio="001r")
        make_fake_chant(source=source, folio="001r")
        make_fake_chant(source=source, folio="001v")
        make_fake_chant(source=source, folio="001v")
        make_fake_chant(source=source, folio="002r")
        make_fake_chant(source=source, folio="002v")
        response = self.client.get(reverse("browse-chants", args=[source.id]))
        # the element in "folios" should be unique and ordered in this way
        folios = response.context["folios"]
        self.assertEqual(list(folios), ["001r", "001v", "002r", "002v"])

    def test_redirect_with_source_parameter(self):
        cantus_segment = make_fake_segment(id=4063)
        source = make_fake_source(segment=[cantus_segment])
        make_fake_chant(source=source)
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


class SourceListViewTest(CustomAccessTestMixin, TestCase):

    def test_url_and_templates(self):
        response = self.client.get(reverse("source-list"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "base.html")
        self.assertTemplateUsed(response, "source_lists/source_list.html")

    def test_images_column_prefers_source_url(self):
        source = make_fake_source(
            published=True, image_link="https://example.com/legacy-images"
        )
        SourceURL.objects.create(
            source=source,
            url="https://example.com/source-url-images",
            url_type=SourceURL.URLTypes.EXTERNAL_IMAGES,
        )
        response = self.client.get(reverse("source-list"))
        html = response.content.decode("utf-8")
        self.assertIn("https://example.com/source-url-images", html)
        self.assertNotIn("https://example.com/legacy-images", html)

    def test_images_column_does_not_query_per_source(self):
        # The Images column calls Source.external_images_url on every row, so
        # the list queryset prefetches source_links. Without it this page costs
        # one extra query per source, up to paginate_by = 100.
        for _ in range(5):
            source = make_fake_source(published=True)
            SourceURL.objects.create(
                source=source,
                url="https://example.com/source-url-images",
                url_type=SourceURL.URLTypes.EXTERNAL_IMAGES,
            )
        with CaptureQueriesContext(connection) as ctx:
            self.client.get(reverse("source-list"))
        source_link_queries = [
            q for q in ctx.captured_queries if "main_app_sourceurl" in q["sql"]
        ]
        self.assertEqual(len(source_link_queries), 1, source_link_queries)

    def test_provenances_and_date_range_in_context(self):
        """`provenances` are options in the selector; `date_range_min`/`date_range_max`
        bound the year-range slider."""
        provenance = make_fake_provenance()
        make_fake_century(name="10th century")
        make_fake_century(name="15th century")
        response = self.client.get(reverse("source-list"))
        provenances = response.context["provenances"]
        self.assertIn({"id": provenance.id, "name": provenance.name}, provenances)
        self.assertEqual(response.context["date_range_min"], 900)
        self.assertEqual(response.context["date_range_max"], 1500)

    def test_permissions(self) -> None:
        published_source = make_fake_source(published=True)
        editor_assigned_source = make_fake_source(
            published=False, current_editors=[self.users["editor"]]
        )
        user_assigned_source = make_fake_source(
            published=False, current_editors=[self.users["user"]]
        )
        unassigned_source = make_fake_source(published=False)
        with self.subTest("Visible to anonymous user"):
            resp = self.client.get(reverse("source-list"))
            sources = resp.context["sources"]
            self.assertCountEqual(sources, [published_source])
        with self.subTest("Visible to superuser"):
            self.client.force_login(self.users["superuser"])
            resp = self.client.get(reverse("source-list"))
            sources = resp.context["sources"]
            self.assertCountEqual(
                sources,
                [
                    published_source,
                    editor_assigned_source,
                    user_assigned_source,
                    unassigned_source,
                ],
            )
        with self.subTest("Visible to global viewer"):
            self.client.force_login(self.users["global viewer"])
            resp = self.client.get(reverse("source-list"))
            sources = resp.context["sources"]
            self.assertCountEqual(
                sources,
                [
                    published_source,
                    editor_assigned_source,
                    user_assigned_source,
                    unassigned_source,
                ],
            )
        with self.subTest("Visible to editor"):
            self.client.force_login(self.users["editor"])
            resp = self.client.get(reverse("source-list"))
            sources = resp.context["sources"]
            self.assertCountEqual(sources, [published_source, editor_assigned_source])
        with self.subTest("Visible to user"):
            self.client.force_login(self.users["user"])
            resp = self.client.get(reverse("source-list"))
            sources = resp.context["sources"]
            self.assertCountEqual(sources, [published_source, user_assigned_source])
        with self.subTest("Visible to expired global viewer"):
            self.client.force_login(self.users["expired global viewer"])
            resp = self.client.get(reverse("source-list"))
            sources = resp.context["sources"]
            self.assertCountEqual(sources, [published_source])

    def test_filter_by_segment(self):
        """The source list can be filtered by `segment`, `country`, `provenance`, `century`, and `full_source`"""
        cantus_segment = make_fake_segment(name="cantus")
        clavis_segment = make_fake_segment(name="clavis")
        chant_source = make_fake_source(
            segment=[cantus_segment], shelfmark="chant source", published=True
        )
        seq_source = make_fake_source(
            segment=[clavis_segment], shelfmark="sequence source", published=True
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

    def test_filter_by_date_range(self):
        ninth_century = make_fake_century(name="09th century")
        tenth_century = make_fake_century(name="10th century")
        fifteenth_century = make_fake_century(name="15th century")

        ninth_century_source = make_fake_source(published=True, shelfmark="9th")
        ninth_century_source.century.set([ninth_century])

        tenth_century_source = make_fake_source(published=True, shelfmark="10th")
        tenth_century_source.century.set([tenth_century])

        fifteenth_century_source = make_fake_source(published=True, shelfmark="15th")
        fifteenth_century_source.century.set([fifteenth_century])

        # Range 800-999 overlaps 9th and 10th centuries; not 15th
        response = self.client.get(
            reverse("source-list"), {"dateStart": 800, "dateEnd": 999}
        )
        sources = response.context["sources"]
        self.assertIn(ninth_century_source, sources)
        self.assertIn(tenth_century_source, sources)
        self.assertNotIn(fifteenth_century_source, sources)

        # Only dateStart: sources whose century max_date >= 1400
        response = self.client.get(reverse("source-list"), {"dateStart": 1400})
        sources = response.context["sources"]
        self.assertNotIn(ninth_century_source, sources)
        self.assertNotIn(tenth_century_source, sources)
        self.assertIn(fifteenth_century_source, sources)

        # Only dateEnd: sources whose century min_date <= 999
        response = self.client.get(reverse("source-list"), {"dateEnd": 999})
        sources = response.context["sources"]
        self.assertIn(ninth_century_source, sources)
        self.assertIn(tenth_century_source, sources)
        self.assertNotIn(fifteenth_century_source, sources)

    def test_date_range_does_not_hide_sources_without_century(self) -> None:
        """A source with no century assigned must not disappear from the list
        just because the date-range form was submitted at its default (full)
        span -- it should only be filtered out when the range is actually
        narrowed. Regression test for undated sources vanishing from search.
        """
        # Dated centuries establish the outer slider bounds: 800-1499, which
        # the view rounds/clips to a default range of 800-1500.
        make_fake_century(name="09th century")
        tenth_century = make_fake_century(name="10th century")
        make_fake_century(name="15th century")

        undated_source = make_fake_source(published=True, shelfmark="no century")
        undated_source.century.set([])
        tenth_century_source = make_fake_source(published=True, shelfmark="10th")
        tenth_century_source.century.set([tenth_century])

        with self.subTest("No date params: undated source is shown"):
            response = self.client.get(reverse("source-list"))
            self.assertIn(undated_source, response.context["sources"])

        with self.subTest("Default full-range params: undated source is shown"):
            response = self.client.get(
                reverse("source-list"), {"dateStart": 800, "dateEnd": 1500}
            )
            self.assertIn(undated_source, response.context["sources"])

        with self.subTest("Range beyond the bounds: undated source is shown"):
            response = self.client.get(
                reverse("source-list"), {"dateStart": 600, "dateEnd": 3000}
            )
            self.assertIn(undated_source, response.context["sources"])

        with self.subTest("Genuine narrowing: undated source is filtered out"):
            response = self.client.get(
                reverse("source-list"), {"dateStart": 900, "dateEnd": 999}
            )
            sources = response.context["sources"]
            self.assertNotIn(undated_source, sources)
            self.assertIn(tenth_century_source, sources)

    def test_ccdb_browse_date_range_does_not_hide_sources_without_century(
        self,
    ) -> None:
        """`CcdbBrowseView` reuses `SourceListView`'s date-range filtering
        unchanged, so it must exhibit the same undated-source regression
        fix as the plain source list: shown at the default (full) range,
        filtered out only once the range is genuinely narrowed.
        """
        ccdb_segment = make_fake_segment(id=settings.CCDB_SEGMENT_ID)
        make_fake_century(name="09th century")
        tenth_century = make_fake_century(name="10th century")
        make_fake_century(name="15th century")

        undated_source = make_fake_source(
            segment=[ccdb_segment], published=True, shelfmark="no century"
        )
        undated_source.century.set([])
        tenth_century_source = make_fake_source(
            segment=[ccdb_segment], published=True, shelfmark="10th"
        )
        tenth_century_source.century.set([tenth_century])

        with self.subTest("No date params: undated source is shown"):
            response = self.client.get(reverse("ccdb-browse"))
            self.assertIn(undated_source, response.context["sources"])

        with self.subTest("Default full-range params: undated source is shown"):
            response = self.client.get(
                reverse("ccdb-browse"), {"dateStart": 800, "dateEnd": 1500}
            )
            self.assertIn(undated_source, response.context["sources"])

        with self.subTest("Genuine narrowing: undated source is filtered out"):
            response = self.client.get(
                reverse("ccdb-browse"), {"dateStart": 900, "dateEnd": 999}
            )
            sources = response.context["sources"]
            self.assertNotIn(undated_source, sources)
            self.assertIn(tenth_century_source, sources)

    def test_search_by_identifier_does_not_hide_undated_source(self) -> None:
        """Regression test for an undated source (e.g. Otto Ege MS 22)
        disappearing from an identifier search. The source list form submits
        the date-range slider's default (full) bounds alongside any search
        term, so a general/identifier search must not be affected by that.
        """
        make_fake_century(name="09th century")
        make_fake_century(name="15th century")

        undated_source = make_fake_source(published=True, shelfmark="Otto Ege MS 22")
        undated_source.century.set([])
        SourceIdentifier.objects.create(
            source=undated_source,
            identifier="Ege-22",
            type=SourceIdentifier.OTHER,
        )

        response = self.client.get(
            reverse("source-list"),
            {"general": "Ege-22", "dateStart": 800, "dateEnd": 1500},
        )
        self.assertIn(undated_source, response.context["sources"])

    def test_advanced_search_active_reflects_date_range_narrowing(self) -> None:
        """`advanced_search_active` controls whether the advanced-search
        panel opens by default; it must not flip on just because the
        date-range slider submits its default (full) bounds.
        """
        make_fake_century(name="09th century")
        make_fake_century(name="15th century")

        with self.subTest("No params: advanced search not active"):
            response = self.client.get(reverse("source-list"))
            self.assertFalse(response.context["advanced_search_active"])

        with self.subTest("Default full-range params: advanced search not active"):
            response = self.client.get(
                reverse("source-list"), {"dateStart": 800, "dateEnd": 1500}
            )
            self.assertFalse(response.context["advanced_search_active"])

        with self.subTest("Narrowed range: advanced search active"):
            response = self.client.get(
                reverse("source-list"), {"dateStart": 900, "dateEnd": 999}
            )
            self.assertTrue(response.context["advanced_search_active"])

    def test_filter_by_full_source(self) -> None:
        full_source = make_fake_source(
            source_completeness=Source.SourceCompletenessChoices.FULL_SOURCE,
            published=True,
            shelfmark="full source",
        )
        fragment = make_fake_source(
            source_completeness=Source.SourceCompletenessChoices.FRAGMENT,
            published=True,
            shelfmark="fragment",
        )
        reconstruction = make_fake_source(
            source_completeness=Source.SourceCompletenessChoices.RECONSTRUCTION,
            published=True,
            shelfmark="reconstruction",
        )
        fragmented = make_fake_source(
            source_completeness=Source.SourceCompletenessChoices.FRAGMENTED,
            published=True,
            shelfmark="fragmented",
        )

        with self.subTest("Display all sources: No query params"):
            response = self.client.get(reverse("source-list"))
            sources = response.context["sources"]
            self.assertIn(full_source, sources)
            self.assertIn(fragment, sources)
            self.assertIn(reconstruction, sources)
            self.assertIn(fragmented, sources)

        with self.subTest("Display all sources: All sourceCompleteness params"):
            response = self.client.get(
                reverse("source-list"),
                {"sourceCompleteness": Source.SourceCompletenessChoices.values},
            )
            sources = response.context["sources"]
            self.assertIn(full_source, sources)
            self.assertIn(fragment, sources)
            self.assertIn(reconstruction, sources)
            self.assertIn(fragmented, sources)

        with self.subTest("Display full sources only"):
            response = self.client.get(
                reverse("source-list"),
                {"sourceCompleteness": Source.SourceCompletenessChoices.FULL_SOURCE},
            )
            sources = response.context["sources"]
            self.assertIn(full_source, sources)
            self.assertNotIn(fragment, sources)
            self.assertNotIn(reconstruction, sources)
            self.assertNotIn(fragmented, sources)

        with self.subTest("Display fragments"):
            response = self.client.get(
                reverse("source-list"),
                {"sourceCompleteness": Source.SourceCompletenessChoices.FRAGMENT},
            )
            sources = response.context["sources"]
            self.assertNotIn(full_source, sources)
            self.assertIn(fragment, sources)
            self.assertNotIn(reconstruction, sources)
            self.assertNotIn(fragmented, sources)

        with self.subTest("Display fragmented sources"):
            response = self.client.get(
                reverse("source-list"),
                {"sourceCompleteness": Source.SourceCompletenessChoices.FRAGMENTED},
            )
            sources = response.context["sources"]
            self.assertNotIn(full_source, sources)
            self.assertNotIn(fragment, sources)
            self.assertNotIn(reconstruction, sources)
            self.assertIn(fragmented, sources)

        with self.subTest(
            "Display multiple source types: fragmented and reconstructions"
        ):
            response = self.client.get(
                reverse("source-list"),
                {
                    "sourceCompleteness": [
                        Source.SourceCompletenessChoices.FRAGMENTED,
                        Source.SourceCompletenessChoices.RECONSTRUCTION,
                    ]
                },
            )
            sources = response.context["sources"]
            self.assertNotIn(full_source, sources)
            self.assertNotIn(fragment, sources)
            self.assertIn(reconstruction, sources)
            self.assertIn(fragmented, sources)

    def test_filter_by_production_method(self) -> None:
        manuscript_source = make_fake_source(
            production_method=Source.ProductionMethodChoices.MANUSCRIPT, published=True
        )
        print_source = make_fake_source(
            production_method=Source.ProductionMethodChoices.PRINT, published=True
        )
        with self.subTest("All sources"):
            response = self.client.get(reverse("source-list"))
            sources = response.context["sources"]
            self.assertIn(manuscript_source, sources)
            self.assertIn(print_source, sources)
        with self.subTest("Manuscript sources only"):
            response = self.client.get(
                reverse("source-list"),
                {"prodMethod": Source.ProductionMethodChoices.MANUSCRIPT},
            )
            sources = response.context["sources"]
            self.assertIn(manuscript_source, sources)
            self.assertNotIn(print_source, sources)
        with self.subTest("Print sources only"):
            response = self.client.get(
                reverse("source-list"),
                {"prodMethod": Source.ProductionMethodChoices.PRINT},
            )
            sources = response.context["sources"]
            self.assertNotIn(manuscript_source, sources)
            self.assertIn(print_source, sources)

    def test_filter_by_inventoried(self) -> None:
        inventoried_source = make_fake_source(number_of_chants=5, published=True)
        zero_chants_source = make_fake_source(number_of_chants=0, published=True)
        null_chants_source = make_fake_source(number_of_chants=None, published=True)

        with self.subTest("No parameter: all sources shown"):
            response = self.client.get(reverse("source-list"))
            sources = response.context["sources"]
            self.assertIn(inventoried_source, sources)
            self.assertIn(zero_chants_source, sources)
            self.assertIn(null_chants_source, sources)

        with self.subTest("inventoried=all: all sources shown"):
            response = self.client.get(reverse("source-list"), {"inventoried": "all"})
            sources = response.context["sources"]
            self.assertIn(inventoried_source, sources)
            self.assertIn(zero_chants_source, sources)
            self.assertIn(null_chants_source, sources)

        with self.subTest(
            "inventoried=inventoried: only sources with chants are shown"
        ):
            response = self.client.get(
                reverse("source-list"), {"inventoried": "inventoried"}
            )
            sources = response.context["sources"]
            self.assertIn(inventoried_source, sources)
            self.assertNotIn(zero_chants_source, sources)
            self.assertNotIn(null_chants_source, sources)

        with self.subTest(
            "inventoried=nonInventoried: sources with chants are excluded"
        ):
            response = self.client.get(
                reverse("source-list"), {"inventoried": "nonInventoried"}
            )
            sources = response.context["sources"]
            self.assertNotIn(inventoried_source, sources)
            self.assertIn(zero_chants_source, sources)
            self.assertIn(null_chants_source, sources)

    def test_search_by_title(self) -> None:
        """The "general search" field searches in `title`, `shelfmark`, `description`, and `summary`"""
        source = make_fake_source(
            shelfmark=faker.sentence(),
            published=True,
        )
        search_term = get_random_search_term(source.shelfmark)

        # Partial matching
        response = self.client.get(reverse("source-list"), {"general": search_term})
        self.assertIn(source, response.context["sources"])

        # Exact matching
        response = self.client.get(
            reverse("source-list"), {"general": f'"{source.shelfmark}"'}
        )
        self.assertIn(source, response.context["sources"])

        # Test that postgres searches unaccented version of title
        unaccented_title = source.shelfmark
        accented_title = add_accents_to_string(unaccented_title)
        source.title = accented_title
        source.save()
        response = self.client.get(
            reverse("source-list"), {"general": f'"{source.title}"'}
        )
        self.assertIn(source, response.context["sources"])

    def test_search_by_shelfmark(self) -> None:
        hinst = make_fake_institution(name="Fake Institution", siglum="FA-Ke")
        source = make_fake_source(
            published=True, shelfmark="title", holding_institution=hinst
        )
        search_term = get_random_search_term(source.shelfmark)

        # Partial matching
        response = self.client.get(reverse("source-list"), {"general": search_term})
        self.assertIn(source, response.context["sources"])

        # Exact matching
        response = self.client.get(
            reverse("source-list"), {"general": f'"{source.shelfmark}"'}
        )
        self.assertIn(source, response.context["sources"])

        # Test that postgres searches unaccented version of shelfmark
        unaccented_siglum = source.shelfmark
        accented_siglum = add_accents_to_string(unaccented_siglum)
        source.siglum = accented_siglum
        source.save()
        response = self.client.get(
            reverse("source-list"), {"general": f'"{source.siglum}"'}
        )
        self.assertIn(source, response.context["sources"])

    def test_search_by_description(self) -> None:
        source = make_fake_source(
            description=faker.sentence(),
            published=True,
            shelfmark="title",
        )
        search_term = get_random_search_term(source.description)

        # Partial matching
        response = self.client.get(reverse("source-list"), {"general": search_term})
        self.assertIn(source, response.context["sources"])

        # Exact matching
        response = self.client.get(
            reverse("source-list"), {"general": f'"{source.description}"'}
        )
        self.assertIn(source, response.context["sources"])

        # Test that postgres searches unaccented version of description
        unaccented_description = source.description
        accented_description = add_accents_to_string(unaccented_description)
        source.description = accented_description
        source.save()
        response = self.client.get(
            reverse("source-list"), {"general": f'"{source.description}"'}
        )
        self.assertIn(source, response.context["sources"])

    def test_search_by_summary(self) -> None:
        source = make_fake_source(
            summary=faker.sentence(),
            published=True,
            shelfmark="title",
        )
        search_term = get_random_search_term(source.summary)

        # Partial matching
        response = self.client.get(reverse("source-list"), {"general": search_term})
        self.assertIn(source, response.context["sources"])

        # Exact matching
        response = self.client.get(
            reverse("source-list"), {"general": f'"{source.summary}"'}
        )
        self.assertIn(source, response.context["sources"])

        # Test that postgres searches unaccented version of summary
        unaccented_summary = source.summary
        accented_summary = add_accents_to_string(unaccented_summary)
        source.summary = accented_summary
        source.save()
        response = self.client.get(
            reverse("source-list"), {"general": f'"{source.summary}"'}
        )
        self.assertIn(source, response.context["sources"])

    def test_search_by_indexing_notes(self) -> None:
        """The "indexing notes" field searches in `indexing_notes` and indexer/editor related fields"""
        source = make_fake_source(
            indexing_notes=faker.sentence(),
            published=True,
            shelfmark="title",
        )
        search_term = get_random_search_term(source.indexing_notes)

        # Partial matching
        response = self.client.get(reverse("source-list"), {"indexing": search_term})
        self.assertIn(source, response.context["sources"])

        # Exact matching
        response = self.client.get(
            reverse("source-list"), {"indexing": f'"{source.indexing_notes}"'}
        )
        self.assertIn(source, response.context["sources"])

        # Test that postgres searches unaccented version of indexing_notes
        unaccented_indexing_notes = source.indexing_notes
        accented_indexing_notes = add_accents_to_string(unaccented_indexing_notes)
        source.indexing_notes = accented_indexing_notes
        source.save()
        response = self.client.get(
            reverse("source-list"), {"indexing": f'"{source.indexing_notes}"'}
        )
        self.assertIn(source, response.context["sources"])

    def test_search_by_name(self) -> None:
        source = make_fake_source(
            name=faker.sentence(), published=True, shelfmark="title"
        )
        search_term = get_random_search_term(source.name)

        # Partial matching
        response = self.client.get(reverse("source-list"), {"general": search_term})
        self.assertIn(source, response.context["sources"])

        # Exact matching
        response = self.client.get(
            reverse("source-list"), {"general": f'"{source.name}"'}
        )
        self.assertIn(source, response.context["sources"])

    def test_search_by_provenance_and_trailing_punctuation(self) -> None:
        provenance = make_fake_provenance()
        provenance.name = "Kremsmünster"
        provenance.save()
        source = make_fake_source(
            provenance=provenance,
            published=True,
            shelfmark="title",
        )

        for term in ["Kremsmünster", "Kremsmünster,"]:
            with self.subTest(term=term):
                response = self.client.get(reverse("source-list"), {"general": term})
                self.assertIn(source, response.context["sources"])

    def test_search_by_identifier_with_colon_and_trailing_punctuation(self) -> None:
        source = make_fake_source(
            published=True,
            shelfmark="title",
            dact_id="D:06e4d",
            fragmentarium_id="F:01a2b",
        )
        SourceIdentifier.objects.create(
            source=source,
            identifier="ID:123",
            type=SourceIdentifier.OTHER,
        )

        for term in ["D:06e4d", "D:06e4d,", "F:01a2b", "ID:123", "ID:123,"]:
            with self.subTest(term=term):
                response = self.client.get(reverse("source-list"), {"general": term})
                self.assertIn(source, response.context["sources"])

    def test_ordering(self) -> None:
        """
        Order is currently available by country, city + institution name (parameter:
        "city_institution"), and siglum + shelfmark. Siglum + shelfmark is the default.
        """
        sources = []
        # Add a source from a private collector
        private_collector = make_fake_institution(is_private_collector=True)
        sources.append(make_fake_source(holding_institution=private_collector))
        # Add a source with no holding institution
        sources.append(make_fake_source(holding_institution=None))
        # Create a bunch of other sources
        for _ in range(10):
            inst = make_fake_institution()
            sources.append(make_fake_source(holding_institution=inst))
        # Make sure we have a source with the same country but different holding
        # institution than our other sources.
        sources.append(
            make_fake_source(
                holding_institution=make_fake_institution(country=inst.country)
            )
        )
        # Make sure we have a source with the same institution as another source
        sources.append(make_fake_source(holding_institution=inst))
        # Default ordering is by siglum and shelfmark, ascending
        with self.subTest("Default ordering"):
            response = self.client.get(reverse("source-list"))
            response_sources = response.context["sources"]
            expected_source_order = sorted(
                sources,
                key=lambda source: (
                    source.holding_institution is None
                    or source.holding_institution.is_private_collector,
                    (
                        source.holding_institution.siglum
                        if source.holding_institution
                        and not source.holding_institution.is_private_collector
                        else ""
                    ),
                    source.shelfmark,
                ),
            )
            self.assertEqual(list(expected_source_order), list(response_sources))
            response_reverse = self.client.get(reverse("source-list"), {"sort": "desc"})
            response_sources_reverse = response_reverse.context["sources"]
            self.assertEqual(
                list(reversed(expected_source_order)), list(response_sources_reverse)
            )
        with self.subTest("Order by country"):
            response = self.client.get(reverse("source-list"), {"order": "country"})
            response_sources = response.context["sources"]
            expected_source_order = sorted(
                sources,
                key=lambda source: (
                    source.holding_institution is None,
                    (
                        source.holding_institution.country
                        if source.holding_institution
                        else ""
                    ),
                    (
                        (
                            source.holding_institution.siglum is None,
                            source.holding_institution.siglum or "",
                        )
                        if source.holding_institution
                        else (True, "")
                    ),
                    source.shelfmark,
                    source.pk,
                ),
            )
            self.assertEqual(list(expected_source_order), list(response_sources))
            response_reverse = self.client.get(
                reverse("source-list"), {"order": "country", "sort": "desc"}
            )
            response_sources_reverse = response_reverse.context["sources"]
            self.assertEqual(
                list(reversed(expected_source_order)), list(response_sources_reverse)
            )
        with self.subTest("Order by city and institution name"):
            response = self.client.get(
                reverse("source-list"), {"order": "city_institution"}
            )
            response_sources = response.context["sources"]
            expected_source_order = sorted(
                sources,
                key=lambda source: (
                    source.holding_institution is None,
                    (
                        source.holding_institution.city
                        if source.holding_institution
                        else ""
                    ),
                    (
                        source.holding_institution.name
                        if source.holding_institution
                        else ""
                    ),
                    (
                        source.holding_institution.siglum
                        if source.holding_institution
                        and source.holding_institution.is_private_collector
                        else ""
                    ),
                    source.shelfmark,
                ),
            )
            self.assertEqual(list(expected_source_order), list(response_sources))
            response_reverse = self.client.get(
                reverse("source-list"), {"order": "city_institution", "sort": "desc"}
            )
            response_sources_reverse = response_reverse.context["sources"]
            self.assertEqual(
                list(reversed(expected_source_order)), list(response_sources_reverse)
            )

    def test_pagination(self):
        paginate_by = SourceListView.paginate_by
        full_pages = 2
        for _ in range(paginate_by * full_pages):
            make_fake_source(published=True)

        for page_num in range(1, full_pages + 1):
            response = self.client.get(reverse("source-list"), {"page": page_num})
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.context["is_paginated"])
            self.assertEqual(len(response.context["sources"]), paginate_by)

        random.seed(0)
        overflow = random.randint(1, paginate_by - 1)
        for _ in range(overflow):
            make_fake_source(published=True)

        response = self.client.get(reverse("source-list"), {"page": full_pages + 1})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["sources"]), overflow)

        response = self.client.get(reverse("source-list"), {"page": "last"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["sources"]), overflow)

        for invalid_page in [-1, 0, "lst", full_pages + 2]:
            response = self.client.get(reverse("source-list"), {"page": invalid_page})
            self.assertEqual(response.status_code, 404)


class SourceAddImageLinksViewTest(CustomAccessTestMixin, TestCase):
    source: Source
    default_user = "superuser"

    @classmethod
    def setUpTestData(cls) -> None:
        super().setUpTestData()
        cls.source = make_fake_source(published=True)
        for folio in ["001r", "001v", "003", "004A"]:
            make_fake_chant(source=cls.source, folio=folio, image_link=None)
        # Make a second chant for one of the folios, with an existing image link.
        # We'll update this image_link in the process.
        make_fake_chant(
            source=cls.source, folio="001v", image_link="https://i-already-exist.com"
        )
        # Make a final chant for a different folio with an existing image link. We
        # won't update this image_link in the process.
        make_fake_chant(
            source=cls.source, folio="004B", image_link="https://i-already-exist.com/2"
        )

    def test_permissions(self) -> None:
        self.run_request_permissions_test(
            reverse("source-add-image-links", args=[self.source.id]),
            get_allowed_users=["superuser"],
            post_allowed_users=["superuser"],
            test_name="Any source",
        )

    def test_form(self) -> None:
        with self.subTest("Test form fields"):
            response = self.client.get(
                reverse("source-add-image-links", args=[self.source.id])
            )
            self.assertEqual(response.status_code, 200)
            self.assertTemplateUsed(response, "source_add_image_links.html")
            form = response.context["form"]
            self.assertListEqual(
                list(form.fields.keys()), ["001r", "001v", "003", "004A", "004B"]
            )
        with self.subTest("Test form submission"):
            response = self.client.post(
                reverse("source-add-image-links", args=[self.source.id]),
                {
                    "001r": "https://example.com/001r",
                    "001v": "https://example.com/001v",
                    "004A": "https://example.com/004A",
                },
            )
            self.assertRedirects(
                response,
                reverse("source-detail", args=[self.source.id]),
                status_code=302,
                target_status_code=200,
            )
        with self.subTest("Test saved data"):
            chants_001r = Chant.objects.filter(source=self.source, folio="001r").all()
            self.assertEqual(len(chants_001r), 1)
            self.assertEqual(chants_001r[0].image_link, "https://example.com/001r")
            chants_001v = Chant.objects.filter(source=self.source, folio="001v").all()
            self.assertEqual(len(chants_001v), 2)
            for chant in chants_001v:
                self.assertEqual(chant.image_link, "https://example.com/001v")
            chants_003 = Chant.objects.filter(source=self.source, folio="003").all()
            self.assertEqual(len(chants_003), 1)
            self.assertIsNone(chants_003[0].image_link)
            chants_004B = Chant.objects.filter(source=self.source, folio="004B").all()
            self.assertEqual(len(chants_004B), 1)
            self.assertEqual(chants_004B[0].image_link, "https://i-already-exist.com/2")


class SourceDeleteViewTest(CustomAccessTestMixin, TestCase):
    source: Source

    def test_permissions(self) -> None:
        unassigned_source = make_fake_source()
        with self.subTest("Test anonymous user"):
            resp = self.client.get(
                reverse("source-delete", args=[unassigned_source.id])
            )
            self.assertEqual(resp.status_code, 302)
            resp = self.client.post(
                reverse("source-delete", args=[unassigned_source.id])
            )
            self.assertEqual(resp.status_code, 302)
            unassigned_source.refresh_from_db()
        with self.subTest("Test unassigned source"):
            for user_type in ["user", "editor", "global viewer"]:
                self.client.force_login(self.users[user_type])
                resp = self.client.get(
                    reverse("source-delete", args=[unassigned_source.id])
                )
                self.assertEqual(resp.status_code, 403)
                resp = self.client.post(
                    reverse("source-delete", args=[unassigned_source.id])
                )
                self.assertEqual(resp.status_code, 403)
                unassigned_source.refresh_from_db()
            self.client.force_login(self.users["superuser"])
            resp = self.client.get(
                reverse("source-delete", args=[unassigned_source.id])
            )
            self.assertEqual(resp.status_code, 200)
            resp = self.client.post(
                reverse("source-delete", args=[unassigned_source.id])
            )
            self.assertEqual(resp.status_code, 302)
            self.assertRaises(ObjectDoesNotExist, unassigned_source.refresh_from_db)
        with self.subTest("Test assigned source"):
            editor_assigned_source = make_fake_source(
                current_editors=[self.users["editor"]]
            )
            user_assigned_source = make_fake_source(
                current_editors=[self.users["user"]]
            )
            # Test that a user can delete neither source
            self.client.force_login(self.users["user"])
            resp = self.client.get(
                reverse("source-delete", args=[editor_assigned_source.id])
            )
            self.assertEqual(resp.status_code, 403)
            resp = self.client.post(
                reverse("source-delete", args=[editor_assigned_source.id])
            )
            self.assertEqual(resp.status_code, 403)
            editor_assigned_source.refresh_from_db()
            resp = self.client.get(
                reverse("source-delete", args=[user_assigned_source.id])
            )
            self.assertEqual(resp.status_code, 403)
            resp = self.client.post(
                reverse("source-delete", args=[user_assigned_source.id])
            )
            self.assertEqual(resp.status_code, 403)
            user_assigned_source.refresh_from_db()
            # Test that an editor can delete their own source only
            self.client.force_login(self.users["editor"])
            resp = self.client.get(
                reverse("source-delete", args=[editor_assigned_source.id])
            )
            self.assertEqual(resp.status_code, 200)
            resp = self.client.post(
                reverse("source-delete", args=[editor_assigned_source.id])
            )
            self.assertEqual(resp.status_code, 302)
            self.assertRaises(
                ObjectDoesNotExist, editor_assigned_source.refresh_from_db
            )
            resp = self.client.get(
                reverse("source-delete", args=[user_assigned_source.id])
            )
            self.assertEqual(resp.status_code, 403)
            resp = self.client.post(
                reverse("source-delete", args=[user_assigned_source.id])
            )
            self.assertEqual(resp.status_code, 403)
            user_assigned_source.refresh_from_db()
