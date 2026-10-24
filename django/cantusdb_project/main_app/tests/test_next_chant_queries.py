from django.test import TestCase
from django.urls import reverse

from main_app.tests.make_fakes import make_fake_chant, make_fake_source
from next_chants import next_chants


class NextChantQueriesTest(TestCase):
    def test_successor_counts_use_one_query(self):
        for published in (True, True, True, False):
            source = make_fake_source(published=published)
            successor = make_fake_chant(source=source, cantus_id="successor")
            make_fake_chant(source=source, cantus_id="origin", next_chant=successor)
        source = make_fake_source(published=True)
        make_fake_chant(source=source, cantus_id="origin")
        successor = make_fake_chant(source=source, cantus_id="temporary")
        type(successor).objects.filter(pk=successor.pk).update(cantus_id=None)
        make_fake_chant(source=source, cantus_id="origin", next_chant=successor)

        with self.assertNumQueries(1):
            self.assertEqual(next_chants("origin"), [("successor", 3)])
        with self.assertNumQueries(1):
            self.assertEqual(next_chants("origin", True), [("successor", 4)])
        with self.assertNumQueries(1):
            self.assertEqual(next_chants("missing"), [])
        with self.assertNumQueries(1):
            response = self.client.get(reverse("json-nextchants", args=["origin"]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"successor": 3})
