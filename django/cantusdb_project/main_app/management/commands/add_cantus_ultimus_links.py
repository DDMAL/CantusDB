from main_app.models import Source
from django.core.management.base import BaseCommand

# This management command goes through all the chants belonging to the specified manuscript
# and adds a link to the corresponding page on Cantus Ultimus where a user can view the folio
# of that manuscript. If the source is available on Cantus Ultimus, this script assumes its
# ID there is the same as its ID on CantusDB.

# This command only works for sources containing chants (i.e. sources in the CANTUS segment,
# and not sources in the Bower segment which contain sequence objects as opposed to chant
# objects).

# run with `python manage.py add_cantus_ultimus_links <source_id>`


def update_image_link_for_chant(chant):
    folio = chant.folio
    number = chant.c_sequence
    source = chant.source.id
    cantus_ultimus_link = (
        f"https://cantus.simssa.ca/manuscript/{source}/?folio={folio}&chant={number}"
    )
    chant.image_link = cantus_ultimus_link
    chant.save()


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            "source_id",
            type=int,
            help="This command attaches Cantus Ultimus links to chants in the source with the specified ID",
        )

    def handle(self, *args, **kwargs):
        source_id = kwargs["source_id"]
        source = Source.objects.get(id=source_id)

        # update the link for the entire source
        print("\nUpdating image link for source:", source)
        source.image_link = f"https://cantus.simssa.ca/manuscript/{source_id}"
        source.save()
        print("Source image link updated successfully!\n")

        # update the links for all the chants
        chants = source.chant_set.all()
        print(f"Updating image links for {chants.count()} chants...")
        counter = 0
        for chant in chants:
            try:
                update_image_link_for_chant(chant)
            except Exception as exc:
                print(
                    f"Encountered error while adding image link to chant {counter}:",
                    chant,
                )
                print(exc)

            counter += 1
            if counter % 100 == 0:
                print(f"  just finished chant {counter}")

        print("All chant image links updated successfully!\n")
