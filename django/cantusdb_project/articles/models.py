from django.contrib.auth import get_user_model
from django.db import models
from django.urls import reverse
from django_quill.fields import QuillField


class Article(models.Model):
    title = models.CharField(max_length=255)
    body = QuillField()  # rich text field
    author = models.ForeignKey(
        get_user_model(),
        on_delete=models.CASCADE,
    )
    date_created = models.DateTimeField(
        help_text="The date this article was created",
        null=False,
        blank=False,
        auto_now_add=True,
    )
    date_updated = models.DateTimeField(
        help_text="The date this article was most recently updated",
        auto_now=True,
        null=True,
        blank=True,
    )

    def __str__(self):
        return self.title

    def get_absolute_url(self) -> str:
        """Get the absolute URL for an instance of a model."""
        detail_name = "article-detail"
        return reverse(detail_name, kwargs={"pk": self.pk})
