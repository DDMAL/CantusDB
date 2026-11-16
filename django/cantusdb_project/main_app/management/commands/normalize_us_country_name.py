from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Retired: country normalization is now performed by the Getty country migration."

    def handle(self, *args: str, **options: str) -> None:
        self.stdout.write(
            "Countries now use the Getty catalogue. Run manage.py migrate."
        )
