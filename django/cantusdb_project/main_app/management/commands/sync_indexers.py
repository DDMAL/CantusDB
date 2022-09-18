from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
import requests, json
from faker import Faker

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
    # use json-export to get indexer information
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

    # check whether the current indexer has a user entry of the same name
    indexer_full_name = f"{first_name} {family_name}"
    print(f"{indexer_id} {indexer_full_name}")
    homonymous_users = get_user_model().objects.filter(full_name__iexact=indexer_full_name)
    # if the indexer also exists as a user
    if homonymous_users:
        assert homonymous_users.count() == 1
        homonymous_user = homonymous_users.get()
        print(f"homonymous: {homonymous_user.full_name}")
        # keep the user as it is (merge the indexer into existing user)
        # and store the ID of its indexer object
        homonymous_user.old_indexer_id = indexer_id
        homonymous_user.show_in_list = True
        homonymous_user.save()
    # if the indexer doesn't exist as a user
    else:
        faker = Faker()
        # create a new user with the indexer information
        get_user_model().objects.create(
            institution=institution,
            city=city,
            country=country,
            full_name=indexer_full_name,
            # assign random email to dummy users
            email=f"{faker.lexify('????????')}@fakeemail.com",
            # leave the password empty for dummy users
            # the password can't be empty in login form, so they can't log in
            password="",
            old_indexer_id = indexer_id,
            show_in_list=True,
        )


class Command(BaseCommand):
    def add_arguments(self, parser):
        pass

    def handle(self, *args, **options):
        indexer_list = get_id_list(INDEXER_ID_FILE)
        for id in indexer_list:
            get_new_indexer(id)
            