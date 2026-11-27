from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("main_app", "0050_link_institution_countries")]
    operations = [migrations.RemoveField("institution", "country_text")]
