"""
This command is meant to be used one time toward solving issue
1420: Chants should belong to segments.

This command iterates through all the sources in database and assigns
all chants in the database to the segment of the source they belong to. 
"""

from django.core.management.base import BaseCommand
from main_app.models import Source, Chant, Segment


class Command(BaseCommand):
    help = "Assigns all chants in the database to the segment of the source they belong to."

    def handle(self, *args, **options):
        sources = Source.objects.all()
        for source in sources:
            segment = Segment.objects.get(id=source.segment_id)
            chants = Chant.objects.filter(source=source)
            chants.update(segment=segment)
