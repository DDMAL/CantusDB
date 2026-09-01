import operator
from functools import reduce

from django.contrib.postgres.search import SearchVector
from django.db import models
from django.db.models import Value
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from typing import Optional

import re

from main_app.models import Chant
from main_app.models import Sequence
from main_app.models import Feast
from main_app.models import Source
from main_app.models.base_chant import BaseChant


@receiver(post_save, sender=Chant)
def on_chant_save(instance, **kwargs) -> None:
    update_source_chant_count(instance)
    update_source_melody_count(instance)

    update_chant_search_vector(instance)
    update_chant_incipit_field(instance)
    update_volpiano_fields(instance)


@receiver(post_delete, sender=Chant)
def on_chant_delete(instance, **kwargs) -> None:
    update_source_chant_count(instance)
    update_source_melody_count(instance)


@receiver(post_save, sender=Sequence)
def on_sequence_save(instance, **kwargs) -> None:
    update_source_chant_count(instance)
    update_sequence_incipit_field(instance)
    update_volpiano_fields(instance)


@receiver(post_delete, sender=Sequence)
def on_sequence_delete(instance, **kwargs) -> None:
    update_source_chant_count(instance)


@receiver(post_save, sender=Feast)
def on_feast_save(instance, **kwargs) -> None:
    update_prefix_field(instance)


def update_chant_search_vector(instance) -> None:
    """When saving an instance of Chant, update its search vector field.

    Called in on_chant_save()
    """
    index_components = instance.index_components()
    pk = instance.pk
    search_vectors = []

    for weight, data in index_components.items():
        search_vectors.append(
            SearchVector(Value(data, output_field=models.TextField()), weight=weight)
        )
    instance.__class__.objects.filter(pk=pk).update(
        search_vector=reduce(operator.add, search_vectors)
    )


def update_source_chant_count(instance) -> None:
    """When saving or deleting a Chant or Sequence, update its Source's number_of_chants field

    Called in on_chant_save(), on_chant_delete(), on_sequence_save() and on_sequence_delete()
    """

    # When a source is deleted (which in turn calls on_chant_delete() on all of its chants) instance.source does not exist
    try:
        source = instance.source
    except Source.DoesNotExist:
        source = None
    if source is not None:
        source.number_of_chants = source.chant_set.count() + source.sequence_set.count()
        source.save()


def update_source_melody_count(instance) -> None:
    """When saving or deleting a Chant, update its Source's number_of_melodies field

    Called in on_chant_save() and on_chant_delete()
    """

    # When a source is deleted (which in turn calls on_chant_delete() on all of its chants) instance.source does not exist
    try:
        source = instance.source
    except Source.DoesNotExist:
        source = None
    if source is not None:
        source.number_of_melodies = (
            source.chant_set.exclude(volpiano__isnull=True)
            .exclude(volpiano__exact="")
            .count()
        )
        source.save()


def update_volpiano_fields(instance: BaseChant) -> None:
    """When saving a Chant or Sequence, make sure its volpiano_notes,
    volpiano_intervals and chant_range are up-to-date

    chant_range is derived data: whenever a record has volpiano, its range is
    recomputed from that volpiano and whatever was stored is overwritten. A
    stored range that disagrees with the melody is treated as an error to be
    corrected, not as ground truth (#2081 / #1176). Proofread status is
    deliberately not consulted — an unproofread melody is still a better
    description of the ambitus than a range typed by hand.

    Called in on_chant_save() and on_sequence_save()
    """

    if instance.volpiano is None:
        return

    volpiano_notes = generate_volpiano_notes(instance.volpiano)
    volpiano_intervals = generate_volpiano_intervals(volpiano_notes)

    # Write through the queryset rather than the instance so that saving does
    # not re-fire the post_save cascade.
    records = instance.__class__.objects.filter(pk=instance.pk)
    records.update(
        volpiano_notes=volpiano_notes,
        volpiano_intervals=volpiano_intervals,
    )

    chant_range = generate_chant_range(instance.volpiano)
    if not chant_range:
        # A melody that yields no derivable range (no recognized pitches, or a
        # mid-melody clef change) tells us nothing about the ambitus, so the
        # stored value is left alone rather than blanked.
        return

    records.update(chant_range=chant_range)


