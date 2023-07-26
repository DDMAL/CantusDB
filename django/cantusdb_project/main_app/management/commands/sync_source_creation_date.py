from django.core.management.base import BaseCommand
from main_app.models import (
    Source,
)
import requests, json
import datetime
from django.utils import timezone


def get_source_list():
    source_list = []
    file = open("source_list.txt", "r")
    for line in file:
        line = line.strip("\n")
        source_list.append(line)
    file.close()
    return source_list


def convert_epoch_to_date_time(epoch):
    try:
        epoch_time = float(epoch)
        datetime_str = datetime.datetime.fromtimestamp(epoch_time)
        datetime_obj = timezone.make_aware(datetime_str, timezone.utc)
    except (ValueError, TypeError) as e:
        print(f"Error converting epoch time: {e}")
        return None
    return datetime_obj


def update_date_created(source_id):
    url = f"http://cantus.uwaterloo.ca/json-node/{source_id}"
    response = requests.get(url)
    json_response = json.loads(response.content)
    try:
        date_created_epoch = json_response["created"]
    except (KeyError, TypeError) as e:
        print(f"Exception for source {source_id}: {e}")
        date_created_epoch = None
    if date_created_epoch is not None:
        datetime_str = convert_epoch_to_date_time(date_created_epoch)
        if datetime_str is not None:
            Source.objects.filter(id=source_id).update(date_created=datetime_str)
            source_obj = Source.objects.get(id=source_id)
        return source_obj


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            "id",
            type=str,
            help="update one source (<source_id>)) or update all sources ('all')",
        )

    def handle(self, *args, **options):
        # before running this, run sync_indexers first
        id = options["id"]
        if id == "all":
            all_sources = get_source_list()
            total = len(all_sources)
            count = 0
            for source_id in all_sources:
                try:
                    source = Source.objects.get(id=source_id)
                except Source.DoesNotExist:
                    print(f"Source with ID {source_id} does not exist")
                    source = None
                if source is not None:
                    print(
                        f"old date created for source {source_id}: {source.date_created}"
                    )
                    source_updated = update_date_created(source_id)
                    print(
                        f"new date created for source {source_id}: {source_updated.date_created}"
                    )
                    if count % 100 == 0:
                        print(
                            f"------------------- {count} of {total} sources updated -------------------"
                        )
                    count += 1

        else:
            source = Source.objects.get(id=id)
            print(f"old date created for source {id}: {source.date_created}")
            source_updated = update_date_created(id)
            print(f"new date created for source {id}: {source_updated.date_created}")
