from django.contrib.postgres.search import SearchVectorField
from django.db import models
from django.db.models.query import QuerySet
from main_app.models import BaseModel
from users.models import User


class Chant(BaseModel):
    """The model for chants

    The fields defined here include both chant fields and some "dummy fields" used to harmonize 
    the `Chant` model and `Sequence` model. There are situations where a queryset of chants and a queryset
    of sequences need to be combined. The two models must have the same fields for that to work. 

    The fields must be the defined in the same order between the `Sequence` and `Chant` model. 
    That's why the "dummy fields" are not grouped together
    """

    # The "visible_status" field corresponds to the "status" field on old Cantus
    visible_status = models.CharField(max_length=1, blank=True, null=True)
    # For chants, the old Cantus "title" field (in json export) is used to populate the new Cantus "incipit" field,
    # For sequences, the old Cantus "title" field is used to populate the new Cantus "title" field,
    # and the old Cantus "incipit" field is used to populate the new Cantus "incipit" field.
    title = models.CharField(blank=True, null=True, max_length=255)
    incipit = models.CharField(blank=True, null=True, max_length=255)
    siglum = models.CharField(blank=True, null=True, max_length=255)
    folio = models.CharField(
        help_text="Binding order", blank=True, null=True, max_length=255, db_index=True
    )
    # The "sequence" char field is for sequence numbers like "01", used for sequences
    # The "sequence_number" integer field below is for sequence numbers like "1", used for chants
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
    # Note that some chants do not have a source
    source = models.ForeignKey(
        "Source", on_delete=models.PROTECT, null=True, blank=True
    )  # PROTECT so that we can't delete a source with chants in it
    cantus_id = models.CharField(blank=True, null=True, max_length=255, db_index=True)
    image_link = models.URLField(blank=True, null=True)
    json_info = models.JSONField(null=True, blank=True)
    marginalia = models.CharField(max_length=63, null=True, blank=True)
    sequence_number = models.PositiveIntegerField(
        help_text='Each folio starts with "1"', null=True, blank=True
    )
    office = models.ForeignKey(
        "Office", on_delete=models.PROTECT, null=True, blank=True
    )
    position = models.CharField(max_length=63, null=True, blank=True)
    feast = models.ForeignKey("Feast", on_delete=models.PROTECT, null=True, blank=True)
    mode = models.CharField(max_length=63, null=True, blank=True)
    differentia = models.CharField(blank=True, null=True, max_length=63)
    differentia_id = models.CharField(blank=True, null=True, max_length=12)
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
    manuscript_full_text_std_proofread = models.BooleanField(blank=True, null=True)
    manuscript_full_text = models.TextField(
        help_text="Enter the wording, word order and spellings as found in the manuscript"
        ", with abbreviations resolved to standard words. Use upper-case letters as found"
        " in the source. Retain “Xpistum” (Christum), “Ihc” (Jesus) and other instances of "
        "Greek characters with their closest approximations of Latin letters. Some punctuation"
        " signs and vertical dividing lines | are employed in this field. Repetenda and psalm "
        "cues can also be recorded here.",
        null=True,
        blank=True,
    )
    manuscript_full_text_proofread = models.BooleanField(blank=True, null=True)
    manuscript_syllabized_full_text = models.TextField(null=True, blank=True)
    volpiano = models.TextField(null=True, blank=True)
    volpiano_proofread = models.BooleanField(blank=True, null=True)
    # The "volpiano_notes" and "volpiano_intervals" field are added in new Cantus to aid melody search.
    # "volpiano_notes" is extracted from the "volpiano" field, by eliminating all non-note characters
    # and removing consecutive repeated notes.
    # "volpiano_intervals" is extracted from the "volpiano_notes" field.
    # It records the intervals between any two adjacent volpiano notes.
    volpiano_notes = models.TextField(null=True, blank=True)
    volpiano_intervals = models.TextField(null=True, blank=True)
    cao_concordances = models.CharField(blank=True, null=True, max_length=63)
    proofread_by = models.ForeignKey(
        User, on_delete=models.PROTECT, null=True, blank=True
    )
    melody_id = models.CharField(blank=True, null=True, max_length=63)
    search_vector = SearchVectorField(null=True, editable=False)
    content_structure = models.CharField(
        blank=True,
        null=True,
        max_length=64,
        help_text="Additional folio number field, if folio numbers appear on the leaves but are not in the 'binding order'.",
    )
    next_chant = models.OneToOneField("self", related_name="prev_chant", null=True, blank=True, on_delete=models.SET_NULL)
    # prev_chant = ...  # prev_chant is created when next_chant is calculated 

    is_last_chant_in_feast = models.BooleanField(blank=True, null=True)

    # fragmentarium_id = models.CharField(blank=True, null=True, max_length=64)
    # # Digital Analysis of Chant Transmission
    # dact = models.CharField(blank=True, null=True, max_length=64)
    # also a second differentia field

    def __str__(self):
        incipit = ""
        if self.incipit:
            incipit = self.incipit
        elif self.manuscript_full_text:
            split_text = self.manuscript_full_text.split()
            incipit = " ".join(split_text[:4])
        return '"{incip}" ({id})'.format(incip = incipit, id = self.id)


    def get_ci_url(self) -> str:
        """Construct the url to the entry in Cantus Index correponding to the chant.

        Returns:
            str: The url to the Cantus Index page
        """
        return f"http://cantusindex.org/id/{self.cantus_id}"

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
            # For chants that end with ra, rb, va, vb - don't do anything about those. That formatting will not stay.
            
            if folio is None:
                # this shouldn't happen, but during testing, we may have some chants without folio
                next_folio = None
                return next_folio

            # some folios begin with an "a" - these should be treated like other folios, but preserving the leading "a"
            if folio[0] == "a":
                prefix, folio = folio[:1], folio[1:]
            else:
                prefix = ""

            stem, suffix = folio[:3], folio[3:]
            if stem.isdecimal():
                stem_int = int(stem)
            else:
                next_folio = None
                return next_folio

            if suffix == "r":
                # 001r -> 001v
                next_folio = prefix + stem + "v"
            elif suffix == "v":
                next_stem = str(stem_int + 1).zfill(3)
                next_folio = prefix + next_stem + "r"
            elif suffix == "":
                # 001 -> 002
                next_folio = prefix + str(stem_int + 1).zfill(3)

            # special cases: inserted pages
            elif suffix == "w":
                # 001w -> 001x
                next_folio = prefix + stem + "x"
            elif suffix == "y":
                # 001y -> 001z
                next_folio = prefix + stem + "z"
            elif suffix == "a":
                # 001a -> 001b
                next_folio = prefix + stem + "b"
            else:
                # unusual/uncommon suffix
                next_folio = None
            return next_folio

        try:
            next_chant = Chant.objects.get(
                source=self.source,
                folio=self.folio,
                sequence_number=self.sequence_number + 1,
            )
        except Chant.DoesNotExist: # i.e. it's the last chant on the folio
            chants_next_folio = Chant.objects.filter(
                source=self.source, folio=get_next_folio(self.folio)
            ).order_by("sequence_number")
            try:
                next_chant = chants_next_folio[0]
            except AttributeError: # i.e. next folio is None
                return None
            except Chant.DoesNotExist: # i.e. next folio contains no chants (I think?)
                return None
            except IndexError: # i.e. next folio contains no chants (I think?)
                return None
            except ValueError: # i.e. next folio contains no chants
                next_chant = None
        except Chant.MultipleObjectsReturned: # i.e. multiple chants have the same source, folio and sequence_number
                                              # for example, the two chants on folio h001r sequence_number 1, in source with ID 123753 
            next_chant = None
        except TypeError: # sequence_number is None
            next_chant = None


        return next_chant

