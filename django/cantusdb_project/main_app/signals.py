import operator
from functools import reduce

from django.contrib.postgres.search import SearchVector
from django.db import models
from django.db.models import Value
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from main_app.models import Chant
from main_app.models import Sequence


@receiver(post_save, sender=Chant)
def update_chant_search_vector(instance, **kwargs):
    """When saving an instance of Chant, update its search vector field."""
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

@receiver(post_save, sender=Chant)
@receiver(post_save, sender=Sequence)
@receiver(post_delete, sender=Chant)
@receiver(post_delete, sender=Sequence)
def update_source_chant_count(instance, **kwargs):
    """When saving or deleting a Chant or Sequence, update its Source's number_of_chants field"""
    source = instance.source
    source.number_of_chants = source.chant_set.count() + source.sequence_set.count()
    source.save()

@receiver(post_save, sender=Chant)
@receiver(post_delete, sender=Chant)
def update_source_melody_count(instance, **kwargs):
    """When saving or deleting a Chant, update its Source's number_of_melodies field"""
    source = instance.source
    source.number_of_melodies = source.chant_set.filter(volpiano__isnull=False).count()
    source.save()

@receiver(post_save, sender=Chant)
@receiver(post_delete, sender=Chant)
def update_next_chant_fields(instance, **kwargs):
    """When saving or deleting a Chant, make sure the next_chant of each chant in the source is up-to-date"""
    source = instance.source
    for chant in source.chant_set.all():
        chant.next_chant = chant.get_next_chant()