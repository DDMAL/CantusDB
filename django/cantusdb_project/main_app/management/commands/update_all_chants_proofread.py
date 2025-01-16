from django.core.management.base import BaseCommand
from main_app.models import Source
from django.db.models import Q


class Command(BaseCommand):
    help = "Update all sources by recalculating the all_chants_proofread status"

    def handle(self, *args, **options):
        sources = Source.objects.all()
        for source in sources:
            # Checks if all chants in the source have their manuscript full text fields proofread
            # Ignores the volpiano_proofread field for this check
            all_proofread = not source.chant_set.filter(
                Q(manuscript_full_text_proofread=False)
                | Q(manuscript_full_text_std_proofread=False)
            ).exists()
            source.all_chants_proofread = all_proofread
            source.save(update_fields=["all_chants_proofread"])

        self.stdout.write(
            self.style.SUCCESS(f"Successfully updated {sources.count()} sources")
        )
