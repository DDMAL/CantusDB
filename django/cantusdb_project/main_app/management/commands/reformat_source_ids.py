"""
A command designed to do a one-time reformatting of DACT IDs and Fragment
IDs in the database. 

Fragment IDs should be of the form "F-XXXX" where XXXX is some alphanumeric.
Fragment IDs are currently assumed to be in the form "F-XXXX" or "XXXX".
DACT IDs should be of the form "D:0XXXX" where XXXX is the Fragment ID alphanumeric. 
DACT IDs are currently assumed to be in the form "0XXXX" or  "D-0XXXX".

This command simply adds the prefix "F-" to all Fragment IDs and "D:" to all
DACT IDs where they are missing.
"""

from django.core.management.base import BaseCommand

from main_app.models import Source


class Command(BaseCommand):
    help = "Reformat DACT IDs and Fragment IDs in the database."

    def handle(self, *args, **options):
        sources = Source.objects.all()
        for source in sources:
            if source.dact_id:
                if len(source.dact_id) == 5 and source.dact_id.startswith("0"):
                    source.dact_id = f"D:{source.dact_id}"
                elif len(source.dact_id) == 7 and source.dact_id.startswith("D-0"):
                    source.dact_id = f"D:{source.dact_id[2:]}"
                else:
                    self.stdout.write(
                        self.style.WARNING(
                            f"{source.id} | DACT ID {source.dact_id} is not in the correct format."
                        )
                    )
            if source.fragmentarium_id:
                if len(source.fragmentarium_id) == 4:
                    source.fragmentarium_id = f"F-{source.fragmentarium_id}"
                elif len(
                    source.fragmentarium_id
                ) == 6 and source.fragmentarium_id.startswith("F-"):
                    pass
                else:
                    self.stdout.write(
                        self.style.WARNING(
                            f"{source.id} | Fragment ID {source.fragmentarium_id} is not in the correct format."
                        )
                    )
            source.save()
