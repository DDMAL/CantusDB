from django.test import TestCase
from django.core.management import call_command

from main_app.models import Chant, Sequence, Project

from main_app.tests.make_fakes import make_fake_source


class AssignSequencesToBowerProjectTest(TestCase):
    def test_assign_sequences_to_bower_project(self):
        project = Project.objects.create(name="Clavis Sequentiarum")
        chant_source = make_fake_source()
        sequence_source = make_fake_source()
        for _ in range(5):
            Chant.objects.create(source=chant_source)
        for _ in range(4):
            Sequence.objects.create(source=sequence_source)
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
