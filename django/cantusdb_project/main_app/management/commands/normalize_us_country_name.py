from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Retired: country normalization is now performed by the institution country migration."

    def handle(self, *args: str, **options: str) -> None:
        self.stdout.write(
            "Institution countries now use shared country records. Run manage.py migrate."
        )
