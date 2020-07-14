from django.db import models
from main_app.models import BaseModel
from psycopg2.extras import NumericRange
from django.contrib.postgres.fields import IntegerRangeField
from django.contrib.postgres.fields import JSONField
from users.models import User


class Source(BaseModel):
    source_fragment_choices = [(True, "Full Source"), (False, "Fragment or Fragmented")]
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
    ]
    complete_inventory_choices = [
        (True, "Complete Inventory"),
        (False, "Partial Inventory"),
    ]

    title = models.CharField(
        max_length=255,
        help_text="Full Manuscript Identification (City, Archive, Shelf-mark)",
    )
    rism_siglum = models.CharField(max_length=50, null=True, blank=True)
    siglum = models.ForeignKey(
        "Siglum",
        on_delete=models.PROTECT,
        help_text="RISM style siglum + shelf mark",
        null=True,
        blank=True,
    )
    provenance = models.ForeignKey(
        "Provenance",
        on_delete=models.PROTECT,
        help_text="If the origin is unknown, select a location where the source was "
        "used later in its lifetime and provide details in the "
        '"Provenance notes" field.',
        null=True,
        blank=True,
    )
    provenance_notes = models.TextField(
        blank=True,
        null=True,
        help_text="More exact indication of the provenance (if necessary)",
    )
    full_source = models.BooleanField(
        blank=True, null=True, choices=source_fragment_choices
    )
    date = models.CharField(
        blank=True,
        null=True,
        max_length=50,
        help_text='Date of the manuscript (e.g. "1200s", "1300-1350", etc.)',
    )
    century = models.ForeignKey(
        "Century", on_delete=models.PROTECT, null=True, blank=True,
    )
    notation = models.ManyToManyField("Notation", related_name="sources")
    cursus = models.CharField(
        blank=True, null=True, choices=cursus_choices, max_length=10
    )
    current_editors = models.ManyToManyField(User, related_name="sources_edited")
    invetoried_by = models.ManyToManyField(
        "Indexer", related_name="sources_inventoried"
    )
    full_text_entered_by = models.ManyToManyField(
        "Indexer", related_name="entered_full_text_for_sources"
    )
    melodies_entered_by = models.ManyToManyField(
        "Indexer", related_name="entered_melody_for_sources"
    )
    proofreaders = models.ManyToManyField("Indexer", related_name="proofread_sources")
    other_editors = models.ManyToManyField("Indexer", related_name="edited_sources")
    segment = models.ForeignKey(
        "Segment", on_delete=models.PROTECT, blank=True, null=True
    )
    source_status = models.CharField(
        blank=True, null=True, choices=source_status_choices, max_length=255
    )
    complete_inventory = models.BooleanField(
        blank=True, null=True, choices=complete_inventory_choices
    )
    summary = models.TextField(blank=True, null=True)
    liturgical_occasions = models.TextField(blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    selected_bibliography = models.TextField(blank=True, null=True)
    image_link = models.URLField(blank=True, null=True)
    indexing_date = models.DateField(blank=True, null=True)
    indexing_notes = models.TextField(blank=True, null=True)
