from main_app.models import Source
from django.core.management.base import BaseCommand

# Run with `python manage.py populate_chant_and_melody_counts`.
# This command populates the `number_of_chants` amd `number_of_melodies` fields of the source model.
# Those fields appear on the source-list page and are expensive to calculate on the fly.
# This command should ideally be run only once when initially setting up the website.
# After that, the receivers in `signals.py` should update the fields automatically when a chant/sequence is changed.


class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        sources = Source.objects.all()
        for source in sources:
            source.number_of_chants = (
                source.chant_set.count() + source.sequence_set.count()
            )
            source.number_of_melodies = source.chant_set.filter(
                volpiano__isnull=False
            ).count()
            source.save()
