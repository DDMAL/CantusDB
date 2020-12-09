import json
import random
import sys
import time
from pprint import pprint
from typing import Dict, List

import requests
from django.core.management.base import BaseCommand
from main_app.models import Sequence


class Command(BaseCommand):
    def add_arguments(self, parser):
        pass

    def handle(self, *args, **options):
        # Open the files we need
        ids_json_file = open("/code/django/cantusdb_project/sequence_ids.json", "r")
        seq_json_file = open("/code/django/cantusdb_project/sequences.json", "w")
        downloaded_log_file = open("seqs_downloaded.txt", "a")
        error_log_file = open("error_log.txt", "a")

        seq_json_file.write("[")

        id_list = [element["nid"] for element in json.load(ids_json_file)]

        # Get size and set and index for bookkeeping
        length = len(id_list)
        print(f"There are {length} sequences\n")
        i = 0
        while id_list:
            # Pick a random item from the list and pop it, which removes it and gets the value
            random_index = random.randrange(len(id_list))
            seq_id = id_list.pop(random_index)

            try:
                # Make the request
                url = f"http://cantus.uwaterloo.ca/json-node/{seq_id}"
                response = requests.get(url)

                # Print response to file
                json_response = json.loads(response.content)
                seq_json_file.write(f"{str(json.dumps(json_response))}\n")
                seq_json_file.write(",")
                downloaded_log_file.write(f"{seq_id}\n")

            # Log any exceptions
            except Exception as e:
                error_log_file.write(f"Error at {seq_id} with exception {e}\n")

            # Print progress to terminal
            i += 1
            percent_done = round(((i / length) * 100), 6)
            sys.stdout.write(f"\r{percent_done} %")

            # Sleep every 1000 requests
            if i % 1000 == 0:
                time.sleep(10)

        # Finish the json file
        seq_json_file.write("]")

        # Make terminal nice at the end
        print("\n")
