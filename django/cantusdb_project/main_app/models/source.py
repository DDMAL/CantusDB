from typing import Optional

from django.db import models
from django.contrib.auth import get_user_model

from main_app.models.url_field import NormalizedURLField
from main_app.models import BaseModel, Segment
from main_app.models.source_url import SourceURL


class Source(BaseModel):
    cursus_choices = [("Monastic", "Monastic"), ("Secular", "Secular")]
    source_status_choices = [
        (
            "Editing process (not all the fields have been proofread)",
            "Editing process (not all the fields have been proofread)",
        ),
        ("Published / Complete", "Published / Complete"),
        ("Published / Proofread pending", "Published / Proofread pending"),
        ("Unpublished / Editing process", "Unpublished / Editing process"),
        ("Unpublished / Indexing process", "Unpublished / Indexing process"),
        ("Unpublished / Proofread pending", "Unpublished / Proofread pending"),
        ("Unpublished / Proofreading process", "Unpublished / Proofreading process"),
        ("Unpublished / No indexing activity", "Unpublished / No indexing activity"),
    ]

    # The old Cantus uses two fields to jointly control the access to sources.
    # Here in the new Cantus, we only use one field, and there are two levels: published and unpublished.
    # Published sources are available to the public.
    # Unpublished sources are hidden from the list and cannot be accessed by URL until the user logs in.
    published = models.BooleanField(blank=False, null=False, default=False)

    title = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Full Source Identification (City, Archive, Shelf-mark)",
    )
    # the siglum field as implemented on the old Cantus is composed of both the RISM siglum and the shelfmark
    # it is a human-readable ID for a source
    siglum = models.CharField(
        max_length=63,
        null=True,
        blank=True,
        help_text="RISM-style siglum + Shelf-mark (e.g. GB-Ob 202).",
    )
    holding_institution = models.ForeignKey(
        "Institution",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )
    shelfmark = models.CharField(
        max_length=255,
        blank=False,
        null=False,
        help_text=(
            "Primary Cantus Database identifier for the source "
            "(e.g. library shelfmark, DACT ID, etc.)"
        ),
        default="[No Shelfmark]",
    )
    name = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="A colloquial or commonly-used name for the source",
    )
    provenance = models.ForeignKey(
        "Provenance",
        on_delete=models.PROTECT,
        help_text="If the origin is unknown, select a location where the source was "
        "used later in its lifetime and provide details in the "
        '"Provenance notes" field.',
        null=True,
        blank=True,
        related_name="sources",
    )
    provenance_notes = models.TextField(
        blank=True,
        null=True,
        help_text="More exact indication of the provenance (if necessary)",
    )

    class SourceCompletenessChoices(models.IntegerChoices):
        FULL_SOURCE = 1, "Complete (or mostly complete)"
        FRAGMENTED = 4, "Fragmented"
        FRAGMENT = 2, "Fragment"
        RECONSTRUCTION = 3, "Reconstruction"
        UNKNOWN = 5, "Unknown"

    source_completeness = models.IntegerField(
        choices=SourceCompletenessChoices.choices,
        default=SourceCompletenessChoices.FULL_SOURCE,
        verbose_name="Physical Status",
    )

    full_source = models.BooleanField(blank=True, null=True)
    date = models.CharField(
        blank=True,
        null=True,
        max_length=63,
        help_text='Date of the source, if known (e.g. "1541")',
    )
    century = models.ManyToManyField("Century", related_name="sources", blank=True)
    notation = models.ManyToManyField("Notation", related_name="sources", blank=True)
    cursus = models.CharField(
        blank=True, null=True, choices=cursus_choices, max_length=63
    )
    current_editors = models.ManyToManyField(
        get_user_model(), related_name="sources_user_can_edit", blank=True
    )

    ######
    # The following seven fields have nothing to do with user permissions;
    # instead they give credit to users who are contributors/editors (e.g.,
    # indexers, data contributors, proofreaders) and are displayed on the
    # user detail page as sources the user has contributed to.
    inventoried_by = models.ManyToManyField(
        get_user_model(), related_name="inventoried_sources", blank=True
    )
    full_text_entered_by = models.ManyToManyField(
        get_user_model(), related_name="entered_full_text_for_sources", blank=True
    )
    melodies_entered_by = models.ManyToManyField(
        get_user_model(), related_name="entered_melody_for_sources", blank=True
    )
    description_entered_by = models.ManyToManyField(
        get_user_model(),
        verbose_name="description written by",
        related_name="entered_description_for_sources",
        blank=True,
    )
    proofreaders = models.ManyToManyField(
        get_user_model(), related_name="proofread_sources", blank=True
    )
    other_editors = models.ManyToManyField(
        get_user_model(), related_name="edited_sources", blank=True
    )
    source_data_contributed_by = models.ManyToManyField(
        get_user_model(),
        verbose_name="source metadata contributed by",
        related_name="contributed_data_for_sources",
        blank=True,
    )
    ######

    segment = models.ForeignKey(
        "Segment", on_delete=models.PROTECT, blank=True, null=True
    )
    segment_m2m = models.ManyToManyField(
        "Segment", blank=True, related_name="sources", verbose_name="Segments"
    )
    source_status = models.CharField(
        blank=True, null=True, choices=source_status_choices, max_length=255
    )
    complete_inventory = models.BooleanField(blank=True, null=True)
    summary = models.TextField(blank=True, null=True)
    liturgical_occasions = models.TextField(blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    selected_bibliography = models.TextField(blank=True, null=True)
    image_link = NormalizedURLField(
        blank=True,
        null=True,
        help_text="HTTP link to the image gallery of the source.",
    )
    indexing_notes = models.TextField(blank=True, null=True)
    indexing_date = models.TextField(blank=True, null=True)
    json_info = models.JSONField(blank=True, null=True)
    fragmentarium_id = models.CharField(
        max_length=15, blank=True, null=True, verbose_name="fragmentarium ID"
    )
    dact_id = models.CharField(
        max_length=15, blank=True, null=True, verbose_name="DACT ID"
    )
    exists_on_cantus_ultimus = models.BooleanField(
        blank=False, null=False, default=False
    )

    class ProductionMethodChoices(models.IntegerChoices):
        MANUSCRIPT = 1, "Manuscript"
        PRINT = 2, "Print"

    production_method = models.IntegerField(
        default=ProductionMethodChoices.MANUSCRIPT,
        choices=ProductionMethodChoices.choices,
        verbose_name="Manuscript/Print",
    )

    # number_of_chants and number_of_melodies are used for rendering the source-list page (perhaps among other places)
    # they are automatically recalculated in main_app.signals.update_source_chant_count and
    # main_app.signals.update_source_melody_count every time a chant or sequence is saved or deleted
    number_of_chants = models.IntegerField(blank=True, null=True)
    number_of_melodies = models.IntegerField(blank=True, null=True)

    def __str__(self) -> str:
        return self.heading

    @property
    def heading(self) -> str:
        title = []
        if holdinst := self.holding_institution:
            city = f"{holdinst.city}," if holdinst.city else ""
            title.append(city)
            title.append(f"{holdinst.name},")
        else:
            title.append("Cantus")

        title.append(self.shelfmark)

        if self.name:
            title.append(f'("{self.name}")')

        return " ".join(title)

    # Both properties below are transitional: once the legacy image_link column
    # is dropped (#1839, after populate_source_urls runs), external_images_url
    # collapses to a plain source_links lookup and show_legacy_image_link is
    # always False. Simplify or remove them then.
    @property
    def external_images_url(self) -> Optional[str]:
        """The URL of this source's external image gallery, or None.

        A source's image gallery can be recorded two ways: the legacy
        ``image_link`` field, or a ``SourceURL`` with url_type
        ``EXTERNAL_IMAGES``, which supersedes it. This returns whichever
        applies, so a page that renders a single "images" link renders one
        link no matter which mechanism a given source uses.

        Pages that render ``source_links`` themselves should use
        `show_legacy_image_link` instead, or the SourceURL will appear twice.

        Iterates source_links in Python rather than filtering in SQL so that
        this reads a ``prefetch_related("source_links")`` cache when the view
        provides one; a ``.filter()`` would cost a query per source.
        """
        # source_links is SourceURL's related_name; mypy cannot see reverse
        # relations without django-stubs, which this project does not install.
        for link in self.source_links.all():  # type: ignore[attr-defined]
            if link.url_type == SourceURL.URLTypes.EXTERNAL_IMAGES:
                return link.url
        return self.image_link or None

    @property
    def show_legacy_image_link(self) -> bool:
        """Whether to render the legacy ``image_link`` field as its own link.

        True only when the field is set and no ``EXTERNAL_IMAGES``
        ``SourceURL`` supersedes it. For pages that already render
        ``source_links``; see `external_images_url` for the rest.
        """
        return bool(self.image_link) and not any(
            link.url_type == SourceURL.URLTypes.EXTERNAL_IMAGES
            for link in self.source_links.all()  # type: ignore[attr-defined]
        )

    @staticmethod
    def compose_short_heading(institution_siglum: Optional[str], shelfmark: str) -> str:
        """Build a source's short heading from its component values.

        Kept separate from the `short_heading` property so that bulk exports,
        which read the underlying columns with `QuerySet.values()` rather than
        instantiating Source objects, produce identical strings.

        `feast_source_query` in `main_app/views/feast.py` reimplements this in
        SQL; keep the two in sync.
        """
        title = []
        if institution_siglum and institution_siglum != "XX-NN":
            title.append(institution_siglum)
        else:
            title.append("Cantus")

        title.append(shelfmark)

        return " ".join(title)

    @property
    def short_heading(self) -> str:
        holdinst = self.holding_institution
        return self.compose_short_heading(
            holdinst.siglum if holdinst else None, self.shelfmark
        )
