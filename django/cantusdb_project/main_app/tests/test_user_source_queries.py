from django.db import connection
from django.template.loader import render_to_string
from django.test import RequestFactory, TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from main_app.models import Chant, Sequence
from main_app.templatetags.helper_tags import (
    get_user_created_source_pagination,
    get_user_source_pagination,
)
from main_app.tests.make_fakes import make_fake_source, make_fake_user


class UserSourceQueriesTest(TestCase):
    def test_homepage_and_my_sources_have_constant_query_counts(self):
        user = make_fake_user()
        self.client.force_login(user)
        request = RequestFactory().get("/")
        request.user = user

        def render_homepage():
            return render_to_string(
                "flatpages/default.html", {"user": user}, request=request
            )

        def render_my_sources():
            response = self.client.get(reverse("my-sources"))
            self.assertEqual(response.status_code, 200)
            return response.content.decode()

        source = make_fake_source(created_by=user, name="Named manuscript")
        Chant.objects.create(source=source)
        render_homepage()  # Initialize the singleton banner.
        query_counts = {}
        for render in (render_homepage, render_my_sources):
            with CaptureQueriesContext(connection) as baseline:
                html = render()
            self.assertIn("Named manuscript", html)
            self.assertIn(reverse("source-edit-chants", args=[source.pk]), html)
            query_counts[render] = len(baseline)

        # Include a sequence-only source: cached total count is not chant existence.
        empty = make_fake_source(created_by=user, name="Empty manuscript")
        sequence_only = make_fake_source(created_by=user, name="Sequence manuscript")
        Sequence.objects.create(source=sequence_only)
        for render in (render_homepage, render_my_sources):
            with CaptureQueriesContext(connection) as expanded:
                html = render()
            self.assertEqual(len(expanded), query_counts[render])
            self.assertNotIn(reverse("source-edit-chants", args=[empty.pk]), html)
            self.assertNotIn(
                reverse("source-edit-chants", args=[sequence_only.pk]), html
            )
            self.assertIn(reverse("source-edit-chants", args=[source.pk]), html)
            self.assertIn("Sequence manuscript", html)

    def test_template_tags_load_heading_and_chant_existence_with_the_page(self):
        user = make_fake_user()
        sources = [
            make_fake_source(created_by=user, name=f"Named {i}") for i in range(8)
        ]
        Chant.objects.create(source=sources[-1])
        Sequence.objects.create(source=sources[-2])
        request = RequestFactory().get("/", {"page": 2, "page2": 1})
        context = {"user": user, "request": request}
        for tag, page_number in (
            (get_user_source_pagination, 2),
            (get_user_created_source_pagination, 1),
        ):
            with self.subTest(tag=tag.__name__):
                with self.assertNumQueries(2):
                    page = tag(context)
                    rows = [
                        (source.pk, source.heading, source.has_chants)
                        for source in page
                    ]
                self.assertEqual(page.number, page_number)
                self.assertTrue(rows)
                for pk, heading, has_chants in rows:
                    self.assertIn("Named", heading)
                    self.assertEqual(has_chants, pk == sources[-1].pk)
