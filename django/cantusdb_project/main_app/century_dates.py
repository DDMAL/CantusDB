"""Utility for parsing century names into (min_date, max_date) ranges.

Used by the data migration that populates Century.min_date/max_date and by
test factories that need consistent date ranges for fake centuries.
"""

import re
from typing import Optional, Tuple


def century_name_to_dates(century_name: str) -> Optional[Tuple[int, int]]:
    """
    Convert century name to (min_date, max_date) tuple.

    Handles patterns found in the database:
      - "16th century" → (1500, 1599)
      - "15th century (1st half)" → (1400, 1449)
      - "15th century (2nd half)" → (1450, 1499)
      - "10th century (900-925)" → (900, 925)
      - "18th century (first half)" → (1700, 1749)
      - "18th century (second half)" → (1750, 1799)
      - "20th century (before Vatican II)" → (1900, 1965)
      - "20th century (after Vatican II)" → (1965, 1999)

    Returns None if the name does not match any known pattern.
    """
    century_name = century_name.strip()

    match = re.match(r"(\d+)(?:st|nd|rd|th) century \((\d+)-(\d+)\)", century_name)
    if match:
        return (int(match.group(2)), int(match.group(3)))

    match = re.match(r"(\d+)(?:st|nd|rd|th) century \(1st half\)", century_name)
    if match:
        century_start = (int(match.group(1)) - 1) * 100
        return (century_start, century_start + 49)

    match = re.match(r"(\d+)(?:st|nd|rd|th) century \(2nd half\)", century_name)
    if match:
        century_start = (int(match.group(1)) - 1) * 100
        return (century_start + 50, century_start + 99)

    match = re.match(r"(\d+)(?:st|nd|rd|th) century \(first half\)", century_name)
    if match:
        century_start = (int(match.group(1)) - 1) * 100
        return (century_start, century_start + 49)

    match = re.match(r"(\d+)(?:st|nd|rd|th) century \(second half\)", century_name)
    if match:
        century_start = (int(match.group(1)) - 1) * 100
        return (century_start + 50, century_start + 99)

    if "before Vatican II" in century_name:
        return (1900, 1965)
    if "after Vatican II" in century_name:
        return (1965, 1999)

    match = re.match(r"(\d+)(?:st|nd|rd|th) century$", century_name)
    if match:
        century_start = (int(match.group(1)) - 1) * 100
        return (century_start, century_start + 99)

    return None
