from django.db import migrations, models

from ._country_authority_urls import unique_authority_urls


class Migration(migrations.Migration):
    dependencies = [("main_app", "0050_reconcile_wikidata_country_ids")]
    operations = [
        migrations.AlterField(
            model_name="country",
            name="authorities",
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text="Enter database names and full record URLs. Getty TGN and Wikidata also accept short IDs. "
                'Example for Canada: {"GeoNames": "https://www.geonames.org/6251999/", "wikidata": "Q16"}.',
            ),
        ),
        unique_authority_urls,
    ]
