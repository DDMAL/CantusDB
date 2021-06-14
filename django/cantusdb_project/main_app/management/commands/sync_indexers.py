from main_app.models import Indexer
from django.core.management.base import BaseCommand
import requests, json

INDEXER_ID_FILE = "indexer_list.txt"


def get_id_list(file_path):
    indexer_list = []
    file = open(file_path, "r")
    for line in file:
        line = line.strip("\n")
        indexer_list.append(line)
    file.close()
    return indexer_list


def get_new_indexer(indexer_id):
    url = f"http://cantus.uwaterloo.ca/json-node/{indexer_id}"
    response = requests.get(url)
    json_response = json.loads(response.content)
    if json_response["field_first_name"]:
        first_name = json_response["field_first_name"]["und"][0]["value"]
    else:
        first_name = None
    if json_response["field_family_name"]:
        family_name = json_response["field_family_name"]["und"][0]["value"]
    else:
        family_name = None
    if json_response["field_indexer_institution"]:
        institution = json_response["field_indexer_institution"]["und"][0]["value"]
    else:
        institution = None
    if json_response["field_indexer_city"]:
        city = json_response["field_indexer_city"]["und"][0]["value"]
    else:
        city = None
    if json_response["field_indexer_country"]:
        country = json_response["field_indexer_country"]["und"][0]["value"]
    else:
        country = None

    indexer, created = Indexer.objects.update_or_create(
        id=indexer_id,
        defaults={
            "first_name": first_name,
            "family_name": family_name,
            "institution": institution,
            "city": city,
            "country": country,
        },
    )
    if created:
        print(f"created indexer {indexer_id}")


def remove_extra():
    waterloo_ids = get_id_list(INDEXER_ID_FILE)
    our_ids = list(Indexer.objects.all().values_list("id", flat=True))
    our_ids = [str(id) for id in our_ids]
    waterloo_ids = set(waterloo_ids)
    print(f"Our count: {len(our_ids)}")
    print(f"Waterloo count: {len(waterloo_ids)}")
    extra_ids = [id for id in our_ids if id not in waterloo_ids]
    for id in extra_ids:
        Indexer.objects.get(id=id).delete()
        print(f"Extra item removed: {id}")


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            "--remove_extra",
            action="store_true",
            help="add this flag to remove the indexers in our database that are no longer present in waterloo database",
        )

    def handle(self, *args, **options):
        indexer_list = get_id_list(INDEXER_ID_FILE)
        for id in indexer_list:
            get_new_indexer(id)
        if options["remove_extra"]:
            remove_extra()
