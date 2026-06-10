from cmarkgfm import github_flavored_markdown_to_html
from cmarkgfm.cmark import Options

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.safestring import SafeString, mark_safe


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
            "Markdown supported: [text](URL) for links, **bold**, *italic*. "
            "Press Enter for a new line."
        ),
    )
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text=(
            "Optional. Banner is automatically hidden at this time. "
            "Must be in the future, or leave blank to keep showing until "
            "you uncheck 'Is active'."
        ),
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
        # Singular on purpose: the admin only ever shows one row.
        verbose_name_plural = "site banner"

    def __str__(self) -> str:
        state = "active" if self.is_active else "inactive"
        return f"Site banner ({state})"

    def clean(self) -> None:
        if self.expires_at is None or self.expires_at > timezone.now():
            return
        # The expiry is in the past. Reject it only if the editor is setting a
        # new value -- an already-elapsed expiry left untouched must stay
        # editable (e.g. to fix the message or clear the date), since an
        # expired banner is a valid state that simply doesn't display.
        stored_expiry = (
            type(self)
            .objects.filter(pk=self.pk)
            .values_list("expires_at", flat=True)
            .first()
        )
        if stored_expiry != self.expires_at:
            raise ValidationError({"expires_at": "Expiry time must be in the future."})

    def save(self, *args, **kwargs) -> None:
        # Enforce singleton: always pk=1. Drop force_insert so Django picks
        # UPDATE-or-INSERT based on row existence (objects.create() sets
        # force_insert=True, which would otherwise collide on the fixed pk).
        self.pk = 1
        kwargs.pop("force_insert", None)
        # Skip validate_unique: the fixed pk=1 makes a second create() look
        # like a duplicate row, but it's actually meant to overwrite the
        # singleton. Field-level validation still runs.
        self.full_clean(validate_unique=False)
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

    def rendered_message(self) -> SafeString:
        """Render the message from GFM markdown to sanitized HTML.

        cmarkgfm's default ("safe") mode drops raw HTML and rewrites unsafe
        URL schemes (javascript:, data:) to an empty href, so the output is
        safe to mark for the template.
        """
        if not self.message.strip():
            return mark_safe("")
        html = github_flavored_markdown_to_html(
            self.message, options=Options.CMARK_OPT_HARDBREAKS
        ).strip()
        # Drop the outer <p> wrapper for single-paragraph messages so the
        # alert box doesn't inherit a paragraph's default bottom margin.
        if html.startswith("<p>") and html.endswith("</p>") and html.count("<p>") == 1:
            html = html[3:-4]
        return mark_safe(html)
