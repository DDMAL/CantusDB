from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import ValidationError
from django.db import ProgrammingError
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone

from main_app.context_processors import site_banner
from main_app.models import SiteBanner
from main_app.tests.make_fakes import make_fake_user


class SiteBannerModelTest(TestCase):
    def test_save_enforces_singleton(self) -> None:
        SiteBanner.objects.create(message="first")
        SiteBanner.objects.create(message="second")
        self.assertEqual(SiteBanner.objects.count(), 1)
        self.assertEqual(SiteBanner.objects.get().message, "second")
        self.assertEqual(SiteBanner.objects.get().pk, 1)

    def test_load_creates_row_on_first_call(self) -> None:
        self.assertFalse(SiteBanner.objects.exists())
        banner = SiteBanner.load()
        self.assertEqual(banner.pk, 1)
        self.assertEqual(SiteBanner.objects.count(), 1)

    def test_load_returns_existing_row(self) -> None:
        SiteBanner.objects.create(message="hello", is_active=True)
        banner = SiteBanner.load()
        self.assertEqual(banner.message, "hello")
        self.assertTrue(banner.is_active)

    def test_delete_is_noop(self) -> None:
        banner = SiteBanner.objects.create(message="keep me")
        banner.delete()
        self.assertEqual(SiteBanner.objects.count(), 1)

    def test_save_rejects_past_expiry(self) -> None:
        past = timezone.now() - timedelta(minutes=1)
        with self.assertRaises(ValidationError) as ctx:
            SiteBanner.objects.create(message="hi", expires_at=past)
        self.assertIn("expires_at", ctx.exception.message_dict)

    def test_save_accepts_future_expiry(self) -> None:
        future = timezone.now() + timedelta(hours=1)
        SiteBanner.objects.create(message="hi", expires_at=future)
        self.assertEqual(SiteBanner.objects.get().expires_at, future)

    def test_save_accepts_blank_expiry(self) -> None:
        SiteBanner.objects.create(message="hi", expires_at=None)
        self.assertIsNone(SiteBanner.objects.get().expires_at)

    def test_save_allows_resaving_untouched_past_expiry(self) -> None:
        """An expiry that has already elapsed must not block further edits;
        only a newly entered past time is rejected."""
        SiteBanner.objects.create(
            message="old",
            is_active=True,
            expires_at=timezone.now() + timedelta(hours=1),
        )
        # Force the stored expiry into the past, mimicking elapsed time.
        SiteBanner.objects.filter(pk=1).update(
            expires_at=timezone.now() - timedelta(hours=1)
        )
        banner = SiteBanner.load()
        banner.message = "updated"
        banner.save()  # must not raise even though expires_at is in the past
        self.assertEqual(SiteBanner.objects.get().message, "updated")

    def test_save_rejects_newly_set_past_expiry_on_existing_row(self) -> None:
        SiteBanner.objects.create(message="hi")  # row exists, no expiry
        banner = SiteBanner.load()
        banner.expires_at = timezone.now() - timedelta(minutes=1)
        with self.assertRaises(ValidationError) as ctx:
            banner.save()
        self.assertIn("expires_at", ctx.exception.message_dict)

    def test_save_runs_full_clean(self) -> None:
        """Regression guard: save() must run model validation so any
        validator added in the future is enforced. Mirrors BaseModel's
        contract; SiteBanner doesn't extend BaseModel because its
        singleton semantics don't fit (no detail URL, no meaningful
        creator)."""
        with patch.object(SiteBanner, "full_clean") as mocked:
            SiteBanner.objects.create(message="hi")
        mocked.assert_called_once()

    def test_has_content_false_when_message_blank(self) -> None:
        banner = SiteBanner(is_active=True, message="   ")
        self.assertFalse(banner.has_content())

    def test_has_content_true_when_no_expiry(self) -> None:
        banner = SiteBanner(is_active=True, message="hi", expires_at=None)
        self.assertTrue(banner.has_content())

    def test_has_content_true_when_expiry_in_future(self) -> None:
        future = timezone.now() + timedelta(hours=1)
        banner = SiteBanner(is_active=True, message="hi", expires_at=future)
        self.assertTrue(banner.has_content())

    def test_has_content_false_when_expired(self) -> None:
        past = timezone.now() - timedelta(hours=1)
        banner = SiteBanner(is_active=True, message="hi", expires_at=past)
        self.assertFalse(banner.has_content())

    def test_is_displayable_requires_active_and_content(self) -> None:
        banner = SiteBanner(is_active=False, message="hi")
        self.assertFalse(banner.is_displayable())
        banner.is_active = True
        self.assertTrue(banner.is_displayable())
        banner.message = ""
        self.assertFalse(banner.is_displayable())

    def test_rendered_message_blank_returns_empty(self) -> None:
        banner = SiteBanner(message="   ")
        self.assertEqual(banner.rendered_message(), "")

    def test_rendered_message_renders_link_and_bold(self) -> None:
        banner = SiteBanner(
            message="See [the wiki](https://example.com) for **details**."
        )
        html = banner.rendered_message()
        self.assertIn('<a href="https://example.com">the wiki</a>', html)
        self.assertIn("<strong>details</strong>", html)

    def test_rendered_message_strips_outer_p_for_single_paragraph(self) -> None:
        banner = SiteBanner(message="hello")
        self.assertEqual(banner.rendered_message(), "hello")

    def test_rendered_message_keeps_p_tags_for_multi_paragraph(self) -> None:
        banner = SiteBanner(message="Para 1\n\nPara 2")
        html = banner.rendered_message()
        self.assertEqual(html.count("<p>"), 2)
        self.assertIn("Para 1", html)
        self.assertIn("Para 2", html)

    def test_rendered_message_hard_wraps_single_newlines(self) -> None:
        banner = SiteBanner(message="Line 1\nLine 2")
        html = banner.rendered_message()
        self.assertIn("<br", html)
        self.assertIn("Line 1", html)
        self.assertIn("Line 2", html)

    def test_rendered_message_suppresses_raw_html(self) -> None:
        banner = SiteBanner(message="Hello <script>alert(1)</script> world")
        html = banner.rendered_message()
        self.assertNotIn("<script>", html)
        self.assertNotIn("alert(1)</script>", html)
        # cmarkgfm replaces raw HTML with a comment marker
        self.assertIn("raw HTML omitted", html)

    def test_rendered_message_strips_javascript_url(self) -> None:
        banner = SiteBanner(message="[click](javascript:alert(1))")
        html = banner.rendered_message()
        self.assertNotIn("javascript:", html)
        self.assertIn('href=""', html)

    def test_rendered_message_strips_data_url(self) -> None:
        banner = SiteBanner(message="[click](data:text/html,foo)")
        html = banner.rendered_message()
        self.assertNotIn("data:", html)

    def test_rendered_message_allows_mailto_and_relative(self) -> None:
        banner = SiteBanner(message="[mail](mailto:a@b.com) [home](/articles/)")
        html = banner.rendered_message()
        self.assertIn('href="mailto:a@b.com"', html)
        self.assertIn('href="/articles/"', html)


