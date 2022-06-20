from django.contrib.postgres.search import SearchVectorField
from django.db import models
from main_app.models.base_chant import BaseChant
from users.models import User


class Sequence(BaseChant):
    """The model for chants

    Both Chant and Sequence must have the same fields, otherwise errors will be raised
    when a user searches for chants/sequences in the database. Thus, all fields,
    properties and attributes should be declared in BaseChant in order to keep the two
    models harmonized, even if only one of the two models uses a particular field.
    """
    
    pass