from django.conf import settings
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from main_app.models import Differentia, Segment, Sequence
from main_app.tests.make_fakes import (
    make_fake_feast,
    make_fake_genre,
    make_fake_service,
    make_fake_source,
)


class SequenceInventoryQueriesTest(TestCase):
    def test_inventory_relation_queries_do_not_grow_with_rows(self):
        source = make_fake_source(published=True)
        segment, _ = Segment.objects.get_or_create(
            pk=settings.BOWER_SEGMENT_ID, defaults={"name": "Bower"}
        )
        source.segment_m2m.set([segment])
        feast = make_fake_feast(name="Inventory feast")
        service = make_fake_service(name="V")
        genre = make_fake_genre(name="A")
        differentia = Differentia.objects.create(differentia_id="129a")
        fields = dict(
            source=source,
            feast=feast,
            service=service,
            genre=genre,
            diff_db=differentia,
        )
        Sequence.objects.create(s_sequence="01", title="First sequence", **fields)
        url = reverse("source-inventory", args=[source.pk])
        self.client.get(url)  # Initialize the singleton banner.
        with CaptureQueriesContext(connection) as baseline:
            response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        for index in range(2, 6):
            Sequence.objects.create(s_sequence=f"0{index}", **fields)
        Sequence.objects.create(source=source, s_sequence="06", title="Last sequence")
        with CaptureQueriesContext(connection) as expanded:
            response = self.client.get(url)
        self.assertEqual(len(expanded), len(baseline))
        self.assertContains(response, feast.name, count=5)
        self.assertContains(response, service.description, count=5)
        self.assertContains(response, genre.description, count=5)
        self.assertContains(
            response, "https://differentiaedatabase.ca/differentia/129a", count=5
        )
        self.assertLess(
            response.content.index(b"First sequence"),
            response.content.index(b"Last sequence"),
        )
