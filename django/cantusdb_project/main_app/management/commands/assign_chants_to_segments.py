"""
This command is meant to be used one time toward solving issue
1420: Chants should belong to segments.

This command iterates through all the sources in database and assigns
all chants in the database to the segment of the source they belong to. 
"""

from django.core.management.base import BaseCommand
from main_app.models import Source, Chant, Segment

CHANT_CHUNK_SIZE = 1_000


class Command(BaseCommand):
    help = "Assigns all chants in the database to the segment of the source they belong to."

    def handle(self, *args, **options):
        sources = Source.objects.all()
        for source in sources:
            segment = Segment.objects.get(id=source.segment_id)
            chants = Chant.objects.filter(source=source)
            chants_count = chants.count()
            start_index = 0
            while start_index < chants_count:
                chant_chunk = chants[start_index : start_index + CHANT_CHUNK_SIZE]
                for chant in chant_chunk:
                    chant.segment = segment
                    chant.save()
                start_index += CHANT_CHUNK_SIZE
