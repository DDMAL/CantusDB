from django.core.management.base import BaseCommand
from main_app.models import (
    Century,
    Chant,
    Feast,
    Genre,
    Notation,
    Office,
    Provenance,
    RismSiglum,
    Segment,
    Sequence,
    Source,
)

# Run with `python manage.py save_all_objects`.
# This command runs through all objects in the database
# and saves them, thus triggering any on_save hooks in signals.py.


class Command(BaseCommand):
    def add_arguments(self, parser):
        pass

    def handle(self, *args, **options):
        for cls in (
            Century,
            Chant,
            Feast,
            Genre,
            Notation,
            Office,
            Provenance,
            RismSiglum,
            Segment,
            Sequence,
            Source,
        ):
            CHUNK_SIZE = 100
            objects_count = cls.objects.count()
            start_index = 0
            while start_index <= objects_count:
                print(f"processing {cls} chunk with start index of", start_index)
                chunk = cls.objects.all()[start_index:start_index+CHUNK_SIZE]
                for object in chunk:
                    object.save()
                start_index += CHUNK_SIZE