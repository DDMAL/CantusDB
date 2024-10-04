from django.test import TestCase
from django.core.management import call_command

from main_app.models import Source
from main_app.tests.make_fakes import make_fake_institution, make_fake_segment


class TestReformatSourceIDs(TestCase):
    def test_command(self):
        segment = make_fake_segment()
        fake_inst = make_fake_institution()
        correct_source_1 = Source.objects.create(
            segment=segment,
            shelfmark="Correct Source 1",
            holding_institution=fake_inst,
            dact_id="0a1b3",
            fragmentarium_id="a1b3",
        )
        correct_source_2 = Source.objects.create(
            segment=segment,
            shelfmark="Correct Source 2",
            holding_institution=fake_inst,
            dact_id="D-0a1b3",
            fragmentarium_id="F-a1b3",
        )
        source_with_no_ids = Source.objects.create(
            segment=segment,
            shelfmark="Source with no IDs",
            holding_institution=fake_inst,
        )
        source_with_incorrect_ids = Source.objects.create(
            segment=segment,
            shelfmark="Source with incorrect IDs",
            holding_institution=fake_inst,
            dact_id="a1b3",
            fragmentarium_id="F-1b3",
        )

        call_command("reformat_source_ids")
        self.assertEqual(Source.objects.get(pk=correct_source_1.pk).dact_id, "D:0a1b3")
        self.assertEqual(
            Source.objects.get(pk=correct_source_1.pk).fragmentarium_id, "F-a1b3"
        )
        self.assertEqual(Source.objects.get(pk=correct_source_2.pk).dact_id, "D:0a1b3")
        self.assertEqual(
            Source.objects.get(pk=correct_source_2.pk).fragmentarium_id, "F-a1b3"
        )
        self.assertIsNone(Source.objects.get(pk=source_with_no_ids.pk).dact_id)
        self.assertIsNone(Source.objects.get(pk=source_with_no_ids.pk).fragmentarium_id)
        self.assertEqual(
            Source.objects.get(pk=source_with_incorrect_ids.pk).dact_id, "a1b3"
        )
        self.assertEqual(
            Source.objects.get(pk=source_with_incorrect_ids.pk).fragmentarium_id,
            "F-1b3",
        )
