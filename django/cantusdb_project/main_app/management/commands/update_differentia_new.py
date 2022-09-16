from main_app.models import Chant
from django.core.management.base import BaseCommand
import json

# In the past, the BaseChant model had a `.differentia` field and a `.differentia_id` field.
# There was no data stored in the `differentia_id` field for any Chant or Sequence.
# Then it was discovered that OldCantus has a `field_differentia` and a `field_differentia_new`
# (but only for Chants, not for sequences).
# This script takes the data stored in all Chants' `.json_info` fields and uses it to populate
# those chants' `differentia_new` field (which has replaced the old `differentia_id` field.)

# sync_chants.py has been updated to populate the `differentia_new` field. If you have run
# sync_chants.py since September 15, 2022, you should not need to run this script.

# run with `python manage.py update_differentia_new`


class Command(BaseCommand):

    def handle(self, *args, **kwargs):
        CHUNK_SIZE = 1_000
        chants = Chant.objects.all()
        chants_count = chants.count()
        start_index = 0
        while start_index <= chants_count:
            print("processing chunk with start_index of", start_index)
            chunk = chants[start_index:start_index+CHUNK_SIZE]
            for chant in chunk:
                try:
                    differentia_new = chant.json_info["field_differentia_new"]["und"][0]["value"]
                    chant.differentia_new = differentia_new
                except TypeError: # json_info["field_differentia_new"] is empty
                    chant.differentia_new = None
                chant.save()
            del chunk # make sure we don't use too much RAM
            start_index += CHUNK_SIZE

