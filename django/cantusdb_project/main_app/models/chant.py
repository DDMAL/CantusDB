from django.db import models
from main_app.models import BaseModel
from users.models import User


class Chant(BaseModel):
    incipt = models.CharField(max_length=255)
    source = models.ForeignKey("Source", on_delete=models.PROTECT)
    marginalia = models.CharField(max_length=10)
    folio = models.CharField(blank=True, null=True, max_length=10)
    sequence_number = models.PositiveIntegerField(
        help_text='Each folio starts with "1"'
    )
    office = models.ForeignKey("Office", on_delete=models.PROTECT)
    genre = models.ForeignKey("Genre", on_delete=models.PROTECT)
    position = models.CharField(max_length=10)
    cantus_id = models.CharField(max_length=10)
    feast = models.ForeignKey("Feast", on_delete=models.PROTECT)
    mode = models.CharField(max_length=20)
    differentia = models.CharField(blank=True, null=True, max_length=20)
    finalis = models.CharField(blank=True, null=True, max_length=20)
    extra = models.CharField(blank=True, null=True, max_length=50)
    chant_range = models.CharField(
        blank=True, null=True, help_text='Example: "1-c-k-4".', max_length=255
    )
    # TODO: look into the permissions of this field
    addendum = models.CharField(blank=True, null=True, max_length=255)
    # TODO: maybe change this to its own model?
    manuscript_full_text_std_spelling = models.TextField(
        help_text="Manuscript full text with standardized spelling. Enter the words "
        "according to the manuscript but normalize their spellings following "
        "Classical Latin forms. Use upper-case letters for proper nouns, "
        'the first word of each chant, and the first word after "Alleluia" for '
        "Mass Alleluias. Punctuation is omitted."
    )
    manuscript_full_text_std_proofread = models.NullBooleanField(blank=True, null=True)
    # TODO: maybe change it to its own model?
    manuscript_full_text = models.TextField()
    manuscript_full_text_proofread = models.NullBooleanField(blank=True, null=True)
    # TODO: maybe change this to its own model?
    volpiano = models.TextField()
    volpiano_proofread = models.NullBooleanField(blank=True, null=True)
    image_link = models.URLField(blank=True, null=True)
    # TODO: look into permissions for this field
    cao_concordances = models.CharField(blank=True, null=True, max_length=20)
    siglum = models.CharField(blank=True, null=True, max_length=99)
    proofread_by = models.ForeignKey(User, on_delete=models.PROTECT)
    melody_id = models.CharField(blank=True, null=True, max_length=50)
    sylabilized_full_text = models.TextField(blank=True, null=True)
    indexing_notes = models.TextField(blank=True, null=True)
