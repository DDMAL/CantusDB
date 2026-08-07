"""Validation, canonicalisation and rendering rules for a chant cluster's segments.

Kept free of model imports so the models, forms, admin and views share one
implementation of the rules instead of drifting apart. A "segment spec" here is a plain
dict; the model layer turns specs into rows and back.
"""

import json
from typing import Any, Optional, Sequence, TypedDict

from django.core.exceptions import ValidationError

# A real troped cluster runs to a few dozen segments. Cap it so a crafted or runaway
# payload can't drive an unbounded row-creation loop.
MAX_SEGMENTS: int = 200


class SegmentSpec(TypedDict):
    """One normalised segment.

    Exactly one of three shapes is populated:

    - ``start``/``end`` set — a half-open range of base-text tokens.
    - ``element`` set — a catalogued trope. Only ``.text`` is ever read here, so this
      module needs no import of the model.
    - ``text`` non-empty — a trope Cantus Index has not catalogued.
    """

    start: Optional[int]
    end: Optional[int]
    element: Optional[Any]
    text: str


def normalize_segments(
    base_token_count: int, segments: Sequence[Any]
) -> list[SegmentSpec]:
    """Validate a raw segment list and return it in canonical form.

    Canonical means every segment has exactly one shape, and no two *adjacent* core
    segments are also *contiguous* in the base text — ``[2, 5)`` followed by ``[5, 8)``
    collapses to ``[2, 8)``. Without that merge one rendered text has many encodings,
    which breaks equality and diffing between clusters.

    Overlapping and out-of-order core ranges are deliberately legal: a base phrase may
    be repeated (a repetendum) or reordered, and both are expressed purely by where its
    range sits in this list. Nothing here is in base-text coordinates, so there is no
    anchor that can go stale.

    Raises:
        ValidationError: if the list is empty, over ``MAX_SEGMENTS``, or any segment has
            an ambiguous shape or an out-of-bounds range.
    """
    if not segments:
        raise ValidationError("A cluster must have at least one segment.")
    if len(segments) > MAX_SEGMENTS:
        raise ValidationError(f"A cluster can have at most {MAX_SEGMENTS} segments.")
    normalized: list[SegmentSpec] = [
        _normalize_one(base_token_count, segment) for segment in segments
    ]
    return _merge_adjacent_cores(normalized)


def _normalize_one(base_token_count: int, segment: Any) -> SegmentSpec:
    """Validate one raw segment and return it as a fully-populated spec."""
    if not isinstance(segment, dict):
        raise ValidationError("Each segment must be an object.")
    start: Any = segment.get("start")
    end: Any = segment.get("end")
    element: Any = segment.get("element")
    text: str = (segment.get("text") or "").strip()

    has_range: bool = start is not None or end is not None
    shapes: list[bool] = [has_range, element is not None, bool(text)]
    if sum(shapes) != 1:
        raise ValidationError(
            "A segment must be exactly one of: a base-text range, a catalogued trope, "
            "or inline trope text."
        )

    if has_range:
        if start is None or end is None:
            raise ValidationError("A base-text range needs both a start and an end.")
        # bool is a subclass of int, and JSON `true` decodes to True — reject it rather
        # than silently reading it as the index 1.
        if (
            not isinstance(start, int)
            or not isinstance(end, int)
            or isinstance(start, bool)
            or isinstance(end, bool)
        ):
            raise ValidationError("A base-text range must be given as whole numbers.")
        if start < 0 or end <= start or end > base_token_count:
            raise ValidationError(
                f"Base-text range [{start}, {end}) is outside the base text's "
                f"{base_token_count} tokens."
            )
        return SegmentSpec(start=start, end=end, element=None, text="")

    if element is not None:
        return SegmentSpec(start=None, end=None, element=element, text="")

    return SegmentSpec(start=None, end=None, element=None, text=text)


def _merge_adjacent_cores(segments: list[SegmentSpec]) -> list[SegmentSpec]:
    """Collapse neighbouring core segments that are contiguous in the base text."""
    merged: list[SegmentSpec] = []
    for segment in segments:
        previous: Optional[SegmentSpec] = merged[-1] if merged else None
        if (
            previous is not None
            and previous["start"] is not None
            and segment["start"] is not None
            and previous["end"] == segment["start"]
        ):
            previous["end"] = segment["end"]
            continue
        merged.append(segment)
    return merged


