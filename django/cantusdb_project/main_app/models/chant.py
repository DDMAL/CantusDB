from django.contrib.postgres.fields import JSONField
from django.contrib.postgres.search import SearchVectorField
from django.db import models
from main_app.models import BaseModel
from users.models import User


class Chant(BaseModel):
    incipit = models.CharField(max_length=255, null=True, blank=True)
    source = models.ForeignKey(
        "Source", on_delete=models.PROTECT, null=True, blank=True
    )
    marginalia = models.CharField(max_length=63, null=True, blank=True)
    folio = models.CharField(
        help_text="Binding order", blank=True, null=True, max_length=63
    )
    sequence_number = models.PositiveIntegerField(
        help_text='Each folio starts with "1"', null=True, blank=True
    )
    office = models.ForeignKey(
        "Office", on_delete=models.PROTECT, null=True, blank=True
    )
    genre = models.ForeignKey(
        "Genre", on_delete=models.PROTECT, null=True, blank=True
    )
    position = models.CharField(max_length=63, null=True, blank=True)
    cantus_id = models.CharField(max_length=63, null=True, blank=True)
    feast = models.ForeignKey(
        "Feast", on_delete=models.PROTECT, null=True, blank=True
    )
    mode = models.CharField(max_length=63, null=True, blank=True)
    differentia = models.CharField(blank=True, null=True, max_length=63)
    finalis = models.CharField(blank=True, null=True, max_length=63)
    extra = models.CharField(blank=True, null=True, max_length=63)
    chant_range = models.CharField(
        blank=True,
        null=True,
        help_text='Example: "1-c-k-4". Optional field',
        max_length=255,
    )
    addendum = models.CharField(blank=True, null=True, max_length=255)
    manuscript_full_text_std_spelling = models.TextField(
        help_text="Manuscript full text with standardized spelling. Enter the words "
        "according to the manuscript but normalize their spellings following "
        "Classical Latin forms. Use upper-case letters for proper nouns, "
        'the first word of each chant, and the first word after "Alleluia" for '
        "Mass Alleluias. Punctuation is omitted.",
        null=True,
        blank=True,
    )
    manuscript_full_text_std_proofread = models.NullBooleanField(
        blank=True, null=True
    )
    manuscript_full_text = models.TextField(
        help_text="Enter the wording, word order and spellings as found in the manuscript"
        ", with abbreviations resolved to standard words. Use upper-case letters as found"
        " in the source. Retain “Xpistum” (Christum), “Ihc” (Jesus) and other instances of "
        "Greek characters with their closest approximations of Latin letters. Some punctuation"
        " signs and vertical dividing lines | are employed in this field. Repetenda and psalm "
        "cues can also be recorded here. For more information, contact Cantus Database staff.",
        null=True,
        blank=True,
    )
    manuscript_full_text_proofread = models.NullBooleanField(
        blank=True, null=True
    )
    manuscript_syllabized_full_text = models.TextField(null=True, blank=True)
    volpiano = models.TextField(null=True, blank=True)
    volpiano_proofread = models.NullBooleanField(blank=True, null=True)
    image_link = models.URLField(blank=True, null=True)
    cao_concordances = models.CharField(blank=True, null=True, max_length=63)
    proofread_by = models.ForeignKey(
        User, on_delete=models.PROTECT, null=True, blank=True
    )
    melody_id = models.CharField(blank=True, null=True, max_length=63)
    sylabilized_full_text = models.TextField(blank=True, null=True)
    indexing_notes = models.TextField(blank=True, null=True)
    json_info = JSONField(null=True, blank=True)
    search_vector = SearchVectorField(null=True, editable=False)

    def index_components(self) -> dict:
        """Constructs a dictionary of weighted lists of search terms

        Returns:
            dict: A dictionary of lists of search terms, the keys are the
                  different weights
        """
        incipit = self.incipit if self.incipit else None
        full_text = (
            self.manuscript_full_text if self.manuscript_full_text else None
        )
        full_text_std_spelling = (
            self.manuscript_full_text_std_spelling
            if self.manuscript_full_text_std_spelling
            else None
        )
        source = self.source.title if self.source else None
        genre = self.genre.name if self.genre else None
        feast = self.feast.name if self.feast else None
        office = self.office.name if self.office else None
        return {
            "A": (
                " ".join(
                    filter(
                        None,
                        [incipit, full_text, full_text_std_spelling, source],
                    )
                )
            ),
            "B": (" ".join(filter(None, [genre, feast, office]))),
        }
