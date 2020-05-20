from django.db import models
from main_app.models import CustomBaseModel
from psycopg2.extras import NumericRange
from django.contrib.postgres.fields import IntegerRangeField


class Source(CustomBaseModel):
    century_choices = [
        (NumericRange(800, 901), "09th century"),
        (NumericRange(875, 901), "09th century (875-900)"),
        (NumericRange(900, 1001), "10th century"),
        (NumericRange(900, 951), "10th century (1st half)"),
        (NumericRange(900, 926), "10th century (900-925)"),
        (NumericRange(925, 951), "10th century (925-950)"),
        (NumericRange(950, 1001), "10th century (2nd half)"),
        (NumericRange(950, 976), "10th century (950-975)"),
        (NumericRange(975, 1001), "10th century (975-1000)"),
        (NumericRange(1000, 1101), "11th century"),
        (NumericRange(1000, 1051), "11th century (1st half)"),
        (NumericRange(1000, 1026), "11th century (1000-1025)"),
        (NumericRange(1025, 1051), "11th century (1025-1050)"),
        (NumericRange(1050, 1101), "11th century (2nd half)"),
        (NumericRange(1050, 1076), "11th century (1050-1075)"),
        (NumericRange(1075, 1101), "11th century (1075-1100)"),
        (NumericRange(1100, 1201), "12th century"),
        (NumericRange(1100, 1151), "12th century (1st half)"),
        (NumericRange(1100, 1126), "12th century (1100-1125)"),
        (NumericRange(1125, 1151), "12th century (1125-1150)"),
        (NumericRange(1150, 1201), "12th century (2nd half)"),
        (NumericRange(1150, 1176), "12th century (1150-1175)"),
        (NumericRange(1175, 1201), "12th century (1175-1200)"),
        (NumericRange(1200, 1301), "13th century"),
        (NumericRange(1200, 1251), "13th century (1st half)"),
        (NumericRange(1200, 1226), "13th century (1200-1225)"),
        (NumericRange(1225, 1251), "13th century (1225-1250)"),
        (NumericRange(1250, 1301), "13th century (2nd half)"),
        (NumericRange(1250, 1276), "13th century (1250-1275)"),
        (NumericRange(1275, 1301), "13th century (1275-1300)"),
        (NumericRange(1300, 1401), "14th century"),
        (NumericRange(1300, 1351), "14th century (1st half)"),
        (NumericRange(1300, 1326), "14th century (1300-1325)"),
        (NumericRange(1325, 1351), "14th century (1325-1350)"),
        (NumericRange(1350, 1401), "14th century (2nd half)"),
        (NumericRange(1350, 1376), "14th century (1350-1375)"),
        (NumericRange(1375, 1401), "14th century (1375-1400)"),
        (NumericRange(1400, 1501), "15th century"),
        (NumericRange(1400, 1451), "15th century (1st half)"),
        (NumericRange(1400, 1426), "15th century (1400-1425)"),
        (NumericRange(1425, 1451), "15th century (1425-1450)"),
        (NumericRange(1450, 1501), "15th century (2nd half)"),
        (NumericRange(1450, 1476), "15th century (1450-1475)"),
        (NumericRange(1475, 1501), "15th century (1475-1500)"),
        (NumericRange(1500, 1601), "16th century"),
        (NumericRange(1500, 1551), "16th century (1st half)"),
        (NumericRange(1500, 1526), "16th century (1500-1525)"),
        (NumericRange(1525, 1551), "16th century (1525-1550)"),
        (NumericRange(1550, 1601), "16th century (2nd half)"),
        (NumericRange(1550, 1576), "16th century (1550-1575)"),
        (NumericRange(1575, 1601), "16th century (1575-1600)"),
        (NumericRange(1600, 1701), "17th century"),
        (NumericRange(1600, 1651), "17th century (1st half)"),
        (NumericRange(1600, 1626), "17th century (1600-1625)"),
    ]
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
    rism_siglum = models.ForeignKey(
        "RismSiglum", on_delete=models.PROTECT, blank=True, null=True
    )
    siglum = models.CharField(
        max_length=50, help_text="RISM-style siglum + Shelf-mark (e.g. GB-Ob 202)."
    )
    provenance = models.ForeignKey(
        "Provenance",
        on_delete=models.PROTECT,
        help_text="If the origin is unknown, select a location where the source was "
        "used later in its lifetime and provide details in the "
        '"Provenancenotes" field.',
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
    century = IntegerRangeField(blank=True, null=True, choices=century_choices)
    notation = models.ManyToManyField("Notation", related_name="sources")
    cursus = models.CharField(
        blank=True, null=True, choices=cursus_choices, max_length=10
    )
    # TODO: make user model
    current_editors = models.ManyToManyField("User", related_name="sources_edited")
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
    notes_on_inventory = models.TextField(blank=True, null=True)
    indexing_date = models.DateField(blank=True, null=True)
