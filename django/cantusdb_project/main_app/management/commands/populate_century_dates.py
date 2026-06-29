from django.core.management.base import BaseCommand

from main_app.century_dates import century_name_to_dates
from main_app.models.century import Century


class Command(BaseCommand):
    help = "Populate min_date and max_date on Century objects from their names."

    def handle(self, *args, **options):
        updated = 0
        skipped = []

        for century in Century.objects.filter(min_date__isnull=True, max_date__isnull=True):
            dates = century_name_to_dates(century.name)
            if dates:
                century.min_date, century.max_date = dates
                century.save(update_fields=["min_date", "max_date"])
                updated += 1
            else:
                skipped.append(century.name)

        self.stdout.write(self.style.SUCCESS(f"Updated {updated} centuries."))
        if skipped:
            self.stdout.write(self.style.WARNING(f"Could not parse {len(skipped)} centuries:"))
            for name in skipped:
                self.stdout.write(f"  - {name}")
