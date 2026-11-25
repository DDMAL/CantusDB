"""Roman (Julian calendar) dates for feasts, e.g. 17 May → "XVI. Kal. Iun." (#2376).

Each day is counted back, inclusively, to the next of the month's three fixed
days: the Kalends (the 1st), the Nones (the 5th, or the 7th in March, May,
July and October) and the Ides (eight days after the Nones). The day before
one of them is "Pridie". After the Ides, days count to the Kalends of the
next month.

February has 28 days here: a feast's month and day name no particular year,
and the leap-year day has no fixed date of its own.
"""

from typing import Optional

MONTHS = (
    "Ian.",
    "Feb.",
    "Mart.",
    "Apr.",
    "Mai.",
    "Iun.",
    "Iul.",
    "Aug.",
    "Sept.",
    "Oct.",
    "Nov.",
    "Dec.",
)
DAYS_IN_MONTH = (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)
NUMERALS = ((10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I"))


def to_roman_numeral(number: int) -> str:
    numeral = ""
    for value, letters in NUMERALS:
        while number >= value:
            numeral += letters
            number -= value
    return numeral


def julian_date(month: Optional[int], day: Optional[int]) -> Optional[str]:
    """The Roman date of a month and day, or None if there isn't one."""
    if not month or not day or not 1 <= month <= 12:
        return None
    if not 1 <= day <= DAYS_IN_MONTH[month - 1]:
        return None

    nones = 7 if month in (3, 5, 7, 10) else 5
    ides = nones + 8
    if day == 1:
        return f"Kal. {MONTHS[month - 1]}"
    if day == nones:
        return f"Non. {MONTHS[month - 1]}"
    if day == ides:
        return f"Id. {MONTHS[month - 1]}"

    if day < nones:
        target, name, named_month = nones, "Non.", month
    elif day < ides:
        target, name, named_month = ides, "Id.", month
    else:
        target = DAYS_IN_MONTH[month - 1] + 1
        name, named_month = "Kal.", month % 12 + 1
    count = target - day + 1
    prefix = "Pridie" if count == 2 else f"{to_roman_numeral(count)}."
    return f"{prefix} {name} {MONTHS[named_month - 1]}"
