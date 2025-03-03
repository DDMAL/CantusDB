from typing import Any

from django.core.management.base import BaseCommand
from main_app.models import Source


class Command(BaseCommand):
    help = "Make changes to the Source model"

    def handle(self, *args: Any, **kwargs: Any) -> None:

        sources = Source.objects.all()
        for source in sources:
            source.segment_m2m.add(source.segment)
            source.save()

        self.stdout.write(
            self.style.SUCCESS("Successfully updated Source model with segments")
        )
