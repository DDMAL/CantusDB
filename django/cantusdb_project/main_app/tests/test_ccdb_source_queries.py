from django.conf import settings
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from main_app.models import Segment
from main_app.tests.make_fakes import (
    make_fake_institution,
    make_fake_provenance,
    make_fake_source,
)


class CcdbSourceQueriesTest(TestCase):
    def test_rendered_source_relations_have_constant_query_count(self):
        segment, _ = Segment.objects.get_or_create(
            pk=settings.CCDB_SEGMENT_ID, defaults={"name": "CCDB"}
        )

        def add_source(index, with_relations=True):
            source = make_fake_source(
                published=True,
                shelfmark=f"QueryRegression {index}",
                holding_institution=(
                    make_fake_institution(siglum=f"Test-{index}")
                    if with_relations
                    else None
                ),
                provenance=make_fake_provenance() if with_relations else None,
            )
            source.segment_m2m.set([segment])
            return source

        source = add_source(1)
        url = reverse("ccdb-chant-search")
        params = {"keyword": "QueryRegression"}
        self.client.get(url, params)  # Initialize the singleton banner.
        with CaptureQueriesContext(connection) as baseline:
            response = self.client.get(url, params)
        self.assertContains(response, source.short_heading)
        self.assertContains(response, source.provenance.name)
        more_sources = [add_source(i) for i in range(2, 5)]
        more_sources.append(add_source(5, with_relations=False))
        with CaptureQueriesContext(connection) as expanded:
            response = self.client.get(url, params)
        self.assertEqual(len(expanded), len(baseline))
        self.assertEqual(response.context["ccdb_source_count"], 5)
        for source in more_sources:
            self.assertContains(response, source.short_heading)
