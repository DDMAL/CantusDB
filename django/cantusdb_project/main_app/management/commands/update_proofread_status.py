from django.core.management.base import BaseCommand
from main_app.models import Source, Chant


class Command(BaseCommand):
    help = "Updates proofread-related fields to True for chants in published sources."

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

        for source in published_sources:
            chants_to_update = Chant.objects.filter(source=source)
            for chant in chants_to_update:
                chant.other_fields_proofread = True
                chant.manuscript_full_text_std_proofread = True
                chant.manuscript_full_text_proofread = True
                chant.volpiano_proofread = True
                chant.save()
                updated_chants_count += 1

            self.stdout.write(
                self.style.SUCCESS(f"Successfully updated chants for source: {source}")
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Finished updating. Total chants updated: {updated_chants_count}."
            )
        )
