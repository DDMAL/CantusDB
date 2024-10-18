from django.test import TestCase
from django.core.management import call_command

from main_app.models import Source
from main_app.tests.make_fakes import make_fake_source


class TestPopulateSourceCompleteness(TestCase):
    def test_populate_source_completeness(self):
        # make a few "Full Source" sources
        for _ in range(5):
            source = make_fake_source()
            source.full_source = True
            source.save()
        # make a few "Fragment" sources
        for _ in range(3):
            source = make_fake_source()
            source.full_source = False
            source.save()
        # make a few "Full Source" sources with full_source=None
        for _ in range(2):
            source = make_fake_source()
            source.full_source = None
            source.save()
        # run the command
        call_command("populate_source_completeness")
        sources = Source.objects.all()
        for source in sources:
            if source.full_source or source.full_source is None:
                self.assertEqual(
                    source.source_completeness,
                    source.SourceCompletenessChoices.FULL_SOURCE,
                )
            else:
                self.assertEqual(
                    source.source_completeness,
                    source.SourceCompletenessChoices.FRAGMENT,
                )
