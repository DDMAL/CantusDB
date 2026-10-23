from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from main_app.models import Source, Genre
from main_app.tests.make_fakes import make_fake_source, make_fake_user


class ContentOverviewQueriesTest(TestCase):
    def test_rendered_attribution_queries_do_not_grow_with_rows(self):
        user = make_fake_user(is_superuser=True)
        self.client.force_login(user)
        url = reverse("content-overview")
        self.client.get(url)  # Initialize the singleton banner.
        for model in (Source, Genre):
            with self.subTest(model=model.__name__):

                def add_row(index):
                    if model is Source:
                        return make_fake_source(
                            shelfmark=f"Overview {index}",
                            created_by=user,
                            last_updated_by=user,
                        )
                    return Genre.objects.create(
                        name=f"G{index}",
                        description="Overview genre",
                        created_by=user,
                        last_updated_by=user,
                    )

                first = add_row(1)
                params = {"model": str(model._meta.verbose_name_plural)}
                with CaptureQueriesContext(connection) as baseline:
                    response = self.client.get(url, params)
                self.assertContains(response, user.full_name)
                if model is Source:
                    self.assertContains(response, first.short_heading)
                for index in range(2, 6):
                    add_row(index)
                model.objects.create(
                    **(
                        {"shelfmark": "No attribution"}
                        if model is Source
                        else {"name": "N", "description": "No attribution"}
                    )
                )
                with CaptureQueriesContext(connection) as expanded:
                    response = self.client.get(url, params)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(len(expanded), len(baseline))