def generate_volpiano_notes(volpiano) -> str:
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
    unwanted_chars: list[str] = [
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
    volpiano_lower: str = volpiano.lower()
    # `)` stands for the lowest `g` note liquescent in volpiano, its 'lower case' is `9`
    volpiano_notes: str = volpiano_lower.replace(")", "9")
    # remove none-note charactors
    for unwanted_char in unwanted_chars:
        volpiano_notes = volpiano_notes.replace(unwanted_char, "")
    # remove duplicate consecutive chars
    volpiano_notes = re.sub(r"(.)\1+", r"\1", volpiano_notes)
    return volpiano_notes


def generate_volpiano_intervals(volpiano_notes) -> str:
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
    volpiano_notes: str = volpiano_notes.replace("9", chr(ord("a") - 1))
    # we model the interval between notes using the difference between the ASCII codes of corresponding letters
    # the letter for the note B is "j" (106), note A is "h" (104), the letter "i" (105) is skipped
    # move all notes above A down by one letter
    notes_list: list = list(volpiano_notes)
    for j, note in enumerate(notes_list):
        if ord(note) >= 106:
            notes_list[j] = chr(ord(note) - 1)

    # `intervals` records the difference between two adjacent notes.
    # Note that intervals are encoded by counting the number of scale
    # steps between adjacent notes: an ascending second is thus encoded
    # as "1"; a descending third is encoded "-2", and so on.
    intervals: list[int] = []
    for j in range(1, len(notes_list)):
        intervals.append(ord(notes_list[j]) - ord(notes_list[j - 1]))
    volpiano_intervals: str = "".join([str(interval) for interval in intervals])
    return volpiano_intervals


# Volpiano note characters in ascending pitch order. "9" is the lowest note
# (the G below A); the letter "i" is skipped in volpiano (the note B is "j").
VOLPIANO_PITCH_ORDER: str = "9abcdefghjklmnopqrs"

# Volpiano defines exactly two clefs: "1" (G clef) and "2" (F clef). The
# notation has no C-clef character; if one is ever added, listing it here is
# the only change needed. Chants are overwhelmingly notated with the G clef,
# which is what we fall back to for a melody that declares no clef at all.
VOLPIANO_CLEFS: str = "12"
DEFAULT_VOLPIANO_CLEF: str = "1"

# The character that terminates a chant_range string: a volpiano double barline.
VOLPIANO_RANGE_TERMINATOR: str = "4"


def extract_volpiano_clef(volpiano: str) -> Optional[str]:
    """Return the clef a raw volpiano melody is written in.

    Falls back to the G clef when the melody declares no clef. Returns ``None``
    when the melody changes clef partway through: the same note letter denotes
    a different pitch on either side of the change, so no single clef can
    describe the melody's ambitus.

    Args:
        volpiano (str): The content of ``chant.volpiano`` (raw, un-normalized).

    Returns:
        Optional[str]: The clef character, or None if the melody changes clef.
    """
    clefs: set[str] = {char for char in volpiano if char in VOLPIANO_CLEFS}
    if not clefs:
        return DEFAULT_VOLPIANO_CLEF
    if len(clefs) > 1:
        return None
    return clefs.pop()


def generate_chant_range(volpiano: str) -> str:
    """Derive a chant's ``chant_range`` from its raw volpiano.

    The range is itself a short volpiano string of the form
    ``"{clef}-{lowest}-{highest}-4"`` (clef, lowest note, highest note,
    double barline) that renders in the volpiano font as the chant's ambitus.

    The clef is copied from the melody rather than hardcoded, so that a range
    always renders on the same staff as the melody it describes.

    Args:
        volpiano (str): The content of ``chant.volpiano`` (raw, un-normalized).

    Returns:
        str: The ``chant_range`` string, or ``""`` if there are no notes or the
        melody changes clef.
    """
    # Real volpiano fields contain occasional dirty characters — stray
    # punctuation, whitespace, and typos (e.g. a literal "TEST!") — that
    # survive generate_volpiano_notes. Restrict to recognized pitches so the
    # ambitus reflects actual notes and a bad character can't crash a batch.
    present: set[str] = set(generate_volpiano_notes(volpiano))
    pitches: list[str] = [pitch for pitch in VOLPIANO_PITCH_ORDER if pitch in present]
    if not pitches:
        return ""
    clef: Optional[str] = extract_volpiano_clef(volpiano)
    if clef is None:
        # The melody changes clef, so its ambitus cannot be written as a single
        # clef plus two notes. Deriving nothing is better than deriving a range
        # that is confidently wrong.
        return ""
    return f"{clef}-{pitches[0]}-{pitches[-1]}-{VOLPIANO_RANGE_TERMINATOR}"


def update_prefix_field(instance) -> None:
    pk = instance.pk

    if instance.feast_code:
        prefix = str(instance.feast_code)[0:2]
        instance.__class__.objects.filter(pk=pk).update(prefix=prefix)
    else:  # feast_code is None, ""
        instance.__class__.objects.filter(pk=pk).update(prefix="")


def update_chant_incipit_field(chant: Chant) -> None:
    """Update the incipit field of the specified Chant to be the first
    several words of the chant's standardized-spelling fulltext

    Args:
        chant (Chant): The chant from the database whose `incipit` field
        is to be updated
    """
    fulltext: Optional[str] = chant.manuscript_full_text_std_spelling
    if fulltext:  # many chants in the database have only an incipit -
        # we should only update the incipit if the chant has a fulltext,
        # just in case a chant manages to get saved without a fulltext somehow
        new_incipit: str = generate_incipit(fulltext)
        Chant.objects.filter(id=chant.id).update(incipit=new_incipit)


def update_sequence_incipit_field(sequence: Sequence) -> None:
    """Update the incipit field of the specified Sequence to be the first
    several words of the sequence's standardized-spelling fulltext

    Args:
        sequence (Sequence): The sequence from the database whose `incipit`
        field is to be updated
    """
    title: Optional[str] = sequence.title
    if title:  # As of late Feb 2024, no sequences in the database have
        # fulltext, but every sequence has a title, and the value stored in
        # the title field is an incipit.
        incipit: str = title
        Sequence.objects.filter(id=sequence.id).update(incipit=incipit)


def generate_incipit(fulltext: str) -> str:
    """Given the fulltext of a chant or sequence, generate an incipit
    consisting of the first 5 words of the fulltext.

    Args:
        fulltext (str): the full text of a chant or sequence

    Returns:
        str: an incipit - the first five words of the fulltext
    """
    INCIPIT_LENGTH: int = 5  # number of words to include in the new incipit

    fulltext_words: list[str] = fulltext.split(" ")
    incipit_words: list[str] = fulltext_words[:INCIPIT_LENGTH]
    incipit: str = " ".join(incipit_words)
    return incipit
