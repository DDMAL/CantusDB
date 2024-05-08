from django.test import TestCase
from django.core.management import call_command

from main_app.models import Chant

from main_app.tests.make_fakes import make_fake_source, make_fake_segment


class AssignChantsToSegmentsTest(TestCase):
    def test_assign_chants_to_segments(self):
        segment_1 = make_fake_segment()
        segment_2 = make_fake_segment()
        source_1 = make_fake_source(segment=segment_1)
        source_2 = make_fake_source(segment=segment_2)
        for _ in range(5):
            Chant.objects.create(source=source_1)
        for _ in range(3):
            Chant.objects.create(source=source_2)
        all_chants = Chant.objects.all()
        for chant in all_chants:
            self.assertIsNone(chant.segment_id)
        call_command("assign_chants_to_segments")
        source_1_chants = Chant.objects.filter(source=source_1)
        source_2_chants = Chant.objects.filter(source=source_2)
        for chant in source_1_chants:
            self.assertEqual(chant.segment_id, segment_1.id)
        for chant in source_2_chants:
            self.assertEqual(chant.segment_id, segment_2.id)
