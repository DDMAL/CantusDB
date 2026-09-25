"""Derive a displayed ambitus from Volpiano notation."""

from typing import Optional

# Volpiano note characters in ascending pitch order. "9" is the lowest note
# (the G below A); the letter "i" is skipped in volpiano (the note B is "j").
VOLPIANO_PITCH_ORDER: str = "9abcdefghjklmnopqrs"

# Volpiano defines exactly two clefs: "1" (G clef) and "2" (F clef). The
# notation has no C-clef character; if one is ever added, listing it here is
# the only change needed. Chants are overwhelmingly notated with the G clef,
# which is what we fall back to for a melody that declares no clef at all.
VOLPIANO_CLEFS: str = "12"
DEFAULT_VOLPIANO_CLEF: str = "1"

# The character that terminates a chant_range string: a volpiano double barline.
VOLPIANO_RANGE_TERMINATOR: str = "4"


def extract_volpiano_clef(volpiano: str) -> Optional[str]:
    """Return the clef a raw volpiano melody is written in.

    Falls back to the G clef when the melody declares no clef. Returns ``None``
    when the melody changes clef partway through: the same note letter denotes
    a different pitch on either side of the change, so no single clef can
    describe the melody's ambitus.

    Args:
        volpiano (str): The content of ``chant.volpiano`` (raw, un-normalized).

    Returns:
        Optional[str]: The clef character, or None if the melody changes clef.
    """
    clefs: set[str] = {char for char in volpiano if char in VOLPIANO_CLEFS}
    if not clefs:
        return DEFAULT_VOLPIANO_CLEF
    if len(clefs) > 1:
        return None
    return clefs.pop()


def generate_chant_range(volpiano: str) -> str:
    """Derive a chant's ``chant_range`` from its raw volpiano.

    The range is itself a short volpiano string of the form
    ``"{clef}-{lowest}-{highest}-4"`` (clef, lowest note, highest note,
    double barline) that renders in the volpiano font as the chant's ambitus.

    The clef is copied from the melody rather than hardcoded, so that a range
    always renders on the same staff as the melody it describes.

    Args:
        volpiano (str): The content of ``chant.volpiano`` (raw, un-normalized).

    Returns:
        str: The ``chant_range`` string, or ``""`` if there are no notes or the
        melody changes clef.
    """
    # Real volpiano fields contain occasional dirty characters — stray
    # punctuation, whitespace, and typos (e.g. a literal "TEST!") — that
    # may occur in legacy records. Restrict to recognized pitches so the
    # ambitus reflects actual notes and a bad character can't crash a batch.
    present: set[str] = set(volpiano.lower().replace(")", "9"))
    pitches: list[str] = [pitch for pitch in VOLPIANO_PITCH_ORDER if pitch in present]
    if not pitches:
        return ""
    clef: Optional[str] = extract_volpiano_clef(volpiano)
    if clef is None:
        # The melody changes clef, so its ambitus cannot be written as a single
        # clef plus two notes. Deriving nothing is better than deriving a range
        # that is confidently wrong.
        return ""
    return f"{clef}-{pitches[0]}-{pitches[-1]}-{VOLPIANO_RANGE_TERMINATOR}"