class SiteBannerContextProcessorTest(TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        cls.factory = RequestFactory()
        cls.superuser = make_fake_user(is_superuser=True)
        cls.regular_user = make_fake_user()

    def _request(self, user) -> object:
        req = self.factory.get("/")
        req.user = user
        return req

    def test_active_banner_returned_to_anonymous(self) -> None:
        SiteBanner.objects.create(message="maintenance soon", is_active=True)
        context = site_banner(self._request(AnonymousUser()))
        self.assertIsNotNone(context["SITE_BANNER"])
        self.assertFalse(context["SITE_BANNER_IS_PREVIEW"])

    def test_inactive_banner_hidden_from_anonymous(self) -> None:
        SiteBanner.objects.create(message="draft", is_active=False)
        context = site_banner(self._request(AnonymousUser()))
        self.assertIsNone(context["SITE_BANNER"])

    def test_inactive_banner_hidden_from_regular_user(self) -> None:
        SiteBanner.objects.create(message="draft", is_active=False)
        context = site_banner(self._request(self.regular_user))
        self.assertIsNone(context["SITE_BANNER"])

    def test_inactive_banner_previewed_to_superuser(self) -> None:
        SiteBanner.objects.create(message="draft", is_active=False)
        context = site_banner(self._request(self.superuser))
        self.assertIsNotNone(context["SITE_BANNER"])
        self.assertTrue(context["SITE_BANNER_IS_PREVIEW"])

    def test_expired_banner_hidden_even_from_superuser(self) -> None:
        # Save with a future expiry (validation requires it), then push the
        # row's expires_at into the past via queryset update to bypass save().
        # Models the real-world case of a banner whose expiry time has elapsed.
        SiteBanner.objects.create(
            message="old notice",
            is_active=True,
            expires_at=timezone.now() + timedelta(hours=1),
        )
        SiteBanner.objects.filter(pk=1).update(
            expires_at=timezone.now() - timedelta(hours=1)
        )
        context = site_banner(self._request(self.superuser))
        self.assertIsNone(context["SITE_BANNER"])

    def test_blank_message_hidden_even_from_superuser(self) -> None:
        SiteBanner.load()  # row exists, but message is empty
        context = site_banner(self._request(self.superuser))
        self.assertIsNone(context["SITE_BANNER"])

    def test_fails_closed_when_table_missing(self) -> None:
        """The deploy serves new code before `migrate` creates the table, so
        this processor runs against a missing table mid-rollout. It must return
        no banner instead of raising, which would 500 every page site-wide."""
        with patch.object(
            SiteBanner, "load", side_effect=ProgrammingError("table does not exist")
        ):
            context = site_banner(self._request(AnonymousUser()))
        self.assertIsNone(context["SITE_BANNER"])
        self.assertFalse(context["SITE_BANNER_IS_PREVIEW"])


class SiteBannerRenderingTest(TestCase):
    """End-to-end checks that the banner partial renders correctly in base.html."""

    @classmethod
    def setUpTestData(cls) -> None:
        cls.superuser = make_fake_user(is_superuser=True)

    def test_active_banner_appears_in_page_for_anonymous(self) -> None:
        SiteBanner.objects.create(
            message="See [read more](https://example.com) for details.",
            is_active=True,
        )
        response = self.client.get(reverse("article-list"))
        self.assertContains(response, '<a href="https://example.com">read more</a>')
        self.assertContains(response, "alert-warning")
        self.assertNotContains(response, "PREVIEW")
        # Raw markdown source must not leak into the page
        self.assertNotContains(response, "[read more](")

    def test_preview_appears_only_for_superuser(self) -> None:
        SiteBanner.objects.create(message="draft notice", is_active=False)
        # Anonymous: no banner.
        response = self.client.get(reverse("article-list"))
        self.assertNotContains(response, "draft notice")
        # Superuser: sees preview.
        self.client.force_login(self.superuser)
        response = self.client.get(reverse("article-list"))
        self.assertContains(response, "draft notice")
        self.assertContains(response, "PREVIEW")

    def test_no_banner_when_message_empty(self) -> None:
        SiteBanner.load()  # row exists with blank message
        response = self.client.get(reverse("article-list"))
        self.assertNotContains(response, "alert-warning")

    def test_footer_edit_link_visible_only_to_superuser(self) -> None:
        # Anonymous: no edit link.
        response = self.client.get(reverse("article-list"))
        self.assertNotContains(response, "Edit Site Banner")
        # Superuser: link is present.
        self.client.force_login(self.superuser)
        response = self.client.get(reverse("article-list"))
        self.assertContains(response, "Edit Site Banner")


class SiteBannerAdminTest(TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        cls.superuser = make_fake_user(is_superuser=True)

    def test_save_sets_updated_by(self) -> None:
        self.client.force_login(self.superuser)
        SiteBanner.load()  # ensure row exists
        url = reverse("admin:main_app_sitebanner_change", args=[1])
        response = self.client.post(
            url,
            {"is_active": "on", "message": "hello", "expires_at": ""},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        banner = SiteBanner.objects.get()
        self.assertEqual(banner.updated_by, self.superuser)
        self.assertEqual(banner.message, "hello")
        self.assertTrue(banner.is_active)

    def test_changelist_redirects_to_singleton(self) -> None:
        self.client.force_login(self.superuser)
        url = reverse("admin:main_app_sitebanner_changelist")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(
            reverse("admin:main_app_sitebanner_change", args=[1]),
            response["Location"],
        )

    def test_add_view_is_disabled(self) -> None:
        self.client.force_login(self.superuser)
        url = reverse("admin:main_app_sitebanner_add")
        response = self.client.get(url)
        # has_add_permission=False → 403.
        self.assertEqual(response.status_code, 403)
