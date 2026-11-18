from typing import Any
from django.conf import settings
from django.core.management.base import BaseCommand
from main_app.countries import find_country
from main_app.models import Source, Segment


class Command(BaseCommand):
    def handle(self, *args: Any, **options: Any) -> None:
        ccdb_segment = Segment.objects.get(id=settings.CCDB_SEGMENT_ID)
        canada = find_country("Canada")
        if canada is None:
            return
        canadian_sources = Source.objects.filter(holding_institution__country=canada)
        for source in canadian_sources:
            source.segment_m2m.add(ccdb_segment)
            source.save()
