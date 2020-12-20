from django.db import models
from main_app.models import BaseModel
from users.models import User
from django.contrib.postgres.fields import JSONField


class Chant(BaseModel):
    incipt = models.CharField(max_length=256, null=True, blank=True)
    source = models.ForeignKey(
        "Source", on_delete=models.PROTECT, null=False, blank=False
    )
    marginalia = models.CharField(max_length=64, null=True, blank=True)
    folio = models.CharField(
        help_text='Binding order', blank=True, null=True, max_length=64
    )
    sequence_number = models.PositiveIntegerField(
        help_text='Each folio starts with "1"', null=True, blank=True
    )
    office = models.ForeignKey(
        "Office", on_delete=models.PROTECT, null=True, blank=True
    )
    genre = models.ForeignKey("Genre", on_delete=models.PROTECT, null=True, blank=True)
    position = models.CharField(max_length=64, null=True, blank=True)
    cantus_id = models.CharField(max_length=64, null=True, blank=True)
    feast = models.ForeignKey("Feast", on_delete=models.PROTECT, null=True, blank=True)
    mode = models.CharField(max_length=64, null=True, blank=True)
    differentia = models.CharField(blank=True, null=True, max_length=64)
    finalis = models.CharField(blank=True, null=True, max_length=64)
    extra = models.CharField(blank=True, null=True, max_length=64)
    chant_range = models.CharField(
        blank=True, null=True, help_text='Example: "1-c-k-4". Optional field', max_length=256
    )
    # TODO: look into the permissions of this field
    # addendum is important, should have a spot on input form, should be editable
    addendum = models.CharField(blank=True, null=True, max_length=256)
    # TODO: maybe change this to its own model?
    manuscript_full_text_std_spelling = models.TextField(
        help_text="Manuscript full text with standardized spelling. Enter the words "
        "according to the manuscript but normalize their spellings following "
        "Classical Latin forms. Use upper-case letters for proper nouns, "
        'the first word of each chant, and the first word after "Alleluia" for '
        "Mass Alleluias. Punctuation is omitted.",
        null=True,
        blank=True,
    )
    manuscript_full_text_std_proofread = models.NullBooleanField(blank=True, null=True)
    # TODO: maybe change it to its own model?
    manuscript_full_text = models.TextField(
        help_text="Enter the wording, word order and spellings as found in the manuscript"
        ", with abbreviations resolved to standard words. Use upper-case letters as found"
        " in the source. Retain “Xpistum” (Christum), “Ihc” (Jesus) and other instances of "
        "Greek characters with their closest approximations of Latin letters. Some punctuation"
        " signs and vertical dividing lines | are employed in this field. Repetenda and psalm "
        "cues can also be recorded here. For more information, contact Cantus Database staff.",
        null=True, 
        blank=True
    )
    manuscript_full_text_proofread = models.NullBooleanField(blank=True, null=True)
    manuscript_syllabized_full_text = models.TextField(null=True, blank=True)
    # TODO: maybe change this to its own model?
    volpiano = models.TextField(null=True, blank=True)
    volpiano_proofread = models.NullBooleanField(blank=True, null=True)
    image_link = models.URLField(blank=True, null=True)
    # TODO: look into permissions for this field
    # cao_concordances is not needed anymore 2020-12-16
    # cao_concordances = models.CharField(blank=True, null=True, max_length=64)
    proofread_by = models.ForeignKey(
        User, on_delete=models.PROTECT, null=True, blank=True
    )
    melody_id = models.CharField(blank=True, null=True, max_length=64)
    sylabilized_full_text = models.TextField(blank=True, null=True)
    indexing_notes = models.TextField(blank=True, null=True)
    json_info = JSONField(null=True, blank=True)

    # newly-added fields 2020-11-27
    # not sure what field type we should use exactly
    
    # content_structure = models.CharField(
    #     blank=True, null=True, max_length=64,
    #     help_text="Additional folio number field, if folio numbers appear on the leaves but are not in the 'binding order'."
    #     )
    # fragmentarium_id = models.CharField(blank=True, null=True, max_length=64)
    # # Digital Analysis of Chant Transmission
    # dact = models.CharField(blank=True, null=True, max_length=64)
    # also a second differentia field