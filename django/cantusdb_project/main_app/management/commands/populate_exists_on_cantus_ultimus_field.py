from main_app.models import Source
from django.core.management.base import BaseCommand
import requests
from requests import Response

# This management command updates the exists_on_cantus_ultimus field on a single
# Source or all sources. If a source argument is provided, it will check if the
# Source exists on Cantus Ultimus and update exists_on_cantus_ultimus to True if it
# does.

# If no Source argument is provided, it will update all Cantus Segment Sources in
# the database.

# run with `python manage.py add_cantus_ultimus_links <source_id>`


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            "source_id",
            nargs="?",
            type=int,
            default=None,
            help="This command updates the exists_on_cantus_ultimus field for the Source with the specified ID",
        )

    def handle(self, *args, **kwargs):
        source_id: int = kwargs["source_id"]
        if source_id:  # update exists_on_cantus_ultimus for a specified source
            try:
                source: Source = Source.objects.get(id=source_id)
                self.update_exists_on_cantus_ultimus(source)
            except Source.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f"Source {source_id} does not exist")
                )
        else:  # No source argument provided, update all sources
            sources = Source.objects.filter(segment=4063)
            for source in sources:
                self.update_exists_on_cantus_ultimus(source)

    def update_exists_on_cantus_ultimus(self, source: Source) -> None:
        try:
            response: Response = requests.get(
                f"https://cantus.simssa.ca/manuscript/{source.id}", timeout=10
            )
        except (TimeoutError, ConnectionError) as e:
            self.stdout.write(self.style.ERROR(f"{e} for source: {source.id}"))
        # We expect a 404 response if the source doesn't exist on Cantus Ultimus
        if response.status_code == 404:
            self.stdout.write(
                self.style.NOTICE(
                    f"source {source.id} doesn't exist on Cantus Ultimus\n"
                )
            )
            return
        # update the link for the entire source
        self.stdout.write(f"\nUpdating exists_on_cantus_ultimus for source: {source}")
        source.exists_on_cantus_ultimus = True
        source.save()
        self.stdout.write(
            self.style.SUCCESS(
                "Source exists_on_cantus_ultimus updated successfully!\n"
            )
        )
