from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("main_app", "0044_chantelement"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="chantelement",
            constraint=models.UniqueConstraint(
                fields=("chant", "order"), name="unique_chant_element_order"
            ),
        ),
    ]
