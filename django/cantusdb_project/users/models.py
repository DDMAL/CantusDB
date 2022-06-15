from django.db import models
from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    institution = models.CharField(max_length=255, blank=True, null=True)
    city = models.CharField(max_length=255, blank=True, null=True)
    country = models.CharField(max_length=255, blank=True, null=True)
    website = models.URLField(blank=True, null=True)
    sources_user_can_edit = models.ManyToManyField("main_app.Source", related_name="users_who_can_edit_this_source", blank=True)
    full_name = models.CharField(max_length=255, blank=True, null=True)

    @property
    def name(self):
        if self.full_name:
            return self.full_name
        elif self.first_name and self.last_name:
            return f'{self.first_name} {self.last_name}'

    def __str__(self):
        if self.name:
            return self.name
        else:
            return self.username