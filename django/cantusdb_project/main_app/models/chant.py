from django.contrib.postgres.fields import JSONField
from django.contrib.postgres.search import SearchVectorField
from django.db import models

from django.db.models.query import QuerySet
from django.urls.base import reverse
from main_app.models import BaseModel
from users.models import User


class Chant(BaseModel):
    # The following fields include the "dummy fields" used to harmonize the chant and sequence model
    # Those fields should never be populated or displayed
    # Order of the fields must be the same between the seq and chant models
    # That's why the "dummy fields" are not grouped together
    visible_status = models.CharField(max_length=1, blank=True, null=True)
    title = models.CharField(blank=True, null=True, max_length=255)
    incipit = models.CharField(blank=True, null=True, max_length=255)
    siglum = models.CharField(blank=True, null=True, max_length=255)
    folio = models.CharField(
        help_text="Binding order", blank=True, null=True, max_length=255, db_index=True
    )
    sequence = models.CharField(blank=True, null=True, max_length=255)
    genre = models.ForeignKey("Genre", blank=True, null=True, on_delete=models.PROTECT)
    rubrics = models.CharField(blank=True, null=True, max_length=255)
    analecta_hymnica = models.CharField(blank=True, null=True, max_length=255)
    indexing_notes = models.TextField(blank=True, null=True)
    date = models.CharField(blank=True, null=True, max_length=255)
    col1 = models.CharField(blank=True, null=True, max_length=255)
    col2 = models.CharField(blank=True, null=True, max_length=255)
    col3 = models.CharField(blank=True, null=True, max_length=255)
    ah_volume = models.CharField(blank=True, null=True, max_length=255)
    source = models.ForeignKey(
        "Source", on_delete=models.PROTECT, null=True, blank=True
    )  # PROTECT so that we can't delete a source with chants in it
    cantus_id = models.CharField(blank=True, null=True, max_length=255, db_index=True)
    image_link = models.URLField(blank=True, null=True)
    json_info = JSONField(null=True, blank=True)
    marginalia = models.CharField(max_length=63, null=True, blank=True)
    sequence_number = models.PositiveIntegerField(
        help_text='Each folio starts with "1"', null=True, blank=True
    )
    office = models.ForeignKey(
        "Office", on_delete=models.PROTECT, null=True, blank=True
    )
    position = models.CharField(max_length=63, null=True, blank=True)
    # add db_index to speed up filtering
    feast = models.ForeignKey("Feast", on_delete=models.PROTECT, null=True, blank=True)
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
    manuscript_full_text_std_proofread = models.NullBooleanField(blank=True, null=True)
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
    manuscript_full_text_proofread = models.NullBooleanField(blank=True, null=True)
    manuscript_syllabized_full_text = models.TextField(null=True, blank=True)
    volpiano = models.TextField(null=True, blank=True)
    volpiano_proofread = models.NullBooleanField(blank=True, null=True)
    cao_concordances = models.CharField(blank=True, null=True, max_length=63)
    proofread_by = models.ForeignKey(
        User, on_delete=models.PROTECT, null=True, blank=True
    )
    melody_id = models.CharField(blank=True, null=True, max_length=63)
    search_vector = SearchVectorField(null=True, editable=False)
    # newly-added fields 2020-11-27
    content_structure = models.CharField(
        blank=True,
        null=True,
        max_length=64,
        help_text="Additional folio number field, if folio numbers appear on the leaves but are not in the 'binding order'.",
    )
    # fragmentarium_id = models.CharField(blank=True, null=True, max_length=64)
    # # Digital Analysis of Chant Transmission
    # dact = models.CharField(blank=True, null=True, max_length=64)
    # also a second differentia field

    def index_components(self) -> dict:
        """Constructs a dictionary of weighted lists of search terms.

        Returns:
            dict: A dictionary of lists of search terms, the keys are the
                  different weights
        """
        incipit = self.incipit if self.incipit else None
        full_text = self.manuscript_full_text if self.manuscript_full_text else None
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
                    filter(None, [incipit, full_text, full_text_std_spelling, source],)
                )
            ),
            "B": (" ".join(filter(None, [genre, feast, office]))),
        }

    def related_chants_by_cantus_id(self) -> QuerySet:
        return Chant.objects.filter(cantus_id=self.cantus_id)

    def get_next_chant(self):
        """return the next chant in the same source
        Returns:
            chant_object/None: the next chant object, or None if there is no next chant
        """

        def get_next_folio(folio):
            """This is useful when the 'next chant' we need is on the next folio
            Args:
                folio (str): the folio number of a certain chant
            Returns:
                str: the folio number of the next folio
            """
            # For the ra, rb, va, vb - don't do anything about those. That formatting will not stay.
            if folio is None:
                # this shouldn't happen, but during testing, we may have some chants without folio
                next_folio = "nosuchfolio"
            elif folio == "001b":
                # one specific case at this source https://cantus.uwaterloo.ca/chants?source=123612&folio=001b
                next_folio = "001r"
            elif folio.endswith("r"):
                # 001r -> 001v
                next_folio = folio[:-1] + "v"
            elif folio.endswith("v"):
                if folio[0].isdecimal():
                    # 001v -> 002r
                    next_folio = str(int(folio[:-1]) + 1).zfill(len(folio) - 1) + "r"
                else:
                    # a001v -> a002r
                    next_folio = (
                        folio[0] + str(int(folio[1:-1]) + 1).zfill(len(folio) - 1) + "r"
                    )
            elif folio.isdecimal():
                # 001 -> 002
                next_folio = str(int(folio) + 1).zfill(len(folio))

            # special case: inserted pages
            elif folio.endswith("w"):
                # 001w -> 001x
                next_folio = folio[:-1] + "x"
            elif folio.endswith("y"):
                # 001y -> 001z
                next_folio = folio[:-1] + "z"
            elif folio.endswith("a"):
                # 001a -> 001b
                next_folio = folio[:-1] + "b"

            else:
                # using weird folio naming
                next_folio = "nosuchfolio"
            return next_folio

        try:
            next_chant = Chant.objects.get(
                source=self.source,
                folio=self.folio,
                sequence_number=self.sequence_number + 1,
            )
        except:
            chants_next_folio = Chant.objects.filter(
                source=self.source, folio=get_next_folio(self.folio)
            ).order_by("-sequence_number")
            try:
                next_chant = chants_next_folio[0]
            except:
                next_chant = None
        return next_chant
