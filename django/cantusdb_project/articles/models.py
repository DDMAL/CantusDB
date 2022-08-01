from django.conf import settings
from django.db import models

class Article(models.Model):
    title = models.CharField(max_length=255)
    body = models.TextField()
    
    author = models.CharField(max_length=255)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
    )

    date_created = models.DateTimeField(
        help_text="The date this article was created",
        null=True,
        blank=True,)
    date_updated = models.DateTimeField(
        help_text="The date this article was most recently updated",
        auto_now=True,
        null=True,
        blank=True,
    )

    def __str__(self):
        return self.title