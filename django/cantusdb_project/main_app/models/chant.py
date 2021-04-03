from django.db import models
from main_app.models import BaseModel, sequence, source
from users.models import User
from django.contrib.postgres.fields import JSONField


class Chant(BaseModel):
    incipit = models.CharField(max_length=256, null=True, blank=True)
    source = models.ForeignKey(
        "Source", on_delete=models.PROTECT, null=False, blank=False
    )
    marginalia = models.CharField(max_length=64, null=True, blank=True)
    folio = models.CharField(
        help_text="Binding order", blank=True, null=True, max_length=64, db_index=True
    )
    sequence_number = models.PositiveIntegerField(
        help_text='Each folio starts with "1"', null=True, blank=True
    )
    office = models.ForeignKey(
        "Office", on_delete=models.PROTECT, null=True, blank=True
    )
    genre = models.ForeignKey("Genre", on_delete=models.PROTECT, null=True, blank=True)
    position = models.CharField(max_length=64, null=True, blank=True)
    cantus_id = models.CharField(
        max_length=64, null=True, blank=True, db_index=True
    )  # add db_index to speed up filtering
    feast = models.ForeignKey("Feast", on_delete=models.PROTECT, null=True, blank=True)
    mode = models.CharField(max_length=64, null=True, blank=True)
    differentia = models.CharField(blank=True, null=True, max_length=64)
    finalis = models.CharField(blank=True, null=True, max_length=64)
    extra = models.CharField(blank=True, null=True, max_length=64)
    chant_range = models.CharField(
        blank=True,
        null=True,
        help_text='Example: "1-c-k-4". Optional field',
        max_length=256,
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
        blank=True,
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

    # TODO change this function: if the chant is the last one on the folio, don't just give up,
    # return the first chant on the next folio
    # also, just return object, return a CantusID is enough, but return an object can be more general-purpose
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
