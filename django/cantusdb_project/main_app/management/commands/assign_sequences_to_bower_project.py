"""
This command is meant to be used one time toward solving issue
1542, assigning chants and sequences, where necessary, to their appropriate
"project".

This command assigns sequences to the Bower project. Chants 
(in non-Bower sources) currently have
project. 

Note: This command can only be run *after* the Bower project has been created
in the database through the Admin interface.

Note: This command is designed to be run once in order to complete the necessary
data migrations with the introduction of the Project model. It is not intended
for multiple runs.
"""

from django.core.management.base import BaseCommand
from main_app.models import Project, Sequence


class Command(BaseCommand):
    help = "Assigns all sequences to the Bower project."

    def handle(self, *args, **options):
        sequences = Sequence.objects.all()
        bower_project = Project.objects.get(name="Clavis Sequentiarum")
        if not bower_project:
            self.stdout.write(
                self.style.ERROR(
                    "The Bower project does not exist. Please create it in the Admin interface."
                )
            )
            return
        sequences.update(project=bower_project)
        self.stdout.write(
            self.style.SUCCESS(
                f"All sequences have been assigned to the {bower_project} project."
            )
        )
