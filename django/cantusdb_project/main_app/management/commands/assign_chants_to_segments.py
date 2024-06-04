"""
This command is meant to be used one time toward solving issue
1420: Chants should belong to segments.

This command iterates through all the sources in database and assigns
all chants in the database to the segment of the source they belong to. 
"""

from django.core.management.base import BaseCommand
from main_app.models import Source, Chant, Segment, Sequence


class Command(BaseCommand):
    help = "Assigns all chants in the database to the segment of the source they belong to."

    def handle(self, *args, **options):
        sources = Source.objects.all()
        for source in sources:
            segment = Segment.objects.get(id=source.segment_id)
            chants = Chant.objects.filter(source=source)
            sequences = Sequence.objects.filter(source=source)
            chants_count = chants.count()
            sequences_count = sequences.count()
            if chants_count != 0 and sequences_count != 0:
                self.stdout.write(
                    self.style.ERROR(
                        f"Source {source.id} has {chants_count} chants and {sequences_count} sequences."
                    )
                )
                continue
            if chants_count > 0:
                chants.update(segment=segment)
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Assigned {chants_count} chants in source {source.id} to segment {segment.id}."
                    )
                )
            else:
                sequences.update(segment=segment)
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Assigned {sequences_count} sequences in source {source.id} to segment {segment.id}."
                    )
                )
