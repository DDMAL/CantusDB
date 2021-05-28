from main_app.models import Indexer
from django.core.management.base import BaseCommand
import requests, json


def get_indexer_list(file_path):
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


class Command(BaseCommand):
    def add_arguments(self, parser):
        # parser.add_argument(
        #     "indexer_list_file",
        #     type=str,
        #     default="/code/django/cantusdb_project/indexer_list.txt",
        # )
        pass

    def handle(self, *args, **options):
        # file_path = options["indexer_list_file"]
        file_path = "/code/django/cantusdb_project/indexer_list.txt"
        indexer_list = get_indexer_list(file_path)
        for id in indexer_list:
            get_new_indexer(id)
