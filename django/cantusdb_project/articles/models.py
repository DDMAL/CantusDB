from django.db import models
from users.models import User
from django.template.defaultfilters import slugify
from django.urls import reverse


class Article(models.Model):

    date_created = models.DateTimeField(help_text="The date this article was created")
    date_updated = models.DateTimeField(
        auto_now=True, help_text="The date this article was updated"
    )
    title = models.CharField(max_length=255)
    body = models.TextField()
    author_id = models.IntegerField()
    image_link = models.TextField(null=True)
    slug = models.SlugField(null=False, blank=False, unique=True, max_length=255)

    def save(self, *args, **kwargs):
        if not self.id:
            # Newly created object, so set slug
            self.slug = slugify(self.title)

        super(Article, self).save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("article-detail", kwargs={"slug": self.slug})
