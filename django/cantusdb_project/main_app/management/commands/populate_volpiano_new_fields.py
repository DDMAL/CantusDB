import re
from django.core.management.base import BaseCommand
from main_app.models import Chant


class Command(BaseCommand):
    def add_arguments(self, parser):
        pass

    def handle(self, *args, **options):
        chants = Chant.objects.exclude(volpiano=None).order_by("id")
        # the `searchMelody.js` on old cantus makes no reference to the b-flat accidentals ("y", "i", "z")
        # ignore them in volpiano for now
        unwanted_chars = [
            "-",
            "1",
            "2",
            "3",
            "4",
            "5",
            "6",
            "7",
            "?",
            ".",
            " ",
            "y",
            "i",
            "z",
        ]
        i = 0
        # the process might get killed by the time it reaches chant 26066,
        # comment/uncomment the next lines to finish all chants in two shots
        # for chant in chants[:26066]:
        for chant in chants[26066:]:

            # print(f"processing: chant {i}; chant id: {chant.id}")
            # volpiano = chant.volpiano
            # # convert all charactors to lower-case, upper-case letters stand for liquescent of the same pitch
            # volpiano_lower = volpiano.lower()
            # # `)` stands for the lowest `g` note liquescent in volpiano, its 'lower case' is `9`
            # volpiano_notes = volpiano_lower.replace(")", "9")
            # # remove none-note charactors
            # for unwanted_char in unwanted_chars:
            #     volpiano_notes = volpiano_notes.replace(unwanted_char, "")
            # # remove duplicate consecutive chars
            # chant.volpiano_notes = re.sub(r"(.)\1+", r"\1", volpiano_notes)

            print(f"processing: chant {i}; chant id: {chant.id}")
            # if the volpiano_notes field is not empty
            if chant.volpiano_notes:
                # replace "9" (the note G) with the char corresponding to (ASCII(a) - 1)
                chant.volpiano_notes.replace("9", chr(ord("a") - 1))
                # TODO: the letter for the note B is "j", note A is "h", the letter "i" is skipped
                # maybe need to address this by moving everything above A down one letter

                # `intervals` records the difference between two adjacent notes
                intervals = []
                for j in range(1, len(chant.volpiano_notes)):
                    intervals.append(
                        ord(chant.volpiano_notes[j]) - ord(chant.volpiano_notes[j - 1])
                    )
                # convert `intervals` to string
                chant.volpiano_intervals = "".join(
                    [str(interval) for interval in intervals]
                )
                # print(chant.volpiano_intervals)
                # print(chant.volpiano_notes)
                # assert len(chant.volpiano_intervals) == len(chant.volpiano_notes) - 1
                chant.save()
            i += 1
