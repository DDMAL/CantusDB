from django.conf import settings
from django.core.management.base import BaseCommand
from main_app.models import Source, Chant

EXCLUDE = [123766, 123740, 123739, 123738, 123737, 662398, 651162]


class Command(BaseCommand):
    help = "Updates the 'other_fields_proofread' field to True for chants in published sources in the Cantus segment."

    def handle(self, *args, **options):
        # Filter for published sources in the Cantus segment only, excluding sources from EXCLUDE
        published_sources = Source.objects.filter(
            published=True, segment_m2m=settings.CANTUS_SEGMENT_ID
        ).exclude(id__in=EXCLUDE)

        if not published_sources.exists():
            self.stdout.write(
                self.style.WARNING("No published sources found to update.")
            )
            return

        updated_chants_count = 0
        error_count = 0
        chunk_size = 500  # Process in smaller chunks to avoid memory issues

        total_sources = published_sources.count()
        processed_sources = 0

        for source in published_sources.iterator():
            processed_sources += 1
            remaining_sources = total_sources - processed_sources

            self.stdout.write(
                f"Processing source {processed_sources}/{total_sources}: {source} (ID: {source.id}) "
                f"[{remaining_sources} remaining]"
            )

            chant_count = 0
            source_error_count = 0
            # Use iterator to avoid loading all chants into memory at once
            for chant in (
                Chant.objects.filter(source=source)
                .filter(other_fields_proofread=False)
                .iterator(chunk_size=chunk_size)
            ):
                try:
                    chant.other_fields_proofread = True
                    chant.save()  # This ensures signals are fired
                    chant_count += 1
                    updated_chants_count += 1
                except Exception as e:
                    error_count += 1
                    source_error_count += 1
                    self.stdout.write(
                        self.style.WARNING(f"  Error saving chant {chant.id}: {str(e)}")
                    )

                # Progress reporting every 100 chants
                if chant_count % 100 == 0:
                    self.stdout.write(
                        f"  Processed {chant_count} chants for this source..."
                    )

            success_msg = (
                f"Successfully updated {chant_count} chants for source: {source}"
            )
            if source_error_count > 0:
                success_msg += f" ({source_error_count} errors)"

            self.stdout.write(self.style.SUCCESS(success_msg))

        self.stdout.write(
            self.style.SUCCESS(
                f"Finished updating. Total chants updated: {updated_chants_count}."
            )
        )

        if error_count > 0:
            self.stdout.write(
                self.style.WARNING(
                    f"Total errors encountered: {error_count}. "
                    f"Check the log above for details."
                )
            )
