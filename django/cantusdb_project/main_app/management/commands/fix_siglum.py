from django.core.management.base import BaseCommand, CommandError
from pprint import pprint
from main_app.models import Source


class Command(BaseCommand):
    def add_arguments(self, parser):
        pass

    def handle(self, *args, **options):
        sources = Source.objects.all()
        
        for source in sources:
            siglum = source.json_info["field_siglum"]["und"][0]["value"]
            source.siglum = siglum
            source.save()
