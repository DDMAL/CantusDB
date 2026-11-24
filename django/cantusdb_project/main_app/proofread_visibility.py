"""
Fields of a chant or sequence that stay hidden from anonymous users until they
are proofread (#1100). Logged-in users see everything.

Every page and export that shows these fields goes through this module, so they
all agree on what the public can see.
"""

from collections.abc import Iterable
from typing import Any, Union

from django.contrib.auth.models import AnonymousUser
from django.db.models import Q

from main_app.models import Chant, Sequence
from users.models import User

# Each proofread flag mapped to the fields it vouches for. Fields derived from
# another field (the syllabized text, the volpiano search columns) hide with it.
HIDDEN_UNTIL_PROOFREAD: dict[str, tuple[str, ...]] = {
    "volpiano_proofread": ("volpiano", "volpiano_notes", "volpiano_intervals"),
    "manuscript_full_text_proofread": (
        "manuscript_full_text",
        "manuscript_syllabized_full_text",
    ),
    "manuscript_full_text_std_proofread": ("manuscript_full_text_std_spelling",),
}
PROOFREAD_FLAGS = tuple(HIDDEN_UNTIL_PROOFREAD)
FLAG_FOR_FIELD = {
    field: flag for flag, fields in HIDDEN_UNTIL_PROOFREAD.items() for field in fields
}


def sees_unproofread(user: Union[User, AnonymousUser]) -> bool:
    return user.is_authenticated


def public_q(field: str) -> Q:
    """Rows where `field` is visible to the public."""
    return Q(**{FLAG_FOR_FIELD[field]: True})


def visible_q(field: str, user: Union[User, AnonymousUser]) -> Q:
    """Rows where `field` is visible to `user`. Combine with a filter on `field`."""
    return Q() if sees_unproofread(user) else public_q(field)


def hide_unproofread(record: Union[Chant, Sequence]) -> None:
    """Blank the unproofread fields of a record in memory. Never save it afterwards."""
    for flag, fields in HIDDEN_UNTIL_PROOFREAD.items():
        if getattr(record, flag) is not True:
            for field in fields:
                setattr(record, field, None)


def hide_unproofread_values(row: dict[str, Any]) -> None:
    """Blank the unproofread fields of a `.values()` row that includes the flags."""
    for flag, fields in HIDDEN_UNTIL_PROOFREAD.items():
        if row[flag] is not True:
            for field in fields:
                if field in row:
                    row[field] = None


def hide_unproofread_from(
    user: Union[User, AnonymousUser], records: Iterable[Union[Chant, Sequence]]
) -> None:
    """Blank the unproofread fields of `records` unless `user` may see them."""
    if not sees_unproofread(user):
        for record in records:
            hide_unproofread(record)
