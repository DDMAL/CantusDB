import csv
import io

from django.conf import settings
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from main_app.models import Chant, Differentia, Segment, Sequence
from main_app.tests.make_fakes import (
    make_fake_feast,
    make_fake_genre,
    make_fake_service,
    make_fake_source,
)


class CsvExportQueriesTest(TestCase):
    def test_related_queries_do_not_grow_with_export_rows(self):
        feast = make_fake_feast(name="Export feast")
        service = make_fake_service(name="V")
        genre = make_fake_genre(name="A")
        differentia = Differentia.objects.create(differentia_id="129a")
        for model, segment_id in (
            (Chant, settings.CANTUS_SEGMENT_ID),
            (Sequence, settings.BOWER_SEGMENT_ID),
        ):
            with self.subTest(model=model.__name__):
                source = make_fake_source(published=True)
                segment, _ = Segment.objects.get_or_create(
                    pk=segment_id, defaults={"name": f"Segment {segment_id}"}
                )
                source.segment_m2m.set([segment])
                fields = dict(
                    source=source,
                    feast=feast,
                    service=service,
                    genre=genre,
                    diff_db=differentia,
                    c_sequence=1,
                    s_sequence="01",
                )
                model.objects.create(**fields)
                url = reverse("csv-export", args=[source.pk])
                with CaptureQueriesContext(connection) as baseline:
                    response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                for _ in range(4):
                    model.objects.create(**fields)
                model.objects.create(source=source, c_sequence=2, s_sequence="02")
                with CaptureQueriesContext(connection) as expanded:
                    response = self.client.get(url)
                self.assertEqual(len(expanded), len(baseline))
                rows = list(csv.DictReader(io.StringIO(response.content.decode())))
                self.assertEqual(len(rows), 6)
                for row in rows[:5]:
                    self.assertEqual(row["feast"], feast.name)
                    self.assertEqual(row["service"], service.name)
                    self.assertEqual(row["genre"], genre.name)
                    self.assertEqual(row["differentiae_database"], "129a")
                self.assertEqual(rows[-1]["differentiae_database"], "")
