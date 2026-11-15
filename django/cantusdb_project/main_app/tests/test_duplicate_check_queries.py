from django.test import TestCase

from main_app.models import Chant, Sequence
from main_app.tasks import check_duplicate_folio_sequence
from main_app.tests.make_fakes import make_fake_source


class DuplicateCheckQueriesTest(TestCase):
    def test_group_members_are_collected_in_two_queries(self):
        expected = {"published": [], "unpublished": []}
        for published in (True, False):
            source = make_fake_source(published=published)
            bucket = expected["published" if published else "unpublished"]
            for model, sequence_field, id_field in (
                (Chant, "c_sequence", "chant_ids"),
                (Sequence, "s_sequence", "sequence_ids"),
            ):
                for folio in ("001r", "002r", "003r"):
                    ids = [
                        model.objects.create(
                            source=source, folio=folio, **{sequence_field: 1}
                        ).pk
                        for _ in range(2)
                    ]
                    bucket.append((id_field, ids))
                # Nonduplicates and incomplete grouping keys must not appear.
                model.objects.create(source=source, folio="004r", **{sequence_field: 1})
                for _ in range(2):
                    model.objects.create(source=source, **{sequence_field: 1})
                    model.objects.create(source=source, folio="005r")

        with self.assertNumQueries(2):
            result = check_duplicate_folio_sequence()
        for partition, groups in expected.items():
            self.assertEqual(len(result[partition]), len(groups))
            for id_field, ids in groups:
                self.assertTrue(
                    any(
                        group.get(id_field) == ids and group["count"] == 2
                        for group in result[partition]
                    )
                )

        chant_ids = expected["published"][0][1]
        sequence_ids = expected["published"][3][1]
        with self.assertNumQueries(2):
            scoped = check_duplicate_folio_sequence(chant_ids, sequence_ids)
        self.assertEqual(len(scoped["published"]), 2)
        self.assertEqual(scoped["unpublished"], [])
        with self.assertNumQueries(2):
            partial = check_duplicate_folio_sequence(chant_ids[:1], sequence_ids[:1])
        self.assertEqual(partial, {"published": [], "unpublished": []})
