"""
Chant fields that are locked once proofread (#170, #2260).

Each proofread checkbox locks the fields it vouches for. A locked field can't be
changed by anyone: a proofreader unticks the box to unlock it (they can do so in
the same save as the edit), and nobody else can untick it. The indexing notes
are never locked, so indexers can still leave notes on a fully proofread chant.

Every form and view that edits chants goes through this module, so they all
agree on what is locked.
"""

from typing import Optional

from django import forms

from main_app.models import Chant

OTHER_FIELDS_FLAG = "other_fields_proofread"

# Each text flag mapped to the fields it locks. Fields derived from another
# field (the syllabized text, the chant range) lock with it.
TEXT_FIELD_LOCKS: dict[str, tuple[str, ...]] = {
    "manuscript_full_text_std_proofread": ("manuscript_full_text_std_spelling",),
    "manuscript_full_text_proofread": (
        "manuscript_full_text",
        "manuscript_syllabized_full_text",
    ),
    "volpiano_proofread": ("volpiano", "chant_range"),
}
PROOFREAD_FLAGS = (*TEXT_FIELD_LOCKS, OTHER_FIELDS_FLAG)

# Fields `other_fields_proofread` leaves editable: the indexing notes, and the
# proofreading controls themselves.
NEVER_LOCKED = frozenset(
    {"id", "source", "indexing_notes", "proofread_by", *PROOFREAD_FLAGS}
)


def lock_flag_for(field: str) -> Optional[str]:
    """The proofread flag that locks `field`, or None if it is never locked."""
    for flag, fields in TEXT_FIELD_LOCKS.items():
        if field in fields:
            return flag
    if field in NEVER_LOCKED:
        return None
    return OTHER_FIELDS_FLAG


def has_proofread_fields(chant: Chant) -> bool:
    """True if any of the chant's proofread boxes is ticked."""
    return any(getattr(chant, flag) is True for flag in PROOFREAD_FLAGS)


def lock_proofread_fields(
    form: forms.ModelForm, can_unlock: bool = False  # type: ignore[type-arg]
) -> dict[str, list[str]]:
    """Disable the fields of `form` that its chant's proofread boxes lock.

    Disabled fields keep their saved value whatever is submitted, so the lock
    holds on the server too. A NULL flag counts as unticked.

    If `can_unlock` (the user is a proofreader of the chant's source), the
    edit page unlocks a field when its box is unticked, so a field the
    proofreader submits is unlocked: they unticked its box to edit it, whether
    or not they ticked it again before saving (#170). A field they left locked
    isn't submitted, so it keeps its saved value.

    A lockable field left out of a submission also keeps its saved value, even
    if its box is no longer ticked. The page it came from had the field locked,
    and a proofreader has unticked the box since. Treating the missing field as
    empty would erase the saved value.

    Returns, for each proofread checkbox on the form, the names of the fields
    it locks, so the page can lock and unlock them as the box is ticked.
    """
    locked_by: dict[str, list[str]] = {}
    for name in form.fields:
        if flag := lock_flag_for(name):
            locked_by.setdefault(flag, []).append(name)

    for flag, fields in locked_by.items():
        flag_ticked = getattr(form.instance, flag) is True
        for name in fields:
            submitted = form.is_bound and not _value_omitted(form, name)
            if submitted and (can_unlock or not flag_ticked):
                continue
            if flag_ticked or form.is_bound:
                _lock(form.fields[name])

    return {flag: fields for flag, fields in locked_by.items() if flag in form.fields}


def _value_omitted(form: forms.ModelForm, name: str) -> bool:  # type: ignore[type-arg]
    """True if the submission leaves `name` out, as browsers do with disabled inputs."""
    return form.fields[name].widget.value_omitted_from_data(
        form.data, form.files, form.add_prefix(name)
    )


def _lock(field: forms.Field) -> None:
    field.disabled = True
    if field.required:
        # Nobody can fill in a locked field, so it can't be required. The
        # input keeps its `required` attribute: browsers ignore it while the
        # input is disabled, and it applies again once the page unlocks it.
        field.required = False
        field.widget.attrs["required"] = True
