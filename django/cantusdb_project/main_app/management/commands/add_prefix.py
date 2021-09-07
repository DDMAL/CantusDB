from django.core.management.base import BaseCommand, CommandError

# from pprint import pprint
from main_app.models import Feast


class Command(BaseCommand):
    def add_arguments(self, parser):
        pass

    def handle(self, *args, **options):
        feasts = Feast.objects.all()

        for feast in feasts:
            if feast.feast_code:
                feast.prefix = str(feast.feast_code)[0:2]
                feast.save()
                print(feast.prefix)
