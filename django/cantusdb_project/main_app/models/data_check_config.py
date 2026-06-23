from django.db import models


class DataCheckConfig(models.Model):
    class Frequency(models.TextChoices):
        DAILY = "daily", "Daily"
        WEEKLY = "weekly", "Weekly"
        MONTHLY = "monthly", "Monthly"

    class Scope(models.TextChoices):
        ALL = "all", "All records"
        EDITED = "edited", "Only records edited in the period"

    frequency = models.CharField(
        max_length=20,
        choices=Frequency.choices,
        default=Frequency.WEEKLY,
        help_text="How often the data checks should run.",
    )
    scope = models.CharField(
        max_length=20,
        choices=Scope.choices,
        default=Scope.ALL,
        help_text=(
            "All records: run checks against the full dataset. "
            "Only edited: restrict checks to records modified since the last run."
        ),
    )
    last_run = models.DateTimeField(
        null=True,
        blank=True,
        help_text=(
            "Set automatically after each completed run. "
            "Used to determine the editing window when scope is 'Only edited'."
        ),
    )
    recipients = models.TextField(
        blank=True,
        help_text="Comma-separated email addresses that receive the data check report.",
    )

    class Meta:
        verbose_name = "Data check configuration"
        verbose_name_plural = "Data check configurations"

    def __str__(self) -> str:
        return f"{self.get_frequency_display()} / {self.get_scope_display()}"
