from django.core.management.base import BaseCommand

from main_app.models import Institution

US_NAME_VARIANTS = ["USA", "United States"]
CANONICAL_NAME = "United States of America"


class Command(BaseCommand):
    help = "Normalize US country name variants to 'United States of America'"

    def handle(self, *args: str, **options: str) -> None:
        updated = Institution.objects.filter(country__in=US_NAME_VARIANTS).update(
            country=CANONICAL_NAME
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Updated {updated} institution(s) to '{CANONICAL_NAME}'."
            )
        )
