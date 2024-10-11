from django.test import TestCase
from django.core.management import call_command

from main_app.models import Source
from main_app.tests.make_fakes import make_fake_source


class TestPopulateSourceCompleteness(TestCase):
    def test_populate_source_completeness(self):
        # make a few "Full Source" sources
        for _ in range(5):
            make_fake_source(full_source=True)
        # make a few "Fragment" sources
        for _ in range(3):
            make_fake_source(full_source=False)
        # run the command
        call_command("populate_source_completeness")
        sources = Source.objects.all()
        for source in sources:
            if source.full_source:
                self.assertEqual(
                    source.source_completeness,
                    source.SourceCompletenessChoices.FULL_SOURCE,
                )
            else:
                self.assertEqual(
                    source.source_completeness,
                    source.SourceCompletenessChoices.FRAGMENT,
                )
