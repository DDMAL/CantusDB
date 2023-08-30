from django.core.management.base import BaseCommand
from main_app.models import Source, Sequence, Chant, Segment


class Command(BaseCommand):
    def handle(self, *args, **options):
        cantus_segment = Segment.objects.get(id=4063)
        calvin_segment = Segment.objects.get(id=4064)
        chants = Chant.objects.all().filter(source__isnull=True)
        sequences = Sequence.objects.all().filter(source__isnull=True)

        if len(chants) > 0 and len(sequences) > 0:
            unknown_source_chants = Source.objects.create(
                segment=cantus_segment,
                siglum="Unknown",
                published=False,
                title="Unknown Source (Chants)",
            )
            unknown_source_sequences = Source.objects.create(
                segment=calvin_segment,
                siglum="Unknown",
                published=False,
                title="Unknown Source (Sequences)",
            )

            for c in chants:
                c.source = unknown_source_chants
                c.save()
            for s in sequences:
                s.source = unknown_source_sequences
                s.save()
