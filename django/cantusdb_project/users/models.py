from django.db import models
from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    institution = models.CharField(max_length=255, blank=True, null=True)
    city = models.CharField(max_length=255, blank=True, null=True)
    country = models.CharField(max_length=255, blank=True, null=True)
    website = models.URLField(blank=True, null=True)

    def __str__(self):
        return f'{self.first_name} {self.last_name}'