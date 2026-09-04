import operator
from functools import reduce

from django.contrib.postgres.search import SearchVector
from django.db import models
from django.db.models import Q, Value
from django.db.models.signals import m2m_changed, post_delete, post_save
from django.dispatch import receiver

from typing import Optional

import re

from main_app.models import Chant
from main_app.models import Sequence
from main_app.models import Feast
from main_app.models import Century, Institution, Notation, Provenance, Segment, Source
from main_app.models.source_identifier import SourceIdentifier
from main_app.source_search import (
    CONTRIBUTOR_RELATIONS,
    M2M_SEARCH_RELATIONS,
    rebuild_source_search_vectors,
    update_source_search_vector,
)
from users.models import User


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


@receiver(post_save, sender=Source)
def on_source_save(instance, **kwargs) -> None:
    """Keep the stored public-metadata search document current."""
    update_source_search_vector(instance.pk)


@receiver(post_save, sender=SourceIdentifier)
@receiver(post_delete, sender=SourceIdentifier)
def on_source_identifier_change(instance, **kwargs) -> None:
    update_source_search_vector(instance.source_id)


def _rebuild_sources(queryset) -> None:
    rebuild_source_search_vectors(queryset.values_list("pk", flat=True).distinct())


@receiver(post_save, sender=Institution)
def on_institution_save(instance, **kwargs) -> None:
    _rebuild_sources(Source.objects.filter(holding_institution=instance))


@receiver(post_save, sender=Provenance)
def on_provenance_save(instance, **kwargs) -> None:
    _rebuild_sources(Source.objects.filter(provenance=instance))


@receiver(post_save, sender=Century)
def on_century_save(instance, **kwargs) -> None:
    _rebuild_sources(Source.objects.filter(century=instance))


@receiver(post_save, sender=Notation)
def on_notation_save(instance, **kwargs) -> None:
    _rebuild_sources(Source.objects.filter(notation=instance))


@receiver(post_save, sender=Segment)
def on_segment_save(instance, **kwargs) -> None:
    _rebuild_sources(
        Source.objects.filter(Q(segment=instance) | Q(segment_m2m=instance))
    )


@receiver(post_save, sender=User)
def on_contributor_save(instance, **kwargs) -> None:
    contributor_filter = Q()
    for relation in CONTRIBUTOR_RELATIONS:
        contributor_filter |= Q(**{relation: instance})
    _rebuild_sources(Source.objects.filter(contributor_filter))


def _on_source_search_relation_change(instance, action, **kwargs) -> None:
    if action in {"post_add", "post_remove", "post_clear"}:
        update_source_search_vector(instance.pk)


for _relation in M2M_SEARCH_RELATIONS:
    m2m_changed.connect(
        _on_source_search_relation_change,
        sender=getattr(Source, _relation).through,
        dispatch_uid=f"source_search_{_relation}",
    )


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
