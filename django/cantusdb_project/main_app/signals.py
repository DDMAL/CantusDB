import operator
from functools import reduce

import reversion

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


@receiver(post_save, sender=Chant)
def on_chant_save(instance, **kwargs) -> None:
    update_source_chant_count(instance)
    update_source_melody_count(instance)

    # The incipit is regenerated before the search vector is rebuilt, because
    # the vector indexes the incipit: building it first would leave the stored
    # vector holding text the row no longer contains (issue #1803).
    update_chant_incipit_field(instance)
    update_chant_search_vector(instance)
    update_volpiano_fields(instance)


@receiver(post_delete, sender=Chant)
def on_chant_delete(instance, **kwargs) -> None:
    update_source_chant_count(instance)
    update_source_melody_count(instance)


@receiver(post_save, sender=Sequence)
def on_sequence_save(instance, **kwargs) -> None:
    update_source_chant_count(instance)
    update_sequence_incipit_field(instance)


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


def update_volpiano_fields(instance) -> None:
    """When saving a Chant, make sure the chant's volpiano_notes and volpiano_intervals are up-to-date

    Called in on_chant_save()
    """

    if instance.volpiano is None:
        return

    volpiano_notes = generate_volpiano_notes(instance.volpiano)
    volpiano_intervals = generate_volpiano_intervals(volpiano_notes)

    Chant.objects.filter(id=instance.id).update(
        volpiano_notes=volpiano_notes,
        volpiano_intervals=volpiano_intervals,
    )


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

    A curated incipit is protected from an unproofread full text (issue
    #1803): while the standardized-spelling full text is still unproofread,
    an existing incipit is left alone, so adding a rough full text to a
    hand-entered incipit no longer clobbers it. A chant with no incipit yet
    always gets one, and once the full text is proofread the incipit tracks
    it again - which is also the only way a wrong incipit can be corrected,
    since `incipit` is read-only in the admin and absent from both chant
    forms.

    Args:
        chant (Chant): The chant from the database whose `incipit` field
        is to be updated
    """
    fulltext: Optional[str] = chant.manuscript_full_text_std_spelling
    # many chants in the database have only an incipit - we should only update
    # the incipit if the chant has a fulltext, just in case a chant manages to
    # get saved without a fulltext somehow
    if not fulltext:
        return
    # A NULL proofread flag counts as unproofread. On a chant loaded by a
    # deferred queryset this costs one extra query to fetch the flag, which is
    # the correct trade: guessing would either freeze or clobber the incipit.
    if chant.incipit and not chant.manuscript_full_text_std_proofread:
        return
    new_incipit: str = generate_incipit(fulltext)
    Chant.objects.filter(id=chant.id).update(incipit=new_incipit)
    # Bring the in-memory instance in step with the row we just wrote, so the
    # search vector built next indexes the incipit the row actually holds.
    chant.incipit = new_incipit
    # `.update()` bypasses save hooks, so the active revision would otherwise
    # keep the pre-sync incipit. Re-record the instance (now carrying the
    # regenerated incipit) rather than calling save() again, which would
    # recurse back through this signal. The guards mirror django-reversion's
    # own post_save receiver: an unregistered model would raise
    # RegistrationError, and a revision opened with `manage_manually=True` has
    # deliberately opted out of automatic versioning.
    if (
        reversion.is_registered(Chant)
        and reversion.is_active()
        and not reversion.is_manage_manually()
    ):
        reversion.add_to_revision(chant)


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
