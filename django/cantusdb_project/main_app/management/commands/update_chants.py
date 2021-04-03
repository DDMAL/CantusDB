from django.core.management.base import BaseCommand, CommandError
from main_app.models import Chant
import sys

class Command(BaseCommand):
    def add_arguments(self, parser):
        pass

    def handle(self, *args, **options):
        no_of_chants = Chant.objects.all().count()
        i = 0
        for chant in Chant.objects.all().iterator():
            chant.save()
            i += 1
            percent_done = round(((i / no_of_chants) * 100), 6)
            sys.stdout.write(f"\r{percent_done} %")
