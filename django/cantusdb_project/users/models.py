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
    # will be used to check if the user has changed the password assigned to them
    changed_initial_password = models.BooleanField(default=False)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    objects = CustomUserManager()

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
            return self.email

    def get_absolute_url(self) -> str:
        """Get the absolute URL for an instance of a model."""
        detail_name = self.__class__.__name__.lower() + "-detail"
        return reverse(detail_name, kwargs={"pk": self.pk})
