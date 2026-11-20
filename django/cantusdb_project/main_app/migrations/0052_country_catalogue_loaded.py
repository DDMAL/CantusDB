from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("main_app", "0051_country_authority_urls")]
    operations = [
        migrations.AddField(
            model_name="country",
            name="catalogue_loaded",
            field=models.BooleanField(default=False, editable=False),
        ),
    ]
