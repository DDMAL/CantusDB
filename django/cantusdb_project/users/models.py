from django.db import models
from django.contrib.auth.models import AbstractUser
from django.urls.base import reverse
from .managers import CustomUserManager


class User(AbstractUser):
    institution = models.CharField(max_length=255, blank=True, null=True)
    city = models.CharField(max_length=255, blank=True, null=True)
    country = models.CharField(max_length=255, blank=True, null=True)
    website = models.URLField(blank=True, null=True)
    full_name = models.CharField(max_length=255, blank=True, null=True)
    # email replaces username
    # i.e. users will log in with their emails
    username = None
    email = models.EmailField(unique=True)
    # whether the user has an associated indexer object on old Cantus
    # if True, list the user in indexer-list page
    is_indexer = models.BooleanField(default=False)
    # if the user has an associated indexer object on old Cantus, save its ID
    old_indexer_id = models.IntegerField(blank=True, null=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = CustomUserManager()

    def __str__(self):
        if self.full_name:
            return self.full_name
        else:
            return self.email

    def get_absolute_url(self) -> str:
        """Get the absolute URL for an instance of a model."""
        detail_name = self.__class__.__name__.lower() + "-detail"
        return reverse(detail_name, kwargs={"pk": self.pk})
