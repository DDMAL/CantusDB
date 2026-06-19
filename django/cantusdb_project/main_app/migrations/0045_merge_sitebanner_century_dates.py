# Merge migration reconciling the two 0043 leaves created when develop
# (0043_century_date_fields -> 0044_populate_century_dates) and staging
# (0043_sitebanner) diverged from 0042_source_source_data_contributed_by.

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("main_app", "0043_sitebanner"),
        ("main_app", "0044_populate_century_dates"),
    ]

    operations = []
