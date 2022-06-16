from main_app.models import Chant
from django.core.management.base import BaseCommand

class Command(BaseCommand):

    def handle(self, *args, **kwargs):
        CHUNK_SIZE = 1_000
        chants = Chant.objects.all()
        start_index = 0
        while True:
            print("processing chunk with start_index of", start_index)
            try:
                chants_chunk = chants[start_index:start_index+CHUNK_SIZE]
            except IndexError:
                break
            
            for chant in chants_chunk:
                this_chant_feast = chant.feast
                if this_chant_feast is None:
                    chant.ends_feast = False
                    continue
                try:
                    next_chant_feast = chant.next_chant.feast
                    if next_chant_feast is None:
                        chant.ends_feast = True
                    if this_chant_feast != next_chant_feast:
                        chant.ends_feast = True
                    else:
                        chant.ends_feast = False
                except AttributeError: # next_chant is None
                    chant.ends_feast = True
                chant.save()
            del chants_chunk # make sure we don't use too much RAM
            start_index += CHUNK_SIZE