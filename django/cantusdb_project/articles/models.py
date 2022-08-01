from django.conf import settings
from django.db import models
from django.urls import reverse
from main_app.models import Indexer

class Article(models.Model):
    title = models.CharField(max_length=255)
    body = models.TextField()
    
    author = models.ForeignKey(
        Indexer,
        on_delete=models.CASCADE,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
    )

    date_created = models.DateTimeField(
        help_text="The date this article was created",
        null=True,
        blank=True,
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