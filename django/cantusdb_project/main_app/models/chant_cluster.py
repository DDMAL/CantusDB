import hashlib
from typing import Any, Optional, Sequence

from django.core.exceptions import ValidationError
from django.db import models, transaction

from main_app.cluster_structure import (
    ClusterPayload,
    SegmentSpec,
    compute_omitted_ranges,
    flatten_segments,
    normalize_segments,
)
from main_app.models.base_model import BaseModel
from main_app.models.trope_element import TropeElement


class ChantCluster(BaseModel):
    """The structure of a troped chant: an ordered sequence of segments over a frozen
    snapshot of the untroped base text.

    A troped chant's text is not one blob — it alternates between the base chant's own
    words and interleaved tropes. Rather than storing copies of the base text's chunks, a
    cluster stores the base text once and its segments *reference* ranges of it (see
    ``ClusterSegment``). Three consequences motivated the design:

    - Splitting the base text into more pieces cannot inflate a count of its Cantus ID,
      because the ID lives here — one row per chant — and never on a segment.
    - Dropping base text is non-destructive. The snapshot is untouched; the segment list
      simply stops referencing that range, and ``omitted_ranges`` reports it.
    - Base text can be reordered or repeated (a repetendum), because a segment's position
      is its place in the sequence, not a coordinate in the base text.

    ``base_text`` is frozen once segments exist: segment ranges are indices into it, so
    editing it would silently shift every range. ``base_text_hash`` records what Cantus
    Index served at composition time, so later upstream drift is *detectable* without
    ever rewriting the snapshot the ranges are anchored to.

    The flattened text is cached on the chant's ``manuscript_full_text_std_spelling`` so
    display and search need no assembly. ``set_structure`` is the only write path, and it
    refreshes that cache in the same transaction.
    """

    TOKEN_SCHEME_WHITESPACE: str = "whitespace"
    TOKEN_SCHEME_CHOICES = [(TOKEN_SCHEME_WHITESPACE, "Whitespace-delimited words")]

    chant = models.OneToOneField(
        "Chant", related_name="cluster", on_delete=models.CASCADE
    )
    base_cantus_id = models.CharField(max_length=255, verbose_name="base cantus ID")
    base_text = models.TextField(
        help_text="The untroped base text. Frozen once segments exist."
    )
    base_text_hash = models.CharField(
        max_length=64,
        blank=True,
        help_text="Digest of the base text as Cantus Index served it, for drift detection",
    )
    # Recorded rather than assumed so a future move to syllable-level anchoring can
    # migrate existing clusters instead of silently reinterpreting their ranges.
    token_scheme = models.CharField(
        max_length=16,
        choices=TOKEN_SCHEME_CHOICES,
        default=TOKEN_SCHEME_WHITESPACE,
    )

    def __str__(self) -> str:
        return f"Cluster on {self.base_cantus_id} (chant {self.chant_id})"

    @classmethod
    def from_db(cls, db, field_names, values):  # type: ignore[no-untyped-def]
        """Remember the stored base text so ``clean()`` can reject changes to it."""
        instance = super().from_db(db, field_names, values)
        # Guard against deferred loading (`.only(...)`), where reading the attribute
        # would fire a fresh query.
        if "base_text" in field_names:
            instance._loaded_base_text = instance.base_text
        return instance

    @staticmethod
    def hash_base_text(text: str) -> str:
        """Digest a base text for drift detection against Cantus Index.

        Whitespace is normalised first so cosmetic reflowing upstream doesn't read as a
        content change. (sha256 as a change detector, not a security primitive.)
        """
        return hashlib.sha256(" ".join(text.split()).encode("utf-8")).hexdigest()

    @property
    def base_tokens(self) -> list[str]:
        """The base text's tokens — the index space every segment range refers to."""
        return self.base_text.split()

    @property
    def base_token_count(self) -> int:
        return len(self.base_tokens)

    def segment_specs(self) -> list[SegmentSpec]:
        """This cluster's stored segments as plain specs, in rendered order."""
        return [
            SegmentSpec(
                start=segment.start,
                end=segment.end,
                element=segment.element,
                text=segment.text,
            )
            for segment in self.segments.select_related("element")
        ]

    def flatten(self) -> str:
        """The chant's full troped text, assembled from base text and tropes."""
        return flatten_segments(self.base_tokens, self.segment_specs())

    def as_payload(self) -> dict[str, Any]:
        """This cluster in the same shape the composer submits.

        Seeds an edit form, so the round trip through the composer is lossless: what the
        client receives is what it would have sent for the same structure.
        """
        segments: list[dict[str, Any]] = []
        for segment in self.segments.select_related("element"):
            if segment.start is not None:
                segments.append({"start": segment.start, "end": segment.end})
            elif segment.element_id is not None:
                segments.append(
                    {
                        "cantus_id": segment.element.cantus_id,
                        "text": segment.element.text,
                    }
                )
            else:
                segments.append({"text": segment.text})
        return {
            "base_cantus_id": self.base_cantus_id,
            "base_text": self.base_text,
            "segments": segments,
        }

    @property
    def omitted_ranges(self) -> list[tuple[int, int]]:
        """Base-text ranges no segment references. Derived, never stored."""
        return compute_omitted_ranges(self.base_token_count, self.segment_specs())

    def clean(self) -> None:
        super().clean()
        if not self.base_text.split():
            raise ValidationError(
                {"base_text": "The base text must contain at least one word."}
            )
        loaded: Optional[str] = getattr(self, "_loaded_base_text", None)
        if (
            loaded is not None
            and loaded != self.base_text
            and self.pk
            and self.segments.exists()
        ):
            raise ValidationError(
                {
                    "base_text": (
                        "The base text is frozen while this cluster has segments, "
                        "because segment ranges are indices into it. Delete the cluster "
                        "and rebuild it to re-anchor."
                    )
                }
            )

    @classmethod
    def apply_payload(cls, chant: Any, payload: ClusterPayload) -> "ChantCluster":
        """Create or replace ``chant``'s cluster from a parsed payload.

        Trope references arrive as Cantus ID strings and are resolved to shared
        ``TropeElement`` rows here. A Cantus ID with no row yet gets one from the text the
        client supplied; an existing row's text is deliberately left alone, so editing one
        chant cannot rewrite a trope everywhere else it appears.

        A payload whose base text differs from the stored snapshot is a re-anchoring: the
        incoming ranges index into the *new* text, so the old segments are meaningless and
        are dropped before the snapshot is replaced.
        """
        base_text: str = payload["base_text"]
        with transaction.atomic():
            cluster, created = cls.objects.get_or_create(
                chant=chant,
                defaults={
                    "base_cantus_id": payload["base_cantus_id"],
                    "base_text": base_text,
                    "base_text_hash": cls.hash_base_text(base_text),
                },
            )
            if not created and cluster.base_text != base_text:
                cluster.segments.all().delete()
                cluster.base_cantus_id = payload["base_cantus_id"]
                cluster.base_text = base_text
                cluster.base_text_hash = cls.hash_base_text(base_text)
                cluster.save()
            resolved: list[dict[str, Any]] = [
                {
                    "start": segment["start"],
                    "end": segment["end"],
                    "element": cls._resolve_trope(segment),
                    "text": segment["text"],
                }
                for segment in payload["segments"]
            ]
            cluster.set_structure(resolved)
        return cluster

    @staticmethod
    def _resolve_trope(segment: dict[str, Any]) -> Optional[TropeElement]:
        """The shared row for a segment's catalogued trope, creating it if it's new."""
        cantus_id: Optional[str] = segment.get("element")
        if not cantus_id:
            return None
        element, _ = TropeElement.objects.get_or_create(
            cantus_id=cantus_id,
            defaults={"text": segment["element_text"]},
        )
        return element

    def set_structure(self, segments: Sequence[Any]) -> list[SegmentSpec]:
        """Replace this cluster's segments and refresh the chant's cached full text.

        The only write path for a cluster's structure. The whole list is validated and
        canonicalised before anything is written, so a rejected payload leaves the
        cluster exactly as it was; and the chant's flattened text is rewritten in the
        same transaction, so the structure and its cache cannot disagree.

        The cluster row is locked for the duration. This is a wholesale replace, so two
        cataloguers saving concurrently would otherwise silently lose one's work.

        Returns the canonicalised specs that were stored.
        """
        # Imported here rather than at module level: ClusterSegment's foreign key points
        # back at this model, so a top-level import would be circular.
        from main_app.models.cluster_segment import ClusterSegment

        with transaction.atomic():
            locked = ChantCluster.objects.select_for_update().get(pk=self.pk)
            normalized: list[SegmentSpec] = normalize_segments(
                locked.base_token_count, segments
            )
            locked.segments.all().delete()
            for order, segment in enumerate(normalized):
                ClusterSegment(
                    cluster=locked,
                    order=order,
                    start=segment["start"],
                    end=segment["end"],
                    element=segment["element"],
                    text=segment["text"],
                ).save()
            chant = locked.chant
            chant.manuscript_full_text_std_spelling = flatten_segments(
                locked.base_tokens, normalized
            )
            # update_fields is required for django-reversion to record the change; see
            # the same note in management/commands/copy_chants_to_master_source.py.
            chant.save(
                update_fields=["manuscript_full_text_std_spelling", "date_updated"]
            )
        return normalized
