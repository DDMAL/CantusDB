import operator
from functools import reduce

from django.contrib.postgres.search import SearchVector
from django.db import models
from django.db.models import Value
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

import re

from main_app.models import Chant
from main_app.models import Sequence

@receiver(post_save, sender=Chant)
def on_chant_save(instance, **kwargs):
    update_source_chant_count(instance)
    update_source_melody_count(instance)

    update_chant_search_vector(instance)
    update_volpiano_fields(instance)

@receiver(post_delete, sender=Chant)
def on_chant_delete(instance, **kwargs):
    update_source_chant_count(instance)
    update_source_melody_count(instance)

@receiver(post_save, sender=Sequence)
def on_sequence_save(instance, **kwargs):
    update_source_chant_count(instance)

@receiver(post_delete, sender=Sequence)
def on_sequence_delete(instance, **kwargs):
    update_source_chant_count(instance)


def update_chant_search_vector(instance):
    """When saving an instance of Chant, update its search vector field.
    
    Called in on_chant_save()
    """
    index_components = instance.index_components()
    pk = instance.pk
    search_vectors = []

    for weight, data in index_components.items():
        search_vectors.append(
            SearchVector(
                Value(data, output_field=models.TextField()), weight=weight
            )
        )
    instance.__class__.objects.filter(pk=pk).update(
        search_vector=reduce(operator.add, search_vectors)
    )

def update_source_chant_count(instance):
    """When saving or deleting a Chant or Sequence, update its Source's number_of_chants field
    
    Called in on_chant_save(), on_chant_delete(), on_sequence_save() and on_sequence_delete()
    """

    source = instance.source
    source.number_of_chants = source.chant_set.count() + source.sequence_set.count()
    source.save()

def update_source_melody_count(instance):
    """When saving or deleting a Chant, update its Source's number_of_melodies field
    
    Called in on_chant_save() and on_chant_delete()
    """
    source = instance.source
    source.number_of_melodies = source.chant_set.filter(volpiano__isnull=False).count()
    source.save()

def update_volpiano_fields(instance):
    """When saving a Chant, make sure the chant's volpiano_notes and volpiano_intervals are up-to-date
    
    Called in on_chant_save()
    """
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

        # `intervals` records the difference between two adjacent notes.
        # Note that intervals are encoded by counting the number of scale
        # steps between adjacent notes: an ascending second is thus encoded
        # as "1"; a descending third is encoded "-2", and so on.
        intervals = []
        for j in range(1, len(volpiano_notes)):
            intervals.append(ord(volpiano_notes[j]) - ord(volpiano_notes[j - 1]))
        # convert `intervals` to str
        volpiano_intervals = "".join([str(interval) for interval in intervals])
        return volpiano_intervals

    if instance.volpiano is None:
        return

    volpiano_notes = generate_volpiano_notes(
        instance.volpiano
    )
    volpiano_intervals = generate_volpiano_intervals(
        volpiano_notes
    )

    Chant.objects.filter(id=instance.id).update(
        volpiano_notes=volpiano_notes,
        volpiano_intervals=volpiano_intervals,
    )

