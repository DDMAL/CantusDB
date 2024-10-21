"""
A temporary command to populate the source_completeness field in the Source model, 
based on the full_source field. This command will be removed once the source_completeness
is initially populated.
"""

from django.core.management.base import BaseCommand
from main_app.models import Source


class Command(BaseCommand):
    def handle(self, *args, **options):
        sources = Source.objects.all()
        for source in sources:
            if source.full_source or source.full_source is None:
                source.source_completeness = (
                    source.SourceCompletenessChoices.FULL_SOURCE
                )
            else:
                source.source_completeness = source.SourceCompletenessChoices.FRAGMENT
            source.save()
        self.stdout.write(self.style.SUCCESS("Source completeness populated"))
