from django.db import models
from django.contrib.auth.models import AbstractUser, GroupManager
from django.urls.base import reverse
from .managers import CustomUserManager


class Group(models.Model):
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True, null=True)

    def __str__(self) -> str:
        return self.name

    objects = GroupManager()


class User(AbstractUser):
    institution = models.CharField(max_length=255, blank=True, null=True)
    city = models.CharField(max_length=255, blank=True, null=True)
    country = models.CharField(max_length=255, blank=True, null=True)
    website = models.URLField(blank=True, null=True)
    full_name = models.CharField(max_length=255, blank=True, null=True)
    # email replaces username
    # i.e. users will log in with their emails
    username = None  # type: ignore[assignment]
    email = models.EmailField(unique=True)
    # whether the user has an associated indexer object on old Cantus
    # if True, list the user in indexer-list page
    is_indexer = models.BooleanField(default=False)
    # if the user has an associated indexer object on old Cantus, save its ID
    old_indexer_id = models.IntegerField(blank=True, null=True)
    groups_new = models.ManyToManyField(  # type: ignore[var-annotated]
        Group,
        verbose_name="groups",
        through="GroupMembership",
        related_name="user_set",
        related_query_name="user",
    )

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = CustomUserManager()  # type: ignore

    class Meta:
        constraints = [
            models.CheckConstraint(
                check=(models.Q(is_staff=True) & models.Q(is_superuser=True))
                | (models.Q(is_staff=False) & models.Q(is_superuser=False)),
                name="is_staff_xnor_is_superuser",
                violation_error_message=(
                    "A user cannot be staff without being a superuser, "
                    "and vice versa."
                ),
            )
        ]

    def __str__(self) -> str:
        if self.full_name:
            return self.full_name
        return self.email

    def get_absolute_url(self) -> str:
        """Get the absolute URL for an instance of a model."""
        detail_name = self.__class__.__name__.lower() + "-detail"
        return reverse(detail_name, kwargs={"pk": self.pk})


class GroupMembership(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    group = models.ForeignKey(Group, on_delete=models.CASCADE)
    expiration = models.DateField(
        blank=True,
        null=True,
        help_text=("The date the user's membership in the group expires."),
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "group"], name="unique_group_membership"
            )
        ]
