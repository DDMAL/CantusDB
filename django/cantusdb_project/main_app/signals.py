from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db.models import Value
from django.contrib.postgres.search import SearchVector
from functools import reduce
from django.db import models
from django.conf import settings
from main_app.models import Chant
import operator

@receiver(post_save, sender=Chant)
def on_save(instance, **kwargs):
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
