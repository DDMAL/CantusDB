from main_app.models import Source
from django.core.management.base import BaseCommand

# `python manage.py python manage.py populate_chant_and_melody_counts`

class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        sources = Source.objects.all()
        for source in sources:
            source.number_of_chants = source.chant_set.count() + source.sequence_set.count()
            source.number_of_melodies = source.chant_set.filter(volpiano__isnull=False).count()
            source.save()