import re
from django.core.management.base import BaseCommand
from main_app.models import Chant


# Run with `python manage.py populate_volpiano_new_fields`.
def generate_volpiano_notes(volpiano):
    """
    Populate the ``volpiano_notes`` field of the ``Chant`` model

    This field is used for melody search

    Args:
        volpiano (str): The content of ``chant.volpiano``

    Returns:
        str: Volpiano str with non-note chars and duplicate consecutive notes removed
    """
    # unwanted_chars are non-note chars, including the clefs, barlines, and accidentals etc.
    # the `searchMelody.js` on old cantus makes no reference to the b-flat accidentals ("y", "i", "z")
    # so put them in unwanted chars for now
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
    # convert all charactors to lower-case, upper-case letters stand for liquescent of the same pitch
    volpiano_lower = volpiano.lower()
    # `)` stands for the lowest `g` note liquescent in volpiano, its 'lower case' is `9`
    volpiano_notes = volpiano_lower.replace(")", "9")
    # remove none-note charactors
    for unwanted_char in unwanted_chars:
        volpiano_notes = volpiano_notes.replace(unwanted_char, "")
    # remove duplicate consecutive chars
    volpiano_notes = re.sub(r"(.)\1+", r"\1", volpiano_notes)
    return volpiano_notes


def generate_volpiano_intervals(volpiano_notes):
    """
    Populate the ``volpiano_intervals`` field of the ``Chant`` model

    This field is used for melody search when searching for transpositions

    Args:
        volpiano_notes (str): The content of ``chant.volpiano_notes``,
        populated by the ``generate_volpiano_notes`` function

    Returns:
        str: A str of digits, recording the intervals between adjacent notes
    """
    # replace '9' (the note G) with the char corresponding to (ASCII(a) - 1), because 'a' denotes the note A
    volpiano_notes = volpiano_notes.replace("9", chr(ord("a") - 1))
    # we model the interval between notes using the difference between the ASCII codes of corresponding letters
    # the letter for the note B is "j" (106), note A is "h" (104), the letter "i" (105) is skipped
    # move all notes above A down by one letter
    volpiano_notes = list(volpiano_notes)
    for j, note in enumerate(volpiano_notes):
        if ord(note) >= 106:
            volpiano_notes[j] = chr(ord(note) - 1)

    # `intervals` records the difference between two adjacent notes
    intervals = []
    for j in range(1, len(volpiano_notes)):
        intervals.append(ord(volpiano_notes[j]) - ord(volpiano_notes[j - 1]))
    # convert `intervals` to str
    volpiano_intervals = "".join([str(interval) for interval in intervals])
    return volpiano_intervals


class Command(BaseCommand):
    """
    This command populates the ``volpiano_notes`` and ``volpiano_intervals`` fields of the ``Chant`` model

    Run by ``python manage.py populate_volpiano_new_fields``
    """

    def add_arguments(self, parser):
        pass

    def handle(self, *args, **options):
        # only process chants that have melodies
        chants = Chant.objects.exclude(volpiano=None).order_by("id")
        i = 0
        # the process might get killed by the time it reaches chant 26066,
        # comment/uncomment the next lines to finish all chants in two shots
        for chant in chants[26066:]:
            # for chant in chants[:26066]:
            print(f"processing: chant {i}; chant id: {chant.id}")
            chant.volpiano_notes = generate_volpiano_notes(chant.volpiano)

            # if the volpiano_notes field is not empty, compute the intervals
            if chant.volpiano_notes:
                chant.volpiano_intervals = generate_volpiano_intervals(
                    chant.volpiano_notes
                )
            chant.save()
            i += 1
