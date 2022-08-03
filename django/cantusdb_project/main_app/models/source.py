from django.db import models
from main_app.models import BaseModel
from django.contrib.auth import get_user_model


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

    # Here, "public" indicates whether a source will EVER be seen by the public. 
    # `public=True` for regular sources, which might not be published yet but will eventually be.
    # `public=False` for test sources, which are only for testing purpose and will never be published. 

    # If `public=True` & `published=True`, the source is accessible to the public.

    # If `public=True` & `published=False`, the source is a work in progress. 
    # It's hidden from the public, but can be seen in lists and through urls for logged-in users.

    # If `public=False`, the source is a test/hidden source.
    # It's hidden from the public and it doesn't appear in lists.
    # The only access is through the url by logged-in users.
    
    public = models.BooleanField(blank=True, null=True)
    published = models.BooleanField(blank=True, null=True)

    title = models.CharField(
        max_length=255,
        help_text="Full Manuscript Identification (City, Archive, Shelf-mark)",
    )
    # the siglum field as implemented on the old Cantus is composed of both the RISM siglum and the shelfmark
    # it is a human-readable ID for a source
    siglum = models.CharField(
        max_length=63, 
        null=True, 
        blank=True,
        help_text="RISM-style siglum + Shelf-mark (e.g. GB-Ob 202).",
    )
    # the RISM siglum uniquely identifies a library or holding institution
    rism_siglum = models.ForeignKey(
        "RismSiglum", on_delete=models.PROTECT, null=True, blank=True,
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
    full_source = models.BooleanField(blank=True, null=True)
    date = models.CharField(
        blank=True,
        null=True,
        max_length=63,
        help_text='Date of the manuscript (e.g. "1200s", "1300-1350", etc.)',
    )
    century = models.ManyToManyField("Century", related_name="sources")
    notation = models.ManyToManyField("Notation", related_name="sources")
    cursus = models.CharField(
        blank=True, null=True, choices=cursus_choices, max_length=63
    )
    current_editors = models.ManyToManyField(get_user_model(), related_name="sources_edited")
    created_by = models.ForeignKey(
        get_user_model(), related_name="sources_created", on_delete=models.CASCADE, blank=True, null=True
    )
    inventoried_by = models.ManyToManyField(
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
    source_status = models.CharField(blank=True, null=True, choices=source_status_choices, max_length=255)
    complete_inventory = models.BooleanField(blank=True, null=True)
    summary = models.TextField(blank=True, null=True)
    liturgical_occasions = models.TextField(blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    selected_bibliography = models.TextField(blank=True, null=True)
    image_link = models.URLField(
        blank=True, 
        null=True,
        help_text='HTTP link to the image gallery of the source.',
    )
    indexing_notes = models.TextField(blank=True, null=True)
    indexing_date = models.TextField(blank=True, null=True)
    json_info = models.JSONField(blank=True, null=True)
    fragmentarium_id = models.CharField(max_length=15, blank=True, null=True)
    dact_id = models.CharField(max_length=15, blank=True, null=True)

    def number_of_chants(self) -> int:
        """Returns the number of Chants and Sequences in this Source."""
        return self.chant_set.count() + self.sequence_set.count()

    def number_of_melodies(self) -> int:
        """Returns the number of Chants in this Source that have melodies."""
        return self.chant_set.filter(volpiano__isnull=False).count()

    def __str__(self):
        string = '{t} ({i})'.format(t=self.title, i=self.id)
        return string

    