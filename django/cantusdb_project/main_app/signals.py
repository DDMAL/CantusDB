import operator
from functools import reduce

from django.contrib.postgres.search import SearchVector
from django.db import models
from django.db.models import Value
from django.db.models.signals import post_save
from django.dispatch import receiver

from main_app.models import Chant


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
