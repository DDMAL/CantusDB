from django.test import TestCase
from django.core.management import call_command

from main_app.models import Chant, Sequence

from main_app.tests.make_fakes import (
    make_fake_source,
    make_fake_project,
    make_fake_chant,
    make_fake_sequence,
)


class AssignSequencesToBowerProjectTest(TestCase):
    def test_assign_sequences_to_bower_project(self):
        project = make_fake_project(name="Clavis Sequentiarum")
        chant_source = make_fake_source()
        sequence_source = make_fake_source()
        for _ in range(5):
            make_fake_chant(source=chant_source, project=None)
        for _ in range(4):
            make_fake_sequence(source=sequence_source)
        all_chants = Chant.objects.all()
        for chant in all_chants:
            self.assertIsNone(chant.project_id)
        all_sequences = Sequence.objects.all()
        for sequence in all_sequences:
            self.assertIsNone(sequence.project_id)
        call_command("assign_sequences_to_bower_project")
        all_chants = Chant.objects.all()
        all_sequences = Sequence.objects.all()
        for chant in all_chants:
            self.assertIsNone(chant.project_id)
        for sequence in all_sequences:
            self.assertEqual(sequence.project_id, project.id)
