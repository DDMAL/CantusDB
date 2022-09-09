from main_app.models import Chant
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand

# This script memoizes the result of Chant.get_next_chant(), which is expensive
# to calculate on the fly, saving it as the Chant's .next_chant property.
# This script populates the next_chant field for all chants in the database.
# Once it has been calculated once (for example, after importing data
# from OldCantus), it shouldn't need to be run again - whenever chants are
# created, updated or deleted, the field should be recalculated for all chants
# in the source by update_next_chant_fields() in main_app/signals.py.

# to calculate all chants' next_chants from scratch: `python manage.py populate_next_chant_fields --overwrite`
# to calculate next_chants for all chants that don't already have a next_chant specified: `python manage.py populate_next_chant_fields`

class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            "-o",
            "--overwrite", 
            action="store_true", 
            help="Overwrites next_chant of chants that already have a next_chant set."
            )

    def handle(self, *args, **kwargs):
        CHUNK_SIZE = 1_000
        overwrite = kwargs["overwrite"]
        chants = Chant.objects.all()
        chants_count = chants.count()
        start_index = 0
        while start_index <= chants_count:
            print("processing chunk with start_index of", start_index)
            chunk = chants[start_index:start_index+CHUNK_SIZE]
            for chant in chunk:
                if chant.next_chant and not overwrite: # unless -o or -overwrite flag has been supplied, skip chants that already have a next_chant
                    continue
                try:
                    chant.next_chant = chant.get_next_chant()
                    chant.save()
                except ValidationError: # another chant's next_chant already points to this chant's next_chant
                    pass
            del chunk # make sure we don't use too much RAM
            start_index += CHUNK_SIZE

