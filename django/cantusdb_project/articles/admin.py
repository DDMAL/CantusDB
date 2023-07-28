from django.contrib import admin
from articles.models import Article


class ArticleAdmin(admin.ModelAdmin):
    readonly_fields = (
        "date_created",
        "date_updated",
    )


# Register your models here.
admin.site.register(Article, ArticleAdmin)
