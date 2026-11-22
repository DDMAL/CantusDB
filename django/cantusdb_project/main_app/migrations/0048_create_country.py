from django.db import migrations, models
from django.db.models.functions import Lower


class Migration(migrations.Migration):
    dependencies = [("main_app", "0047_notation_clavis_sequentiarum_labels")]

    operations = [
        migrations.CreateModel(
            name="Country",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=64)),
                (
                    "aliases",
                    models.TextField(
                        blank=True, help_text="Enter one alternate name per line."
                    ),
                ),
                (
                    "rism_code",
                    models.CharField(
                        "RISM country code",
                        blank=True,
                        max_length=8,
                        null=True,
                        unique=True,
                    ),
                ),
                (
                    "authorities",
                    models.JSONField(
                        blank=True,
                        default=dict,
                        help_text="Enter a JSON object of database names and full record URLs.",
                    ),
                ),
            ],
            options={
                "ordering": ["name"],
                "verbose_name_plural": "countries",
                "constraints": [
                    models.UniqueConstraint(
                        Lower("name"), name="unique_country_name_ci"
                    )
                ],
            },
        ),
    ]
