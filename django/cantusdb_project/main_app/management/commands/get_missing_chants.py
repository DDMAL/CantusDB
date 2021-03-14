import json
import pprint
import random
import sys
import time
from typing import Dict, List

import requests
from django.core.management.base import BaseCommand

from main_app.models import Chant


class Command(BaseCommand):
    def add_arguments(self, parser):
        pass

    def handle(self, *args, **options):
        json_file = open("/code/django/cantusdb_project/chant_id_list.json", "r")
        # where does this json file come from? It contains all the chant ids, up-to-date with old cantusDB?
        id_list = set(json.load(json_file))
        downloaded_log_file = open("chants_downloaded.txt", "a")
        error_log_file = open("error_log.txt", "a")
        chants_json_file = open("chants_downloaded.json", "a")
        chants_json_file.write("[")

        # chants that we already have in our database
        chant_id_list = set(
            Chant.objects.all().values_list("id", flat=True).order_by("id")
        )
        # these are the new chants we need to get
        missing_ids = list(id_list.difference(chant_id_list))

        # Get size and set and index for bookkeeping
        length = len(missing_ids)
        i = 0

        while missing_ids:
            # Pick a random item from the list and pop it, which removes it and gets the value
            random_index = random.randrange(len(missing_ids))
            chant_id = missing_ids.pop(random_index)

            # Make the request and write to our json file and one of our log files
            try:
                url = f"http://cantus.uwaterloo.ca/chant/{chant_id}"
                response = requests.get(url)
                print(response)
                # json_response = json.loads(response.content)
                # chants_json_file.write(f"{str(json.dumps(json_response))}\n")
                # chants_json_file.write(",")
                # downloaded_log_file.write(f"{chant_id}\n")
            # Log any exceptions
            except Exception as e:
                error_log_file.write(f"Error at {chant_id} with exception {e}\n")

            # Print progress to terminal
            i += 1
            percent_done = round(((i / length) * 100), 6)
            sys.stdout.write(f"\r{percent_done} %")

            # Sleep every 1000 requests
            if i % 1000 == 0:
                time.sleep(10)

        # Finish the json file
        chants_json_file.write("]")

        # Make terminal nice at the end
        print("\n")
