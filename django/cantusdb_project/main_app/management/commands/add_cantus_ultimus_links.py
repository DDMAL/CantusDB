from main_app.models import Source
from django.core.management.base import BaseCommand
import requests
from requests import Response

# This management command goes through all the chants belonging to the specified source
# and adds a link to the corresponding page on Cantus Ultimus where a user can view the folio
# of that source. If the source is available on Cantus Ultimus, this script assumes its
# ID there is the same as its ID on CantusDB.

# This command only works for sources containing chants (i.e. sources in the CANTUS segment,
# and not sources in the Bower segment which contain sequence objects as opposed to chant
# objects).

# If a source source argument is not provided, the command will iterate through each source
# in the database, see if there is a corresponding page on Cantus Ultimus, and update the
# image_link_cantus_ultimus field in the source model along with the image_link field of
# all the chants in the source.

# run with `python manage.py add_cantus_ultimus_links <source_id>`


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            "source_id",
            nargs="?",
            type=int,
            default=None,
            help="This command attaches Cantus Ultimus links to chants in the source with the specified ID",
        )

    def handle(self, *args, **kwargs):
        CHUNK_SIZE = 500
        source_id: int = kwargs["source_id"]
        if source_id:  # update links for a specified source
            source = Source.objects.get(id=source_id)
            try:
                response: Response = requests.get(
                    f"https://cantus.simssa.ca/manuscript/{source_id}", timeout=10
                )
            except (TimeoutError, ConnectionError) as e:
                self.stdout.write(self.style.ERROR(f"{e} for source: {source_id}"))

            # We expect a 404 response if the source doesn't exist on Cantus Ultimus
            if response.status_code == 200:
                # update the link for the entire source
                self.stdout.write(f"\nUpdating image link for source: {source}")
                source.exists_on_cantus_ultimus = True
                source.save()
                self.stdout.write(
                    self.style.SUCCESS("Source image link updated successfully!\n")
                )

                # update the links for all the chants
                chants = source.chant_set.all()
                self.stdout.write(
                    f"Updating image links for {chants.count()} chants..."
                )
                counter = 0
                for chant in chants:
                    try:
                        self.update_image_link_for_chant(chant)
                    except Exception as exc:
                        self.stdout.write(
                            self.style.ERROR(
                                f"Encountered error while adding image link to chant {counter}: {chant}",
                            )
                        )
                        self.stdout.write(exc)
                    counter += 1
                    if counter % 100 == 0:
                        self.stdout.write(f"  just finished chant {counter}")
                self.stdout.write(
                    self.style.SUCCESS("All chant image links updated successfully!\n")
                )
            else:
                self.stdout.write(
                    self.style.NOTICE(
                        f"source {source_id} doesn't exist on Cantus Ultimus\n"
                    )
                )

        else:  # No source parameter provided, update all sources
            sources = Source.objects.filter(segment=4063)
            for source in sources:
                try:
                    response: Response = requests.get(
                        f"https://cantus.simssa.ca/manuscript/{source.id}", timeout=10
                    )
                except (TimeoutError, ConnectionError) as e:
                    self.stdout.write(self.style.ERROR(f"{e} for source: {source.id}"))
                # We expect a 404 response if the source doesn't exist on Cantus Ultimus
                if response.status_code == 200:

                    # update the link for the entire source
                    self.stdout.write(f"\nUpdating image link for source: {source}")
                    source.exists_on_cantus_ultimus = True
                    source.save()
                    self.stdout.write(
                        self.style.SUCCESS("Source image link updated successfully!\n")
                    )

                    # update the links for all the chants
                    chants = source.chant_set.all()
                    self.stdout.write(
                        f"Updating image links for {chants.count()} chants..."
                    )

                    counter = 0
                    total_chants_count = chants.count()
                    start_index = 0
                    while start_index <= total_chants_count:
                        self.stdout.write(f"processing chunk with {start_index=}")
                        chunk = chants[start_index : start_index + CHUNK_SIZE]
                        for chant in chunk:
                            try:
                                self.update_image_link_for_chant(chant)
                            except Exception as exc:
                                self.stdout.write(
                                    self.style.ERROR(
                                        f"Encountered error while adding image link to chant {counter}: {chant}",
                                    )
                                )
                                self.stdout.write(exc)
                            counter += 1
                            if counter % 100 == 0:
                                self.stdout.write(f"just finished chant {counter}")
                        del chunk  # make sure we don't use too much RAM
                        start_index += CHUNK_SIZE

                    self.stdout.write(
                        self.style.SUCCESS(
                            "All chant image links updated successfully!\n"
                        )
                    )
                else:
                    self.stdout.write(
                        self.style.NOTICE(
                            f"source {source.id} doesn't exist on Cantus Ultimus\n"
                        )
                    )

    def update_image_link_for_chant(self, chant):
        folio = chant.folio
        number = chant.c_sequence
        source = chant.source.id
        try:
            response: Response = requests.get(
                f"https://cantus.simssa.ca/manuscript/{source}/?folio={folio}&chant={number}",
                timeout=10,
            )
        except (TimeoutError, ConnectionError) as e:
            self.stdout.write(self.style.ERROR(f"{e} for source: {chant.id}"))

        # We expect a 404 response if the source doesn't exist on Cantus Ultimus
        if response.status_code == 200:
            cantus_ultimus_link = f"https://cantus.simssa.ca/manuscript/{source}/?folio={folio}&chant={number}"
            chant.image_link = cantus_ultimus_link
            chant.save()
        else:
            self.stdout.write(
                self.style.NOTICE(
                    f"chant {chant.id}, folio {folio}, number {number} doesn't exist on Cantus Ultimus\n"
                )
            )
