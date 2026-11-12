"""Source gallery edits must change the links readers actually see (#1958)."""

from typing import Any
from datetime import date
from unittest.mock import patch

from bs4 import BeautifulSoup
from django.conf import settings
from django.test import Client, TestCase
from django.urls import reverse
from reversion.models import Version
from users.models import GroupMembership

from main_app.models import Source, SourceURL
from main_app.tests.make_fakes import (
    make_fake_chant,
    make_fake_segment,
    make_fake_source,
)
from main_app.tests.mixins import CustomAccessTestMixin


class SourceImageLinksViewTest(CustomAccessTestMixin, TestCase):
    default_user = "editor"
    old_url = "https://example.org/old-gallery"
    new_url = "https://arca.irht.cnrs.fr/ark:/63955/md23vt150j1w"

    @classmethod
    def setUpTestData(cls) -> None:
        super().setUpTestData()
        cls.segment = make_fake_segment(
            id=settings.CANTUS_SEGMENT_ID, name="CANTUS Database"
        )

    def make_source(self, legacy: str | None = old_url, **kwargs: Any) -> Source:
        return make_fake_source(
            image_link=legacy,
            segment=[self.segment],
            current_editors=[self.users["editor"]],
            **kwargs,
        )

    def make_link(
        self, source: Source, url: str = old_url, url_type: int = 3
    ) -> SourceURL:
        return SourceURL.objects.create(
            source=source,
            url=url,
            url_type=url_type,
            url_description="Preserve this description",
        )

    def post_data(
        self, source: Source | None, rows: list[tuple[int | None, str, bool]]
    ) -> dict[str, Any]:
        data: dict[str, Any] = {
            "shelfmark": source.shelfmark if source else "new-gallery-source",
            "source_completeness": "1",
            "production_method": "1",
            "segment_m2m": [self.segment.pk],
            "image_links-TOTAL_FORMS": str(len(rows)),
            "image_links-INITIAL_FORMS": str(sum(pk is not None for pk, _, _ in rows)),
        }
        for i, (pk, url, delete) in enumerate(rows):
            data[f"image_links-{i}-id"] = str(pk) if pk is not None else ""
            data[f"image_links-{i}-url"] = url
            if delete:
                data[f"image_links-{i}-DELETE"] = "on"
        return data

    def post_edit(self, source: Source, data: dict[str, Any]):
        return self.client.post(reverse("source-edit", args=[source.pk]), data)

    def assert_public_link(self, source: Source, url: str | None) -> None:
        public = Client()
        response = public.get(reverse("source-detail", args=[source.pk]))
        self.assertEqual(response.status_code, 200)
        soup = BeautifulSoup(response.content, "html.parser")
        links = [
            a["href"]
            for a in soup.find_all("a")
            if a.get_text(strip=True) == "View images on external site"
        ]
        self.assertEqual(links, [url] if url else [])
        response = public.get(reverse("json-node-export", args=[source.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["image_link"], url)

    def test_edit_changes_the_link_on_public_pages(self) -> None:
        source = self.make_source()
        link = self.make_link(source)
        make_fake_chant(source=source, image_link=None)
        response = self.post_edit(
            source, self.post_data(source, [(link.pk, self.new_url, False)])
        )
        self.assertRedirects(response, reverse("source-detail", args=[source.pk]))
        link.refresh_from_db()
        self.assertEqual(link.url, self.new_url)
        self.assertEqual(link.url_description, "Preserve this description")
        source.refresh_from_db()
        self.assertIsNone(source.image_link)
        self.assert_public_link(source, self.new_url)
        for route, args in (
            ("source-edit", [source.pk]),
            ("source-list", []),
            ("browse-chants", [source.pk]),
        ):
            client = self.client if route == "source-edit" else Client()
            page = client.get(reverse(route, args=args))
            self.assertEqual(page.status_code, 200)
            self.assertContains(page, f'href="{self.new_url}"')
            self.assertNotContains(page, f'href="{self.old_url}"')

    def test_get_shows_existing_links_and_conflicting_previous_url(self) -> None:
        source = self.make_source(legacy=self.new_url)
        link = self.make_link(source)
        page = self.client.get(reverse("source-edit", args=[source.pk]))
        self.assertEqual(page.status_code, 200)
        self.assertEqual(
            page.context["image_link_formset"].forms[0]["url"].value(), link.url
        )
        self.assertContains(page, "Another image link was previously entered")
        self.assertContains(page, "To replace an outdated link, paste this URL over")
        self.assertContains(page, self.new_url)
        self.assertNotIn("image_link", page.context["form"].fields)
        source.refresh_from_db()
        self.assertEqual(source.image_link, self.new_url)
        self.assertEqual(source.source_links.count(), 1)

    def test_metadata_only_edit_preserves_conflicting_previous_url(self) -> None:
        source = self.make_source(legacy=self.new_url)
        link = self.make_link(source)
        data = self.post_data(source, [(link.pk, link.url, False)])
        data["shelfmark"] = "changed metadata"
        self.assertEqual(self.post_edit(source, data).status_code, 302)
        source.refresh_from_db()
        self.assertEqual(source.image_link, self.new_url)
        self.assertEqual(source.shelfmark, "changed metadata")

    def test_legacy_only_link_is_prefilled_and_migrates_when_saved(self) -> None:
        source = self.make_source()
        self.make_link(source, "https://example.org/manifest", 1)
        page = self.client.get(reverse("source-edit", args=[source.pk]))
        self.assertEqual(
            page.context["image_link_formset"].forms[0]["url"].value(), self.old_url
        )
        self.assertEqual(source.source_links.count(), 1)  # GET did not migrate it.
        data = self.post_data(source, [(None, self.old_url, False)])
        self.assertEqual(self.post_edit(source, data).status_code, 302)
        source.refresh_from_db()
        self.assertIsNone(source.image_link)
        self.assertEqual(source.source_links.get(url_type=3).url, self.old_url)
        self.assertEqual(
            source.source_links.get(url_type=1).url, "https://example.org/manifest"
        )
        self.assert_public_link(source, self.old_url)

    def test_legacy_only_link_can_be_changed_or_cleared(self) -> None:
        for url in (self.new_url, ""):
            with self.subTest(url=url):
                source = self.make_source()
                response = self.post_edit(
                    source, self.post_data(source, [(None, url, False)])
                )
                self.assertEqual(response.status_code, 302)
                source.refresh_from_db()
                self.assertIsNone(source.image_link)
                self.assert_public_link(source, url or None)

    def test_deleting_last_link_does_not_resurrect_legacy_url(self) -> None:
        source = self.make_source()
        link = self.make_link(source, self.new_url)
        response = self.post_edit(source, self.post_data(source, [(link.pk, "", True)]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(source.source_links.exists())
        self.assert_public_link(source, None)

    def test_multiple_links_can_be_changed_removed_and_added_individually(self) -> None:
        source = self.make_source()
        first = self.make_link(source)
        second = self.make_link(source, "https://example.org/second")
        removed = self.make_link(source, "https://example.org/removed")
        manifest = self.make_link(source, "https://example.org/manifest", 1)
        catalogue = self.make_link(source, "https://example.org/catalogue", 2)
        data = self.post_data(
            source,
            [
                (first.pk, self.new_url, False),
                (second.pk, second.url, False),
                (removed.pk, removed.url, True),
                (None, "https://example.org/additional", False),
            ],
        )
        self.assertEqual(self.post_edit(source, data).status_code, 302)
        actual = dict(source.source_links.values_list("pk", "url"))
        self.assertEqual(actual[first.pk], self.new_url)
        self.assertEqual(actual[second.pk], second.url)
        self.assertNotIn(removed.pk, actual)
        self.assertEqual(actual[manifest.pk], manifest.url)
        self.assertEqual(actual[catalogue.pk], catalogue.url)
        self.assertIn("https://example.org/additional", actual.values())
        source.refresh_from_db()
        self.assertEqual(source.external_images_url, self.new_url)
        page = Client().get(reverse("source-detail", args=[source.pk]))
        soup = BeautifulSoup(page.content, "html.parser")
        galleries = [
            a["href"]
            for a in soup.find_all("a")
            if a.get_text(strip=True) == "View images on external site"
        ]
        self.assertEqual(
            galleries, [self.new_url, second.url, "https://example.org/additional"]
        )

    def test_invalid_link_or_source_changes_nothing(self) -> None:
        for invalid_part in ("url", "source"):
            with self.subTest(invalid_part=invalid_part):
                source = self.make_source()
                link = self.make_link(source)
                data = self.post_data(source, [(link.pk, self.new_url, False)])
                data["image_links-0-url" if invalid_part == "url" else "shelfmark"] = ""
                response = self.post_edit(source, data)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "This field is required")
                if invalid_part == "url":
                    self.assertContains(response, 'href="#source-image-links"')
                source.refresh_from_db()
                link.refresh_from_db()
                self.assertEqual(source.image_link, self.old_url)
                self.assertEqual(link.url, self.old_url)

    def test_missing_management_form_does_not_save_source(self) -> None:
        source = self.make_source()
        original = source.shelfmark
        data = self.post_data(source, [])
        del data["image_links-TOTAL_FORMS"]
        data["shelfmark"] = "must not save"
        response = self.post_edit(source, data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "The image gallery form could not be read")
        source.refresh_from_db()
        self.assertEqual(source.shelfmark, original)

    def test_predeployment_form_preserves_submitted_legacy_url_for_recovery(
        self,
    ) -> None:
        source = self.make_source()
        link = self.make_link(source)
        data = self.post_data(source, [])
        del data["image_links-TOTAL_FORMS"]
        del data["image_links-INITIAL_FORMS"]
        data["image_link"] = self.new_url
        data["shelfmark"] = "unsaved metadata"
        response = self.post_edit(source, data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "The image gallery form could not be read")
        self.assertContains(response, "Copy any you want to keep before reloading")
        self.assertContains(response, self.new_url)
        self.assertEqual(
            response.context["form"]["shelfmark"].value(), data["shelfmark"]
        )
        source.refresh_from_db()
        link.refresh_from_db()
        self.assertNotEqual(source.shelfmark, data["shelfmark"])
        self.assertEqual(source.image_link, self.old_url)
        self.assertEqual(link.url, self.old_url)

    def test_unreadable_formset_shows_escaped_submitted_urls_without_saving(
        self,
    ) -> None:
        for source in (None, self.make_source()):
            with self.subTest(create=source is None):
                link = self.make_link(source) if source else None
                malicious = '<script>alert("URL")</script>'
                data = self.post_data(
                    source,
                    [
                        (link.pk if link else None, self.new_url, False),
                        (None, malicious, False),
                    ],
                )
                data["image_links-TOTAL_FORMS"] = "invalid"
                response = (
                    self.post_edit(source, data)
                    if source
                    else self.client.post(reverse("source-create"), data)
                )
                self.assertEqual(response.status_code, 200)
                self.assertContains(
                    response, "The image gallery form could not be read"
                )
                self.assertContains(response, self.new_url)
                self.assertContains(response, "&lt;script&gt;")
                self.assertNotContains(response, malicious)
                if link:
                    link.refresh_from_db()
                    self.assertEqual(link.url, self.old_url)
                else:
                    self.assertFalse(
                        Source.objects.filter(shelfmark=data["shelfmark"]).exists()
                    )

    def test_other_sources_and_other_link_types_cannot_be_edited_or_deleted(
        self,
    ) -> None:
        source = self.make_source()
        own = self.make_link(source)
        other = self.make_link(self.make_source())
        manifest = self.make_link(source, "https://example.org/manifest", 1)
        catalogue = self.make_link(source, "https://example.org/catalogue", 2)
        for target in (other, manifest, catalogue):
            for delete in (False, True):
                with self.subTest(target=target.pk, delete=delete):
                    original = target.url
                    data = self.post_data(source, [(target.pk, self.new_url, delete)])
                    response = self.post_edit(source, data)
                    self.assertEqual(response.status_code, 200)
                    target.refresh_from_db()
                    own.refresh_from_db()
                    self.assertEqual(target.url, original)
                    self.assertEqual(own.url, self.old_url)

    def test_forged_type_on_new_row_cannot_create_iiif_link(self) -> None:
        source = self.make_source(legacy=None)
        data = self.post_data(source, [(None, self.new_url, False)])
        data["image_links-0-url_type"] = "1"
        response = self.post_edit(source, data)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(source.source_links.get().url_type, 3)

    def test_omitted_or_extra_existing_id_is_rejected(self) -> None:
        source = self.make_source()
        link = self.make_link(source)
        for rows, initial in (([], "0"), ([(link.pk, self.new_url, False)], "0")):
            with self.subTest(initial=initial, rows=rows):
                data = self.post_data(source, rows)
                data["image_links-INITIAL_FORMS"] = initial
                self.assertEqual(self.post_edit(source, data).status_code, 200)
                link.refresh_from_db()
                self.assertEqual(link.url, self.old_url)

    def test_users_without_source_edit_access_cannot_change_links(self) -> None:
        source = self.make_source()
        link = self.make_link(source)
        source.current_editors.add(self.users["user"], self.users["global viewer"])
        for user in (
            "user",
            "global viewer",
            "expired global viewer",
            "anonymous user",
        ):
            with self.subTest(user=user):
                self.client.logout()
                if user != "anonymous user":
                    self.client.force_login(self.users[user])
                response = self.post_edit(
                    source, self.post_data(source, [(link.pk, self.new_url, False)])
                )
                self.assertIn(response.status_code, (302, 403))
                link.refresh_from_db()
                self.assertEqual(link.url, self.old_url)
        self.client.force_login(self.users["editor"])
        source.current_editors.clear()
        self.assertEqual(
            self.post_edit(
                source, self.post_data(source, [(link.pk, self.new_url, False)])
            ).status_code,
            403,
        )

    def test_assigned_creator_and_superuser_can_edit_links(self) -> None:
        for role in ("user", "superuser"):
            with self.subTest(role=role):
                source = self.make_source(created_by=self.users[role])
                if role == "user":
                    source.current_editors.add(self.users[role])
                link = self.make_link(source)
                self.client.force_login(self.users[role])
                self.assertEqual(
                    self.post_edit(
                        source, self.post_data(source, [(link.pk, self.new_url, False)])
                    ).status_code,
                    302,
                )
                link.refresh_from_db()
                self.assertEqual(link.url, self.new_url)

    def test_changed_links_record_actor_and_revision(self) -> None:
        source = self.make_source()
        link = self.make_link(source)
        data = self.post_data(
            source,
            [
                (link.pk, self.new_url, False),
                (None, "https://example.org/extra", False),
            ],
        )
        self.assertEqual(self.post_edit(source, data).status_code, 302)
        link.refresh_from_db()
        added = source.source_links.get(url="https://example.org/extra")
        for item in (link, added):
            self.assertEqual(item.last_updated_by, self.users["editor"])
            version = Version.objects.get_for_object(item).first()
            self.assertIsNotNone(version)
            self.assertEqual(version.field_dict["url"], item.url)
            self.assertEqual(version.revision.user, self.users["editor"])
        self.assertEqual(added.created_by, self.users["editor"])

    def test_deleted_link_is_recorded_in_revision_history(self) -> None:
        source = self.make_source()
        link = self.make_link(source)
        original_pk = link.pk
        response = self.post_edit(
            source, self.post_data(source, [(link.pk, link.url, True)])
        )
        self.assertEqual(response.status_code, 302)
        version = Version.objects.get_for_object(source).first()
        self.assertIsNotNone(version)
        self.assertIn(f"#{original_pk}: {self.old_url}", version.revision.comment)
        self.assertIn("Preserve this description", version.revision.comment)
        self.assertEqual(version.revision.user, self.users["editor"])

    def test_expired_editor_cannot_change_link(self) -> None:
        source = self.make_source()
        link = self.make_link(source)
        GroupMembership.objects.filter(user=self.users["editor"]).update(
            expiration=date(2000, 1, 1)
        )
        response = self.post_edit(
            source, self.post_data(source, [(link.pk, self.new_url, False)])
        )
        self.assertEqual(response.status_code, 403)
        link.refresh_from_db()
        self.assertEqual(link.url, self.old_url)

    def test_retired_conflicting_legacy_url_is_recorded_in_history(self) -> None:
        for delete in (False, True):
            with self.subTest(delete=delete):
                source = self.make_source(legacy=self.new_url)
                link = self.make_link(source)
                response = self.post_edit(
                    source,
                    self.post_data(
                        source, [(link.pk, "https://example.org/replacement", delete)]
                    ),
                )
                self.assertEqual(response.status_code, 302)
                source.refresh_from_db()
                self.assertIsNone(source.image_link)
                comment = (
                    Version.objects.get_for_object(source).first().revision.comment
                )
                self.assertIn(
                    f"Legacy image gallery URL before this edit: {self.new_url}",
                    comment,
                )
                if delete:
                    self.assertIn(self.old_url, comment)

    def test_stale_form_keeps_unsaved_input_and_explains_recovery(self) -> None:
        source = self.make_source()
        link = self.make_link(source)
        data = self.post_data(source, [(link.pk, self.new_url, False)])
        data["shelfmark"] = "unsaved shelfmark"
        self.make_link(source, "https://example.org/added-by-another-editor")
        response = self.post_edit(source, data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Copy any edits you want to keep")
        self.assertContains(response, 'href="#source-image-links"')
        self.assertEqual(
            response.context["form"]["shelfmark"].value(), data["shelfmark"]
        )
        self.assertEqual(
            response.context["image_link_formset"].forms[0]["url"].value(), self.new_url
        )
        original_shelfmark = source.shelfmark
        source.refresh_from_db()
        link.refresh_from_db()
        self.assertEqual(source.shelfmark, original_shelfmark)
        self.assertEqual(link.url, self.old_url)

    def test_deletion_history_keeps_stored_url_when_deleted_row_was_edited(
        self,
    ) -> None:
        source = self.make_source()
        link = self.make_link(source)
        response = self.post_edit(
            source, self.post_data(source, [(link.pk, self.new_url, True)])
        )
        self.assertEqual(response.status_code, 302)
        comment = Version.objects.get_for_object(source).first().revision.comment
        self.assertIn(self.old_url, comment)
        self.assertNotIn(self.new_url, comment)

    def test_link_failure_rolls_back_source_and_other_link_changes(self) -> None:
        source = self.make_source()
        link = self.make_link(source)
        data = self.post_data(source, [(link.pk, self.new_url, False)])
        original = source.shelfmark
        data["shelfmark"] = "must roll back"
        with patch.object(SourceURL, "save", side_effect=RuntimeError("failure")):
            with self.assertRaisesMessage(RuntimeError, "failure"):
                self.post_edit(source, data)
        source.refresh_from_db()
        link.refresh_from_db()
        self.assertEqual(source.shelfmark, original)
        self.assertEqual(source.image_link, self.old_url)
        self.assertEqual(link.url, self.old_url)

    def test_create_stores_gallery_records_and_assigns_creator(self) -> None:
        self.client.force_login(self.users["user"])
        data = self.post_data(None, [(None, self.new_url, False)])
        response = self.client.post(reverse("source-create"), data)
        source = Source.objects.get(shelfmark=data["shelfmark"])
        self.assertRedirects(response, reverse("source-detail", args=[source.pk]))
        self.assertIsNone(source.image_link)
        self.assertEqual(source.source_links.get().url, self.new_url)
        self.assertIn(self.users["user"], source.current_editors.all())
        self.assertEqual(source.source_links.get().created_by, self.users["user"])

    def test_invalid_create_does_not_leave_a_source(self) -> None:
        data = self.post_data(None, [(None, "not a URL", False)])
        response = self.client.post(reverse("source-create"), data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Enter a valid URL")
        self.assertContains(response, 'href="#source-image-links"')
        self.assertFalse(Source.objects.filter(shelfmark=data["shelfmark"]).exists())

    def test_create_link_failure_does_not_leave_source_or_assignment(self) -> None:
        data = self.post_data(None, [(None, self.new_url, False)])
        count = self.users["editor"].sources_user_can_edit.count()
        with patch.object(SourceURL, "save", side_effect=RuntimeError("failure")):
            with self.assertRaisesMessage(RuntimeError, "failure"):
                self.client.post(reverse("source-create"), data)
        self.assertFalse(Source.objects.filter(shelfmark=data["shelfmark"]).exists())
        self.assertEqual(self.users["editor"].sources_user_can_edit.count(), count)

    def test_added_row_survives_invalid_create_and_can_be_corrected(self) -> None:
        data = self.post_data(
            None,
            [(None, self.new_url, False), (None, "not a URL", False)],
        )
        response = self.client.post(reverse("source-create"), data)
        self.assertEqual(response.status_code, 200)
        formset = response.context["image_link_formset"]
        self.assertEqual(formset.total_form_count(), 2)
        self.assertEqual(formset.forms[0]["url"].value(), self.new_url)
        self.assertEqual(formset.forms[1]["url"].value(), "not a URL")
        self.assertFalse(Source.objects.filter(shelfmark=data["shelfmark"]).exists())
        data["image_links-1-url"] = "https://example.org/corrected"
        response = self.client.post(reverse("source-create"), data)
        self.assertEqual(response.status_code, 302)
        source = Source.objects.get(shelfmark=data["shelfmark"])
        self.assertCountEqual(
            source.source_links.values_list("url", flat=True),
            [self.new_url, "https://example.org/corrected"],
        )

    def test_empty_source_and_blank_extra_row_are_allowed(self) -> None:
        for legacy in (None, ""):
            with self.subTest(legacy=legacy):
                source = self.make_source(legacy=legacy)
                response = self.post_edit(
                    source, self.post_data(source, [(None, "", False)])
                )
                self.assertEqual(response.status_code, 302)
                self.assertFalse(source.source_links.exists())
                self.assert_public_link(source, None)

    def test_links_support_long_urls_and_encode_spaces(self) -> None:
        source = self.make_source()
        url = "https://example.org/" + "x" * 250 + "/image gallery"
        response = self.post_edit(source, self.post_data(source, [(None, url, False)]))
        self.assertEqual(response.status_code, 302)
        self.assert_public_link(source, url.replace(" ", "%20"))
