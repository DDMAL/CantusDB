import re
from django.core.management.base import BaseCommand
from main_app.models import Chant


class Command(BaseCommand):
    def add_arguments(self, parser):
        pass

    def handle(self, *args, **options):
        chants = Chant.objects.exclude(volpiano=None).order_by("id")
        unwanted_chars = ["-", "1", "2", "3", "4", "5", "6", "7", "?", ".", " "]
        i = 0
        for chant in chants:
            print(f"processing: chant {i}; chant id: {chant.id}")
            volpiano = chant.volpiano
            # convert all charactors to lower-case, upper-case letters stand for liquescent of the same pitch
            volpiano_lower = volpiano.lower()
            # `)` stands for the lowest `g` note liquescent in volpiano, its 'lower case' is `9`
            volpiano_notes = volpiano_lower.replace(")", "9")
            # remove none-note charactors
            for unwanted_char in unwanted_chars:
                volpiano_notes = volpiano_notes.replace(unwanted_char, "")
            # remove duplicate consecutive chars
            chant.volpiano_notes = re.sub(r"(.)\1+", r"\1", volpiano_notes)
            chant.save()
            i += 1
