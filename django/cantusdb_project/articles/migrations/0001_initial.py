# Generated by Django 4.1.7 on 2023-07-25 16:04

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django_quill.fields


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Article",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("title", models.CharField(max_length=255)),
                ("body", django_quill.fields.QuillField()),
                (
                    "date_created",
                    models.DateTimeField(
                        auto_now_add=True,
                        help_text="The date this article was created",
                        null=True,
                    ),
                ),
                (
                    "date_updated",
                    models.DateTimeField(
                        auto_now=True,
                        help_text="The date this article was most recently updated",
                        null=True,
                    ),
                ),
                (
                    "author",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
    ]
