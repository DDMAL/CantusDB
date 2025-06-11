from django.core.management.base import BaseCommand
from main_app.models import Source, Chant


class Command(BaseCommand):
    help = "Updates the 'other_fields_proofread' field to True for chants in published sources."

    def add_arguments(self, parser):
        parser.add_argument(
            "--source_ids",
            nargs="+",
            type=int,
            help="Optional list of source IDs to update.",
        )

    def handle(self, *args, **options):
        source_ids = options["source_ids"]
        published_sources = Source.objects.filter(published=True)

        if source_ids:
            published_sources = published_sources.filter(id__in=source_ids)
            if not published_sources.exists():
                self.stdout.write(
                    self.style.WARNING(
                        "No published sources found for the provided IDs."
                    )
                )
                return

        updated_chants_count = 0
        chunk_size = 500  # Process in smaller chunks to avoid memory issues

        for source in published_sources.iterator():
            self.stdout.write(f"Processing source: {source} (ID: {source.id})")

            chant_count = 0
            # Use iterator to avoid loading all chants into memory at once
            for chant in Chant.objects.filter(source=source).iterator(
                chunk_size=chunk_size
            ):
                chant.other_fields_proofread = True
                chant.save()  # This ensures signals are fired
                chant_count += 1
                updated_chants_count += 1

                # Progress reporting every 100 chants
                if chant_count % 100 == 0:
                    self.stdout.write(
                        f"  Processed {chant_count} chants for this source..."
                    )

            self.stdout.write(
                self.style.SUCCESS(
                    f"Successfully updated {chant_count} chants for source: {source}"
                )
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Finished updating. Total chants updated: {updated_chants_count}."
            )
        )
