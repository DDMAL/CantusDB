from django.core.management.base import BaseCommand
from main_app.models import (
    Source,
)
import requests, json
from datetime import datetime
from django.utils import timezone
from typing import Optional


def convert_epoch_to_date_time(epoch: str) -> Optional[datetime]:
    try:
        epoch_time = float(epoch)
        datetime_str = datetime.fromtimestamp(epoch_time)
        datetime_obj = timezone.make_aware(datetime_str, timezone.utc)
    except (ValueError, TypeError) as e:
        print(f"Error converting epoch time: {e}")
        return None
    return datetime_obj


def update_date_created(source: Source) -> Source:
    url = f"http://cantus.uwaterloo.ca/json-node/{source.id}"
    response = requests.get(url)
    json_response = json.loads(response.content)
    try:
        date_created_epoch = json_response["created"]
    except (KeyError, TypeError):
        return source
    datetime_str = convert_epoch_to_date_time(date_created_epoch)
    if datetime_str is not None:
        source.date_created = datetime_str
        source.save()
    return source


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            "id",
            type=str,
            help="update one source (<source_id>) or update all sources ('all')",
        )

    def handle(self, *args, **options):
        # before running this, run sync_indexers first
        id = options["id"]
        if id == "all":
            all_sources = Source.objects.all()
            total = len(all_sources)
            count = 0
            for source in all_sources:
                print(f"old date created for source {source.id}: {source.date_created}")
                source_updated = update_date_created(source)
                print(
                    f"new date created for source {source.id}: {source_updated.date_created}"
                )
                if count % 100 == 0:
                    print(
                        f"------------------- {count} of {total} sources updated -------------------"
                    )
                count += 1
                print()

        else:
            source = Source.objects.get(id=id)
            print(f"old date created for source {id}: {source.date_created}")
            source_updated = update_date_created(source)
            print(f"new date created for source {id}: {source_updated.date_created}")
