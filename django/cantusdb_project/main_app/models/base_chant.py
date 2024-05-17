from main_app.models import BaseModel
from django.db import models
from django.contrib.auth import get_user_model
from django.contrib.postgres.search import SearchVectorField


class BaseChant(BaseModel):
    """
    the Chant and Sequence models inherit from BaseChant.

    Both Chant and Sequence must have the same fields, otherwise errors will be raised
    when a user searches for chants/sequences in the database. Thus, all fields,
    properties and attributes should be declared in BaseChant in order to keep the two
    models harmonized, even if only one of the two models uses a particular field.
    """

    class Meta:
        abstract = True

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
    # The "s_sequence" char field, used for Sequences, is used to indicate the relative positions of sequences on the page.
    # It sometimes features non-numeric characters and leading zeroes, so it's a CharField.
    s_sequence = models.CharField("Sequence", blank=True, null=True, max_length=255)
    # The "c_sequence" integer field, used for Chants, similarly indicates the relative positions of chants on the page
    c_sequence = models.PositiveIntegerField(
        "Sequence", help_text='Each folio starts with "1"', null=True, blank=True
    )
    genre = models.ForeignKey("Genre", blank=True, null=True, on_delete=models.PROTECT)
    rubrics = models.CharField(blank=True, null=True, max_length=255)
    analecta_hymnica = models.CharField(blank=True, null=True, max_length=255)
    indexing_notes = models.TextField(blank=True, null=True)
    date = models.CharField(blank=True, null=True, max_length=255)
    col1 = models.CharField(blank=True, null=True, max_length=255)
    col2 = models.CharField(blank=True, null=True, max_length=255)
    col3 = models.CharField(blank=True, null=True, max_length=255)
    ah_volume = models.CharField(
        blank=True, null=True, max_length=255, verbose_name="AH volume"
    )
    source = models.ForeignKey(
        "Source", on_delete=models.CASCADE
    )  # PROTECT so that we can't delete a source with chants in it
    cantus_id = models.CharField(
        blank=True, null=True, max_length=255, db_index=True, verbose_name="cantus ID"
    )
    image_link = models.URLField(blank=True, null=True)
    json_info = models.JSONField(null=True, blank=True)
    marginalia = models.CharField(max_length=63, null=True, blank=True)
    office = models.ForeignKey(
        "Office", on_delete=models.PROTECT, null=True, blank=True
    )
    position = models.CharField(max_length=63, null=True, blank=True)
    feast = models.ForeignKey("Feast", on_delete=models.PROTECT, null=True, blank=True)
    mode = models.CharField(max_length=63, null=True, blank=True)
    differentia = models.CharField(blank=True, null=True, max_length=63)
    differentiae_database = models.CharField(
        blank=True,
        null=True,
        max_length=12,
        verbose_name="differentiae database",
    )
    diff_db = models.ForeignKey(
        "Differentia",
        blank=True,
        null=True,
        on_delete=models.deletion.PROTECT,
        verbose_name="differentiae database",
    )
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

    # NB: the cao_concordances field should not be used in public-facing views, as it contains data that may be out-of-date.
    # For more information, see https://github.com/DDMAL/CantusDB/wiki/BaseChant-Model
    cao_concordances = models.CharField(
        blank=True, null=True, max_length=63, verbose_name="CAO concordances"
    )  # !! see lines immediately above
    proofread_by = models.ManyToManyField(get_user_model(), blank=True)
    melody_id = models.CharField(
        blank=True, null=True, max_length=63, verbose_name="melody ID"
    )
    search_vector = SearchVectorField(null=True, editable=False)
    content_structure = models.CharField(
        blank=True,
        null=True,
        max_length=64,
        help_text="Additional folio number field, if folio numbers appear on the leaves but are not in the 'binding order'.",
    )
    next_chant = models.OneToOneField(
        "self",
        related_name="prev_chant",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    # prev_chant = ...  # prev_chant is created when next_chant is calculated

    # this field, populated by the populate_is_last_chant_in_feast script, exists in order to optimize .get_suggested_feasts() on the chant-create page
    is_last_chant_in_feast = models.BooleanField(blank=True, null=True)

    segment = models.ForeignKey(
        "Segment",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        help_text="The segment of the manuscript that contains this chant",
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
        return f"https://cantusindex.org/id/{self.cantus_id}"

    def __str__(self):
        incipit = ""
        if self.incipit:
            incipit = self.incipit
        elif self.manuscript_full_text:
            split_text = self.manuscript_full_text.split()
            incipit = " ".join(split_text[:4])
        return '"{incip}" ({id})'.format(incip=incipit, id=self.id)
