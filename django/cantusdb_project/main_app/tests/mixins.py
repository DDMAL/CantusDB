"""
Assorted mixins for test cases.
"""

from datetime import date
from typing import Optional, Dict, Set, Literal, List, Union

from django.http import HttpResponse
from django.urls import resolve
from django.test import RequestFactory
from django.contrib.auth.models import AnonymousUser
from django.views import View
from bs4 import BeautifulSoup

from users.models import User as UserT
from main_app.tests.make_fakes import make_fake_user, make_groups, make_fake_source
from main_app.models import Source


class HTMLContentsTestMixin:
    """
    A mixin that provides a `assertParsedContains` method to check for
    HTML contents in the response content.

    This mixin uses the BeautifulSoup library to parse the response content
    which is especially useful for dealing with more complex HTML checks and
    for dealing with disparate whitespace in rendered HTML.
    """

    def assertParsedContains(
        self,
        response: HttpResponse,
        text: str,
        count: Optional[int] = None,
        status_code: int = 200,
        html: bool = True,
    ) -> None:
        """
        Asserts that the response content contains the given text.

        :param response: The response object to check.
        :param text: The text to check for in the response content.
        :param count: The number of times the text should appear in the
            response content.
        :param status_code: The expected status code of the response.
        :param html: If True, the text is treated as HTML and parsed with
            BeautifulSoup.
        """
        self.assertEqual(
            response.status_code,
            status_code,
            "Response status code was %d (expected %d)"
            % (response.status_code, status_code),
        )

        if html:
            soup = BeautifulSoup(response.content, "lxml")
            contents = str(soup)
        else:
            contents = response.content.decode("utf-8")

        if count is not None:
            self.assertEqual(
                contents.count(text),
                count,
                "The text '%s' appeared %d times in the response "
                "content (expected %d times)" % (text, contents.count(text), count),
            )
        else:
            self.assertIn(
                text,
                contents,
                "The text '%s' was not found in the response content" % text,
            )


UserTypes = Literal["anonymous user", "user", "superuser", "editor", "global viewer"]


class CustomAccessTestMixin:
    """
    Mixin to help test permissions for views.
    """

    users: Dict[str, Union[UserT, AnonymousUser]]
    default_user: Optional[UserTypes] = None
    factory: RequestFactory

    @classmethod
    def setUpTestData(cls) -> None:
        groups = make_groups()
        cls.users = {
            "user": make_fake_user(),
            "superuser": make_fake_user(is_superuser=True),
            "editor": make_fake_user(groups=[(groups["editor"], None)]),
            "global viewer": make_fake_user(groups=[(groups["global viewer"], None)]),
            "expired global viewer": make_fake_user(
                groups=[(groups["global viewer"], date(2020, 1, 1))]
            ),
            "anonymous user": AnonymousUser(),
        }
        cls.factory = RequestFactory()

    def setUp(self) -> None:
        if self.default_user:
            self.client.force_login(user=self.users[self.default_user])

    def testDown(self) -> None:
        self.client.logout()

    def run_request_permissions_test(
        self,
        url: str,
        get_allowed_users: List[UserTypes],
        post_allowed_users: List[UserTypes],
        test_name: str,
    ) -> None:
        all_users: Set[UserTypes] = {
            "anonymous user",
            "user",
            "superuser",
            "editor",
            "global viewer",
        }
        get_denied_users: Set[UserTypes] = all_users - set(get_allowed_users)
        post_denied_users: Set[UserTypes] = all_users - set(post_allowed_users)
        resolved_url = resolve(url)
        view_class = resolved_url.func.view_class  # type: ignore
        url_args = resolved_url.args
        url_kwargs = resolved_url.kwargs
        req = self.factory.get(url)
        for user in get_allowed_users:
            with self.subTest(
                "Test GET allowed users.", user=user, test_name=test_name
            ):
                req.user = self.users[user]
                view = view_class()
                view.user = req.user
                view.setup(request=req, *url_args, **url_kwargs)
                test_resp = view.run_test_func()
                self.assertTrue(test_resp)
        for user in list(get_denied_users):
            with self.subTest("Test GET denied users.", user=user, test_name=test_name):
                req.user = self.users[user]
                view = view_class()
                view.user = req.user
                view.setup(request=req, *url_args, **url_kwargs)
                test_resp = view.run_test_func()
                self.assertFalse(test_resp)
        req = self.factory.post(url)
        # If post_allowed_users is empty, then POST requests are not
        # allowed for any user.
        if len(post_allowed_users) > 0:
            for user in post_allowed_users:
                with self.subTest(
                    "Test POST allowed users.", user=user, test_name=test_name
                ):
                    req.user = self.users[user]
                    view = view_class()
                    view.user = req.user
                    view.setup(request=req, *url_args, **url_kwargs)
                    test_resp = view.run_test_func()
                    self.assertTrue(test_resp)
            for user in list(post_denied_users):
                with self.subTest(
                    "Test POST denied users.", user=user, test_name=test_name
                ):
                    req.user = self.users[user]
                    view = view_class()
                    view.user = req.user
                    view.setup(request=req, *url_args, **url_kwargs)
                    test_resp = view.run_test_func()
                    self.assertFalse(test_resp)