def flatten_segments(tokens: Sequence[str], segments: Sequence[SegmentSpec]) -> str:
    """Render a normalised segment list to one whitespace-normalised string.

    A cluster whose only segment spans the whole base text flattens back to the
    normalised base text — the round-trip invariant the tokenisation has to satisfy.
    """
    parts: list[str] = []
    for segment in segments:
        if segment["start"] is not None:
            parts.extend(tokens[segment["start"] : segment["end"]])
        else:
            element: Any = segment.get("element")
            text: str = element.text if element is not None else segment["text"]
            parts.extend(text.split())
    return " ".join(parts)


class ClusterPayload(TypedDict):
    """A cluster as the client submits it, after parsing and shape validation.

    ``segments`` entries are *not* ``SegmentSpec``s: a catalogued trope's reference is
    still a Cantus ID string in ``element``, with the trope's own text alongside it in
    ``element_text``. Resolving those to shared rows needs database access, which is the
    model layer's job (``ChantCluster.apply_payload``), not this module's.
    """

    base_cantus_id: str
    base_text: str
    segments: list[dict[str, Any]]


def parse_cluster_payload(raw: str) -> Optional[ClusterPayload]:
    """Parse a submitted cluster, or return None when the chant has no cluster.

    Validates the payload's shape all the way down so a malformed submission becomes a
    form error instead of an exception during save.

    Each submitted segment is exactly one of:

    - ``{"start": n, "end": m}`` — a half-open range of base-text tokens.
    - ``{"cantus_id": "g04828:01", "text": "..."}`` — a catalogued trope. The text is the
      trope's own, carried so a trope not yet catalogued locally can be stored; it is
      never used to overwrite an existing row.
    - ``{"text": "..."}`` — a trope Cantus Index has not catalogued.

    Raises:
        ValidationError: on malformed JSON, a missing base text, or any segment whose
            shape or range is invalid.
    """
    text: str = (raw or "").strip()
    if not text:
        return None
    try:
        data: Any = json.loads(text)
    except json.JSONDecodeError:
        raise ValidationError("The composed cluster is not valid JSON.")
    if not isinstance(data, dict):
        raise ValidationError("The composed cluster must be an object.")
    base_text: str = " ".join((data.get("base_text") or "").split())
    if not base_text:
        raise ValidationError("A cluster needs a base text.")
    raw_segments: Any = data.get("segments")
    if not isinstance(raw_segments, list):
        raise ValidationError("A cluster's segments must be a list.")

    segments: list[dict[str, Any]] = []
    for segment in raw_segments:
        if not isinstance(segment, dict):
            raise ValidationError("Each segment must be an object.")
        cantus_id: str = (segment.get("cantus_id") or "").strip()
        segment_text: str = (segment.get("text") or "").strip()
        if cantus_id and not segment_text:
            raise ValidationError(
                f"The trope {cantus_id} was submitted without its text, which is needed "
                "to catalogue it."
            )
        segments.append(
            {
                "start": segment.get("start"),
                "end": segment.get("end"),
                "element": cantus_id or None,
                # A catalogued trope's text belongs to the shared row, not to this
                # segment, so it moves out of the slot the shape check reads.
                "text": "" if cantus_id else segment_text,
                "element_text": segment_text if cantus_id else "",
            }
        )
    # Validate shapes and bounds now, with the Cantus ID standing in for the trope row —
    # normalize_segments only tests that slot for presence. The result is discarded; the
    # canonical list is built by set_structure once the rows are resolved.
    normalize_segments(len(base_text.split()), segments)
    return ClusterPayload(
        base_cantus_id=(data.get("base_cantus_id") or "").strip(),
        base_text=base_text,
        segments=segments,
    )


def compute_omitted_ranges(
    base_token_count: int, segments: Sequence[SegmentSpec]
) -> list[tuple[int, int]]:
    """The base-text ranges no segment references, as half-open ``[start, end)`` pairs.

    Derived rather than stored: a stored omission list could contradict the segments,
    and there would be no way to tell which one was right.
    """
    covered: set[int] = set()
    for segment in segments:
        if segment["start"] is not None:
            covered.update(range(segment["start"], segment["end"]))
    ranges: list[tuple[int, int]] = []
    run_start: Optional[int] = None
    for index in range(base_token_count):
        if index in covered:
            if run_start is not None:
                ranges.append((run_start, index))
                run_start = None
        elif run_start is None:
            run_start = index
    if run_start is not None:
        ranges.append((run_start, base_token_count))
    return ranges
