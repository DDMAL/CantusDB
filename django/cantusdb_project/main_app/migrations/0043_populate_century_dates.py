# Data migration to populate min_date and max_date fields for Century model
# Based on century data patterns in the database

from django.db import migrations
import re


def century_name_to_dates(century_name):
    """
    Convert century name to (min_date, max_date) tuple.

    Handles patterns found in the database:
      - "16th century" → (1500, 1599)
      - "15th century (1st half)" → (1400, 1449)
      - "15th century (2nd half)" → (1450, 1499)
      - "10th century (900-925)" → (900, 925)
      - "18th century (first half)" → (1700, 1749)
      - "18th century (second half)" → (1750, 1799)
      - "20th century (before Vatican II)" → (1900, 1962)
      - "20th century (after Vatican II)" → (1962, 1999)
    """
    century_name = century_name.strip()

    # Pattern 1: Explicit date range like "10th century (900-925)"
    match = re.match(r'(\d+)(?:st|nd|rd|th) century \((\d+)-(\d+)\)', century_name)
    if match:
        start_year = int(match.group(2))
        end_year = int(match.group(3))
        return (start_year, end_year)

    # Pattern 2: Half-centuries with "1st half" or "2nd half" format
    match = re.match(r'(\d+)(?:st|nd|rd|th) century \(1st half\)', century_name)
    if match:
        century_num = int(match.group(1))
        century_start = (century_num - 1) * 100
        return (century_start, century_start + 49)

    match = re.match(r'(\d+)(?:st|nd|rd|th) century \(2nd half\)', century_name)
    if match:
        century_num = int(match.group(1))
        century_start = (century_num - 1) * 100
        return (century_start + 50, century_start + 99)

    # Pattern 3: Half-centuries with "first half" or "second half" format
    match = re.match(r'(\d+)(?:st|nd|rd|th) century \(first half\)', century_name)
    if match:
        century_num = int(match.group(1))
        century_start = (century_num - 1) * 100
        return (century_start, century_start + 49)

    match = re.match(r'(\d+)(?:st|nd|rd|th) century \(second half\)', century_name)
    if match:
        century_num = int(match.group(1))
        century_start = (century_num - 1) * 100
        return (century_start + 50, century_start + 99)

    # Pattern 4: Special Vatican II cases
    # Vatican II was 1962-1965, approximate as 1900-1962 and 1962-1999
    if "before Vatican II" in century_name:
        return (1900, 1962)
    if "after Vatican II" in century_name:
        return (1962, 1999)

    # Pattern 5: Full centuries like "16th century"
    match = re.match(r'(\d+)(?:st|nd|rd|th) century$', century_name)
    if match:
        century_num = int(match.group(1))
        century_start = (century_num - 1) * 100
        century_end = century_start + 99
        return (century_start, century_end)

    # No match
    return None


def populate_century_dates(apps, schema_editor):
    """
    Populate min_date and max_date for all existing centuries.
    Extracts dates from century names using regex patterns.

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
            # Century name doesn't match any pattern
            failed_count += 1
            failed_names.append(century.name)

    print(f"\nUpdated {updated_count} centuries with date ranges")

    if failed_count > 0:
        print(f"Failed to auto-map {failed_count} centuries:")
        for name in failed_names:
            print(f"   - {name}")
        print("These will have NULL min_date/max_date. Manually update if needed.\n")


def reverse_populate_century_dates(apps, schema_editor):
    """
    Reverse: Clear all min_date and max_date fields.
    """
    Century = apps.get_model("main_app", "Century")
    Century.objects.all().update(min_date=None, max_date=None)


class Migration(migrations.Migration):

    dependencies = [
        ("main_app", "0042_century_date_fields"),
    ]

    operations = [
        migrations.RunPython(populate_century_dates, reverse_populate_century_dates),
    ]
