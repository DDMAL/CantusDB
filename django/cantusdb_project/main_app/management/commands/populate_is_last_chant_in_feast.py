from main_app.models import Chant
from django.core.management.base import BaseCommand


# Run with `python manage.py populate_is_last_chant_in_feast`.
class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        CHUNK_SIZE = 1_000
        chants = Chant.objects.all()
        chants_count = chants.count()
        start_index = 0
        while start_index <= chants_count:
            print("processing chunk with start_index of", start_index)
            chunk = chants[start_index : start_index + CHUNK_SIZE]

            for chant in chunk:
                this_chant_feast = chant.feast
                if this_chant_feast is None:
                    chant.is_last_chant_in_feast = False
                    continue
                try:
                    next_chant_feast = chant.next_chant.feast
                    if next_chant_feast is None:
                        chant.is_last_chant_in_feast = True
                    if this_chant_feast != next_chant_feast:
                        chant.is_last_chant_in_feast = True
                    else:
                        chant.is_last_chant_in_feast = False
                except AttributeError:  # next_chant is None
                    chant.is_last_chant_in_feast = True
                chant.save()
            del chunk  # make sure we don't use too much RAM
            start_index += CHUNK_SIZE
