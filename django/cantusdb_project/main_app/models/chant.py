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
    # fragmentarium_id = models.CharField(blank=True, null=True, max_length=64)
    # # Digital Analysis of Chant Transmission
    # dact = models.CharField(blank=True, null=True, max_length=64)
    # also a second differentia field
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
            # For the ra, rb, va, vb - don't do anything about those. That formatting will not stay.
            if folio is None:
                # this shouldn't happen, but during testing, we may have some chants without folio
                next_folio = None
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
            print(["chants_next_folio: [{} - {}]".format(chant.folio, chant.sequence_number) for chant in chants_next_folio])
            try:
                next_chant = chants_next_folio[0]
            except AttributeError: # i.e. next folio is None
                return None
            except ValueError: # i.e. next folio contains no chants
                next_chant = None

        return next_chant

    def get_previous_chant(self):
        """return the previous chant in the same source.

        For use in the suggested_feasts function, to populate a list of possible next feasts.
        Since this use case does not require very much accuracy, this function sometimes returns
        erroneous values: if the chant is on a folio with an unusual name, the function
        will return None. If it's the first chant on the folio and the previous folio has
        an unusual name (e.g. a folio was inserted into the manuscript), the function may
        return the wrong chant.

        Returns:
            Chant/None: the previous chant object, or None
        """

        def get_previous_folio(folio):
            """For when the previous chant is on the previous folio
            Args:
                folio (str): the number of a folio
            Returns:
                str/None: the folio number of the previous folio, or None
            """
            if folio is None:
                return None
            if not folio[0].isnumeric():
                # a001 etc.
                previous_folio = None
            elif folio == "001r" or folio == "001":
                # i.e. first page in manuscript, no preceding folio
                previous_folio = None
            elif folio.isdecimal():
                # 002 -> 001
                previous_folio = str(int(folio) - 1).zfill(len(folio))
            elif folio.endswith("v"):
                # 001v -> 001r
                previous_folio = folio[:-1] + "r"
            elif folio.endswith("r"):
                # 002r -> 001v
                previous_folio = str(int(folio[:-1]) - 1).zfill(len(folio) - 1) + "v"
            else:
                # in case of nonstandard folio number
                previous_folio = None
        
            return previous_folio

        sequence_number = self.sequence_number
        try:
            previous_chant = Chant.objects.get(
                source=self.source,
                folio=self.folio,
                sequence_number=sequence_number - 1,
            )
        except Chant.DoesNotExist: # it's the first chant on the folio - we need to look at the previous folio
            try:
                # since QuerySets don't support negative indexing, convert to list to allow for negative indexing in next try block
                chants_previous_folio = list(Chant.objects.filter(
                    source=self.source, folio=get_previous_folio(self.folio)
                ).order_by("sequence_number"))
            except AttributeError: # previous_folio is None
                return None

            try: # get the last chant on the previous folio
                previous_chant = chants_previous_folio[-1]
            except ValueError: # previous folio contains no chants
                previous_chant = None
        
        return previous_chant
