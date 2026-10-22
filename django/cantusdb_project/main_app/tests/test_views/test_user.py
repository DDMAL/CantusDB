import random

from django.test import TestCase
from django.urls import reverse

from main_app.tests.mixins import CustomAccessTestMixin
from main_app.tests.make_fakes import (
    make_fake_user,
    make_fake_source,
    make_fake_chant,
    make_groups,
)
from main_app.views.user import IndexerListView, UserSourceListView
from users.models import User as UserType


class UserDetailViewTestCase(CustomAccessTestMixin, TestCase):
    indexer: UserType
    user: UserType

    @classmethod
    def setUpTestData(cls) -> None:
        super().setUpTestData()
        indexer = make_fake_user()
        indexer.is_indexer = True
        indexer.save()
        cls.indexer = indexer
        cls.user = make_fake_user()

    def test_permissions(self) -> None:
        self.run_request_permissions_test(
            reverse("user-detail", kwargs={"pk": self.user.pk}),
            get_allowed_users=["superuser"],
            post_allowed_users=[],
            test_name="Regular user",
        )
        # Check that the user themself can access their own detail view
        self.client.force_login(self.user)
        response = self.client.get(reverse("user-detail", kwargs={"pk": self.user.pk}))
        self.assertEqual(response.status_code, 200)
        self.client.logout()
        self.run_request_permissions_test(
            reverse("user-detail", kwargs={"pk": self.indexer.pk}),
            get_allowed_users=[
                "anonymous user",
                "user",
                "editor",
                "superuser",
                "global viewer",
            ],
            post_allowed_users=[],
            test_name="Indexer",
        )


class IndexerListViewTestCase(CustomAccessTestMixin, TestCase):
    user_with_source: UserType
    user_without_source: UserType
    user_with_unpublished_source: UserType

    @classmethod
    def setUpTestData(cls) -> None:
        super().setUpTestData()
        cls.user_with_source = make_fake_user()
        cls.user_without_source = make_fake_user()
        cls.user_with_unpublished_source = make_fake_user()
        source = make_fake_source(published=True)
        unpublished_source = make_fake_source(published=False)
        source.inventoried_by.clear()
        source.inventoried_by.add(cls.user_with_source)
        unpublished_source.inventoried_by.add(cls.user_with_unpublished_source)

    def test_shown_users(self) -> None:
        response = self.client.get(reverse("indexer-list"))
        self.assertEqual(response.status_code, 200)
        self.assertCountEqual([self.user_with_source], response.context["indexers"])

    def test_pagination(self) -> None:
        paginate_by = IndexerListView.paginate_by
        full_pages = 2
        # setUpTestData already creates 1 visible indexer (user_with_source),
        # so create paginate_by * full_pages - 1 sources to reach exactly 2 full pages.
        for _ in range(paginate_by * full_pages - 1):
            make_fake_source(published=True)

        for page_num in range(1, full_pages + 1):
            response = self.client.get(reverse("indexer-list"), {"page": page_num})
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.context["is_paginated"])
            self.assertEqual(len(response.context["indexers"]), paginate_by)

        random.seed(0)
        overflow = random.randint(1, paginate_by - 1)
        for _ in range(overflow):
            make_fake_source(published=True)

        response = self.client.get(reverse("indexer-list"), {"page": full_pages + 1})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["indexers"]), overflow)

        response = self.client.get(reverse("indexer-list"), {"page": "last"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["indexers"]), overflow)

        for invalid_page in [-1, 0, "lst", full_pages + 2]:
            response = self.client.get(reverse("indexer-list"), {"page": invalid_page})
            self.assertEqual(response.status_code, 404)


class UserSourceListViewTest(TestCase):
    # No setUpTestData: data is user-specific and created per test.
    def test_unauthenticated_access(self) -> None:
        response = self.client.get(reverse("my-sources"))
        self.assertRedirects(response, f"/login/?next={reverse('my-sources')}")

    def test_pagination(self) -> None:
        paginate_by = UserSourceListView.paginate_by
        full_pages = 2
        user = make_fake_user()
        self.client.force_login(user)
        for _ in range(paginate_by * full_pages):
            make_fake_source(published=True, current_editors=[user])

        for page_num in range(1, full_pages + 1):
            response = self.client.get(reverse("my-sources"), {"page": page_num})
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.context["is_paginated"])
            self.assertEqual(len(response.context["sources"]), paginate_by)

        random.seed(0)
        overflow = random.randint(1, paginate_by - 1)
        for _ in range(overflow):
            make_fake_source(published=True, current_editors=[user])

        response = self.client.get(reverse("my-sources"), {"page": full_pages + 1})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["sources"]), overflow)

        response = self.client.get(reverse("my-sources"), {"page": "last"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["sources"]), overflow)

        for invalid_page in [-1, 0, "lst", full_pages + 2]:
            response = self.client.get(reverse("my-sources"), {"page": invalid_page})
            self.assertEqual(response.status_code, 404)

    def test_submitted_source_offers_no_chant_editing_links(self) -> None:
        # Submitting locks the source's chants (issue #1962) and bumps
        # `date_updated`, which floats it to the top of this page — so the
        # links it offers must not be ones that now 403.
        user = make_fake_user()
        source = make_fake_source(published=False, current_editors=[user])
        source.created_by = user
        source.save()
        make_fake_chant(source=source)
        self.client.force_login(user)

        edit_chants_url = reverse("source-edit-chants", args=[source.pk])
        before = self.client.get(reverse("my-sources"))
        self.assertContains(before, edit_chants_url)

        source.submit_for_proofreading(user)

        after = self.client.get(reverse("my-sources"))
        self.assertNotContains(after, edit_chants_url)
        self.assertNotContains(after, reverse("chant-create", args=[source.pk]))
        self.assertContains(after, "Submitted for proofreading")
        # The links are hidden because they would be refused.
        self.assertEqual(self.client.get(edit_chants_url).status_code, 403)

    def test_editor_keeps_chant_editing_links_on_submitted_source(self) -> None:
        # An editor is the one who proofreads a submitted source, so the lock
        # must not take their links away.
        groups = make_groups()
        editor = make_fake_user(groups=[(groups["editor"], None)])
        source = make_fake_source(published=False, current_editors=[editor])
        source.created_by = editor
        source.save()
        make_fake_chant(source=source)
        source.submit_for_proofreading(editor)

        self.client.force_login(editor)
        response = self.client.get(reverse("my-sources"))
        self.assertContains(response, reverse("source-edit-chants", args=[source.pk]))
        self.assertNotContains(response, "Submitted for proofreading")
