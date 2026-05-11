# Data migration to populate min_date and max_date fields for Century model
# Based on century data patterns in the database

from django.db import migrations

from main_app.century_dates import century_name_to_dates


def populate_century_dates(apps, schema_editor):
    """
    Populate min_date and max_date for all existing centuries.
    Extracts dates from century names using shared regex patterns.

    Reports summary statistics:
      - Number of centuries successfully mapped
      - Number of unmapped centuries (if any)
    """
    Century = apps.get_model("main_app", "Century")

    updated_count = 0
    failed_count = 0
    failed_names = []

    for century in Century.objects.all():
        dates = century_name_to_dates(century.name)

        if dates:
            min_date, max_date = dates
            century.min_date = min_date
            century.max_date = max_date
            century.save()
            updated_count += 1
        else:
            failed_count += 1
            failed_names.append(century.name)

    print(f"\nUpdated {updated_count} centuries with date ranges")

    if failed_count > 0:
        print(f"Failed to auto-map {failed_count} centuries:")
        for name in failed_names:
            print(f"   - {name}")
        print("These will have NULL min_date/max_date. Manually update if needed.\n")


def reverse_populate_century_dates(apps, schema_editor):
    """Clear all min_date and max_date fields."""
    Century = apps.get_model("main_app", "Century")
    Century.objects.all().update(min_date=None, max_date=None)


class Migration(migrations.Migration):

    dependencies = [
        ("main_app", "0042_century_date_fields"),
    ]

    operations = [
        migrations.RunPython(populate_century_dates, reverse_populate_century_dates),
    ]
