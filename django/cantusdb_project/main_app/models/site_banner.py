from django.contrib.auth import get_user_model
from django.db import models
from django.utils import timezone


class SiteBanner(models.Model):
    """Singleton model for a site-wide notification banner.

    Exactly one row exists (pk=1). When ``is_active`` is True the banner
    shows to all visitors; when False but ``message`` is non-empty, only
    superusers see it as an in-context preview.
    """

    is_active = models.BooleanField(
        default=False,
        help_text=(
            "When unchecked, only superusers see the banner (as a preview). "
            "Check this to show it to all site visitors."
        ),
    )
    message = models.TextField(
        blank=True,
        help_text=(
            "Banner text shown to all site visitors. HTML is allowed — "
            'use <a href="URL">text</a> for links.'
        ),
    )
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Optional. Banner is automatically hidden after this time.",
    )
    updated_by = models.ForeignKey(
        get_user_model(),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        editable=False,
        related_name="+",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "main_app"
        verbose_name = "site banner"
        verbose_name_plural = "site banner"

    def __str__(self) -> str:
        state = "active" if self.is_active else "inactive"
        return f"Site banner ({state})"

    def save(self, *args, **kwargs) -> None:
        # Enforce singleton: always pk=1. Drop force_insert so Django picks
        # UPDATE-or-INSERT based on row existence (objects.create() sets
        # force_insert=True, which would otherwise collide on the fixed pk).
        self.pk = 1
        kwargs.pop("force_insert", None)
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs) -> None:
        # Singleton: never deleted.
        return

    @classmethod
    def load(cls) -> "SiteBanner":
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def has_content(self) -> bool:
        """True if the banner has a non-empty, non-expired message."""
        if not self.message.strip():
            return False
        return self.expires_at is None or self.expires_at > timezone.now()

    def is_displayable(self) -> bool:
        """True if the banner should be shown to all visitors."""
        return self.is_active and self.has_content()
