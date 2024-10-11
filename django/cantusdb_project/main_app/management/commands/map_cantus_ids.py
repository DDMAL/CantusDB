"""
This is a (potentially temporary) command to change one Cantus ID to another
Cantus ID. For the moment (October 2024), Cantus Index and Cantus Database are
working out some issues in the process of merging Cantus ID's, so this command
gives us a more fine-grained (but more general than changing them all manually)
approach to changing Cantus ID's.
"""

from django.core.management.base import BaseCommand
import reversion  # type: ignore[import-untyped]

from main_app.models import Chant


class Command(BaseCommand):
    help = "Change one Cantus ID to another Cantus ID."

    def add_arguments(self, parser):
        parser.add_argument(
            "old_cantus_id",
            type=str,
            help="The Cantus ID to change.",
        )
        parser.add_argument(
            "new_cantus_id",
            type=str,
            help="The Cantus ID to change to.",
        )

    def handle(self, *args, **options):
        old_cantus_id = options["old_cantus_id"]
        new_cantus_id = options["new_cantus_id"]
        with reversion.create_revision():
            chants = Chant.objects.filter(cantus_id=old_cantus_id)
            num_chants = chants.count()
            for chant in chants.iterator(chunk_size=1_000):
                chant.cantus_id = new_cantus_id
                chant.save()
            self.stdout.write(
                self.style.SUCCESS(
                    f"Changed {old_cantus_id} to {new_cantus_id} in {num_chants} chants."
                )
            )
            reversion.set_comment(
                f"Changed Cantus ID: {old_cantus_id} to {new_cantus_id}"
            )
