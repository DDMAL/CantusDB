from django.test import TestCase
from django.urls import reverse

from main_app.tests.mixins import CustomAccessTestMixin
from main_app.tests.make_fakes import make_fake_user, make_fake_source
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
