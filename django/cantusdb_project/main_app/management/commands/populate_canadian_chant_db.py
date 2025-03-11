from typing import Any
from django.core.management.base import BaseCommand
from main_app.models import Source, Segment


class Command(BaseCommand):
    def handle(self, *args: Any, **options: Any) -> None:
        ccdb_segment = Segment.objects.get(name="Canadian Chant Database")
        canadian_sources = Source.objects.filter(holding_institution__country="Canada")
        for source in canadian_sources:
            source.segment_m2m.add(ccdb_segment)
            source.save()
