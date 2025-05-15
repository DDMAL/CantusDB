from django.core.management.base import BaseCommand
from django.db import reset_queries

from main_app.models import Source, ProofreadingStats


class Command(BaseCommand):
    help = (
        "Update ProofreadingStats for each Source with individual field-level progress"
    )

    def handle(self, *args, **options):
        self.stdout.write("Updating proofreading stats...")

        sources = Source.objects.all().only("id")

        for source_obj in sources.iterator():
            self.stdout.write(self.style.NOTICE(f"Processing source {source_obj.id}"))

            ProofreadingStats.objects.calculate_and_update_for_source(source_obj)

            reset_queries()
        self.stdout.write(
            self.style.SUCCESS("Proofreading stats updated successfully!")
        )
