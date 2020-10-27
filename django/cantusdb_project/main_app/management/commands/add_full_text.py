from django.core.management.base import BaseCommand, CommandError
from main_app.models import Chant


class Command(BaseCommand):
    def add_arguments(self, parser):
        pass

    def handle(self, *args, **options):
        chants = Chant.objects.all()
        count = chants.count()
        i = 0

        for chant in chants.iterator():
            i += 1
            try:
                manuscript_full_text_std_spelling = chant.json_info["body"]["und"][0][
                    "value"
                ]
            except:
                manuscript_full_text_std_spelling = None
            try:
                manuscript_full_text = chant.json_info["field_full_text_ms"]["und"][0][
                    "value"
                ]
            except:
                manuscript_full_text = None
            chant.manuscript_full_text = manuscript_full_text
            chant.manuscript_full_text_std_spelling = manuscript_full_text_std_spelling
            chant.save()
            print((i / count) * 100)
