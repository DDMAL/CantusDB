"""
Data migration to import sources from cantorales_2024-05-01.csv.

Delegates to the import_cantorales management command so that the import
runs automatically on every environment via ``manage.py migrate``.
"""

from django.core.management import call_command
from django.db import migrations


def import_cantorales(apps, schema_editor):
    call_command("import_cantorales")


class Migration(migrations.Migration):

    dependencies = [
        ("main_app", "0041_alter_source_source_completeness"),
        ("users", "__latest__"),
    ]

    operations = [
        migrations.RunPython(
            import_cantorales,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
