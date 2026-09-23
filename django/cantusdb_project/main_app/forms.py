from typing import Optional, Any, Dict

from django import forms
from django.conf import settings
from django.contrib.auth.forms import ReadOnlyPasswordHashField
from django.contrib.auth import get_user_model
from django.db.models import Q, Model
from django.contrib.admin.widgets import (
    FilteredSelectMultiple,
)
from django.core.exceptions import ValidationError
from django.forms.widgets import CheckboxSelectMultiple, HiddenInput
from dal import autocomplete  # type: ignore[import-untyped]
from volpiano_display_utilities.cantus_text_syllabification import syllabify_text
from volpiano_display_utilities.latin_word_syllabification import LatinError
from .models import (
    Chant,
    Service,
    Genre,
    Institution,
    Notation,
    Feast,
    Source,
    Segment,
    Project,
    Provenance,
    Century,
    Sequence,
)
from .models.url_field import NormalizedURLFormField
from .widgets import (
    TextInputWidget,
    VolpianoInputWidget,
    TextAreaWidget,
    VolpianoAreaWidget,
    SelectWidget,
    CheckboxWidget,
    MarkdownWidget,
)

# ModelForm allows to build a form directly from a model
# see https://docs.djangoproject.com/en/3.0/topics/forms/modelforms/

# Define choices for the Source model's
# complete_inventory BooleanField
COMPLETE_INVENTORY_FORM_CHOICES = (
    (True, "Full inventory"),
    (False, "Partial inventory"),
)

# Define choices for Chant model's
# various proofreading fields: manuscript_full_text_std_proofread,
# manuscript_full_text_proofread, volpiano_proofread, other_fields_proofread
PROOFREAD_CHOICES = [
    (None, "Any"),
    (True, "Yes"),
    (False, "No"),
]


class NameModelChoiceField(forms.ModelChoiceField):
    """
    A custom ModelChoiceField that overrides the label_from_instance method
    to display the object's name attribute instead of str(object).
    This field is specifically designed for handling genre and service objects.
    Rather than displaying the name along with its description, sometimes we
    only want the shorthand notation for the genre and service objects.
    (Eg. [AV] Antiphon verse --> AV)
    """

    def label_from_instance(self, obj):
        return obj.name


class SelectWidgetNameModelChoiceField(NameModelChoiceField):
    """
    This class inherits from NameModelChoiceField, but uses the
    the custom SelectWidget defined in widgets.py as its widget
    (for styling).
    """

    widget = SelectWidget()


class CheckboxNameModelMultipleChoiceField(forms.ModelMultipleChoiceField):
    """
    A custom ModelMultipleChoiceField that overrides the label_from_instance method
    to display the object's name attribute instead of str(object) and uses
    the CheckboxMulitpleSelect widget.
    """

    def label_from_instance(self, obj):
        return obj.name

    widget = CheckboxSelectMultiple()


class CantusDBLatinField(forms.CharField):
    """
    A custom CharField for chant text fields. Validates that the text
    can be syllabified (essentially, that it does not have any improper
    characters).
    """

    def validate(self, value):
        super().validate(value)
        # Temporarily turn off validation; see #1674
        # if value:
        #     try:
        #         syllabify_text(value)
        #     except LatinError as err:
        #         raise forms.ValidationError(str(err))
        #     except ValueError as exc:
        #         raise forms.ValidationError("Invalid characters in text.") from exc


class CantusDBSyllabifiedLatinField(forms.CharField):
    """
    A custom CharField for chant syllabified text fields. Validates that the text
    can be syllabified (essentially, that it does not have any improper
    characters).
    """

    def validate(self, value):
        super().validate(value)
        # Temporarily turn off validation; see #1674
        # if value:
        #     try:
        #         syllabify_text(value, text_presyllabified=True)
        #     except ValueError as exc:
        #         raise forms.ValidationError("Invalid characters in text.") from exc


class StyledChoiceField(forms.ChoiceField):
    """
    A custom ChoiceField that uses the custom SelectWidget defined in widgets.py
    as its widget (for styling).
    """

    widget = SelectWidget()


class FormsetOptimizedModelChoiceIterator(forms.models.ModelChoiceIterator):
    """
    An iterator for the FormsetOptimizedModelChoiceField that does not
    evaluate the queryset for each form in the formset. Instead of iterating
    through the field's queryset, we iterate through the field's choices.
    """

    def __init__(self, field):
        self.field = field
        self.choices = field.choices
        self.queryset = field.queryset

    def __iter__(self):
        if self.field.empty_label is not None:
            yield ("", self.field.empty_label)
        queryset = self.queryset
        if queryset is None:
            queryset = self.field.queryset
        for obj in queryset:
            yield self.choice(obj)


class FormsetOptimizedModelChoiceField(forms.ModelChoiceField):
    """
    A ModelChoiceField that is optimized for a ModelFormset.
    In the defaul ModelChoiceField, a queryset is evaluated for
    each form in the formset, leading to a large number of queries
    when summed over multiple formsets.
    """

    def __init__(self, queryset, choices, *args, **kwargs):
        super().__init__(queryset, *args, **kwargs)
        self.choices = choices


class ChantCreateForm(forms.ModelForm):
    class Meta:
        model = Chant
        # specify either 'fields' or 'excludes' so that django knows which fields to use
        fields = [
            "marginalia",
            "folio",
            "c_sequence",
            "service",
            "genre",
            "position",
            "cantus_id",
            "feast",
            "mode",
            "differentia",
            "diff_db",
            "finalis",
            "extra",
            "chant_range",
            "manuscript_full_text_std_spelling",
            "manuscript_full_text",
            "volpiano",
            "image_link",
            "melody_id",
            "content_structure",
            "indexing_notes",
            "addendum",
            "project",
            "liturgical_function",
            "polyphony",
            "cm_melody_id",
            "incipit_of_refrain",
            "later_addition",
            "rubrics",
            "source",
            "text_language",
        ]
        # the widgets dictionary is ignored for a model field with a non-empty
        # choices attribute. In this case, you must override the form field to
        # use a different widget. this goes for all foreignkey and required fields
        # here, which are written explicitly below to override form field
        widgets = {
            "marginalia": TextInputWidget(),
            # folio: defined below (required)
            # c_sequence: defined below (required)
            "service": autocomplete.ModelSelect2(url="service-autocomplete"),
            "genre": autocomplete.ModelSelect2(url="genre-autocomplete"),
            "position": TextInputWidget(),
            "cantus_id": TextInputWidget(),
            "feast": autocomplete.ModelSelect2(url="feast-autocomplete"),
            "mode": TextInputWidget(),
            "differentia": TextInputWidget(),
            "diff_db": autocomplete.ModelSelect2(url="differentia-autocomplete"),
            "finalis": TextInputWidget(),
            "extra": TextInputWidget(),
            "chant_range": VolpianoInputWidget(),
            # manuscript_full_text_std_spelling: defined below (required & special field)
            # "manuscript_full_text": defined below (special field)
            "volpiano": VolpianoAreaWidget(),
            "image_link": TextInputWidget(),
            "melody_id": TextInputWidget(),
            "content_structure": TextInputWidget(),
            "indexing_notes": TextAreaWidget(),
            "addendum": TextInputWidget(),
            "polyphony": SelectWidget(),
            "liturgical_function": SelectWidget(),
            "cm_melody_id": TextInputWidget(),
            "incipit_of_refrain": TextInputWidget(),
            "later_addition": TextInputWidget(),
            "rubrics": TextInputWidget(),
            "text_language": SelectWidget(),
        }

    folio = forms.CharField(
        required=True,
        widget=TextInputWidget,
        help_text="Binding order",
    )

    c_sequence = forms.IntegerField(
        required=True,
        widget=TextInputWidget,
        help_text="Each folio starts with '1'.",
    )

    manuscript_full_text_std_spelling = CantusDBLatinField(
        widget=TextAreaWidget,
        help_text=Chant._meta.get_field("manuscript_full_text_std_spelling").help_text,
        label="Full text as in Source (standardized spelling)",
        required=True,
    )

    manuscript_full_text = CantusDBLatinField(
        widget=TextAreaWidget,
        label="Full text as in Source (source spelling)",
        help_text=Chant._meta.get_field("manuscript_full_text").help_text,
        required=False,
    )

    project = SelectWidgetNameModelChoiceField(
        queryset=Project.objects.all().order_by("id"),
        initial=None,
        required=False,
        help_text="Select the project (if any) that the chant belongs to.",
    )

    def clean(self) -> dict[str, Any]:
        """
        Provide custom clean method that ensures the created chant does
        not duplicate the folio and c_sequence of an already-existing chant.
        """
        # Call super().clean() to ensure that the form's built-in validation
        # is run before our custom validation.
        super().clean()
        folio = self.cleaned_data["folio"]
        c_sequence = self.cleaned_data["c_sequence"]
        source = self.cleaned_data["source"]
        if source.chant_set.filter(folio=folio, c_sequence=c_sequence):
            raise forms.ValidationError(
                "Chant with the same sequence and folio already exists in this source.",
                code="duplicate-folio-sequence",
            )
        return self.cleaned_data


class SourceCreateForm(forms.ModelForm):
    class Meta:
        model = Source
        fields = [
            # "title",
            # "siglum",
            "holding_institution",
            "shelfmark",
            "name",
            "segment_m2m",
            "provenance",
            "provenance_notes",
            "full_source",
            "date",
            "century",
            "cursus",
            "current_editors",
            "melodies_entered_by",
            "inventoried_by",
            "full_text_entered_by",
            "description_entered_by",
            "proofreaders",
            "other_editors",
            "source_data_contributed_by",
            "complete_inventory",
            "summary",
            "liturgical_occasions",
            "description",
            "selected_bibliography",
            "image_link",
            "fragmentarium_id",
            "dact_id",
            "indexing_notes",
            "production_method",
            "source_completeness",
        ]
        widgets = {
            # "title": TextInputWidget(),
            # "siglum": TextInputWidget(),
            "holding_institution": autocomplete.ModelSelect2(
                url="holding-autocomplete"
            ),
            "shelfmark": TextInputWidget(),
            "provenance": autocomplete.ModelSelect2(url="provenance-autocomplete"),
            "name": TextInputWidget(),
            "provenance_notes": TextInputWidget(),
            "date": TextInputWidget(),
            "cursus": SelectWidget(),
            "summary": TextAreaWidget(),
            "liturgical_occasions": TextAreaWidget(),
            "description": MarkdownWidget(),
            "selected_bibliography": MarkdownWidget(),
            "image_link": TextInputWidget(),
            "fragmentarium_id": TextInputWidget(),
            "dact_id": TextInputWidget(),
            "indexing_notes": TextAreaWidget(),
            "current_editors": autocomplete.ModelSelect2Multiple(
                url="active-users-autocomplete"
            ),
            "melodies_entered_by": autocomplete.ModelSelect2Multiple(
                url="all-users-autocomplete"
            ),
            "century": autocomplete.ModelSelect2Multiple(url="century-autocomplete"),
            "inventoried_by": autocomplete.ModelSelect2Multiple(
                url="all-users-autocomplete"
            ),
            "full_text_entered_by": autocomplete.ModelSelect2Multiple(
                url="all-users-autocomplete"
            ),
            "description_entered_by": autocomplete.ModelSelect2Multiple(
                url="all-users-autocomplete"
            ),
            "proofreaders": autocomplete.ModelSelect2Multiple(
                url="all-users-autocomplete"
            ),
            "other_editors": autocomplete.ModelSelect2Multiple(
                url="all-users-autocomplete"
            ),
            "source_data_contributed_by": autocomplete.ModelSelect2Multiple(
                url="all-users-autocomplete"
            ),
            "production_method": SelectWidget(),
            "source_completeness": SelectWidget(),
        }
        field_classes = {
            "segment_m2m": CheckboxNameModelMultipleChoiceField,
        }

    complete_inventory = StyledChoiceField(
        choices=COMPLETE_INVENTORY_FORM_CHOICES, required=False
    )

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        # "Benedicamus Domino" is a chant-level project designation, not a
        # source segment, so it's excluded here (see #2131).
        self.fields["segment_m2m"].queryset = Segment.objects.exclude(
            id=settings.BENEDICAMUS_DOMINO_SEGMENT_ID
        )


class ChantEditForm(forms.ModelForm):
    class Meta:
        model = Chant
        fields = [
            "manuscript_full_text_std_spelling",
            "manuscript_full_text",
            "volpiano",
            "marginalia",
            "folio",
            "c_sequence",
            "feast",
            "service",
            "genre",
            "position",
            "cantus_id",
            "melody_id",
            "mode",
            "finalis",
            "differentia",
            "diff_db",
            "extra",
            "image_link",
            "indexing_notes",
            "addendum",
            "chant_range",
            "other_fields_proofread",
            "manuscript_full_text_std_proofread",
            "manuscript_full_text_proofread",
            "volpiano_proofread",
            "proofread_by",
            "project",
            "liturgical_function",
            "polyphony",
            "cm_melody_id",
            "incipit_of_refrain",
            "later_addition",
            "rubrics",
            "source",
            "text_language",
        ]
        widgets = {
            # manuscript_full_text_std_spelling: defined below (required) & special field
            # manuscript_full_text: defined below (special field)
            "volpiano": VolpianoAreaWidget(),
            "marginalia": TextInputWidget(),
            # folio: defined below (required)
            # c_sequence: defined below (required)
            "feast": autocomplete.ModelSelect2(url="feast-autocomplete"),
            "service": autocomplete.ModelSelect2(url="service-autocomplete"),
            "genre": autocomplete.ModelSelect2(url="genre-autocomplete"),
            "position": TextInputWidget(),
            "cantus_id": TextInputWidget(),
            "melody_id": TextInputWidget(),
            "mode": TextInputWidget(),
            "finalis": TextInputWidget(),
            "differentia": TextInputWidget(),
            "diff_db": autocomplete.ModelSelect2(url="differentia-autocomplete"),
            "extra": TextInputWidget(),
            "image_link": TextInputWidget(),
            "indexing_notes": TextAreaWidget(),
            "addendum": TextInputWidget(),
            "chant_range": VolpianoAreaWidget(),
            "other_fields_proofread": CheckboxWidget(),
            "manuscript_full_text_std_proofread": CheckboxWidget(),
            "manuscript_full_text_proofread": CheckboxWidget(),
            "volpiano_proofread": CheckboxWidget(),
            "proofread_by": autocomplete.ModelSelect2Multiple(
                url="proofread-by-autocomplete"
            ),
            "polyphony": SelectWidget(),
            "liturgical_function": SelectWidget(),
            "cm_melody_id": TextInputWidget(),
            "incipit_of_refrain": TextInputWidget(),
            "later_addition": TextInputWidget(),
            "rubrics": TextInputWidget(),
            "text_language": SelectWidget(),
        }

    manuscript_full_text_std_spelling = CantusDBLatinField(
        widget=TextAreaWidget,
        help_text=Chant._meta.get_field("manuscript_full_text_std_spelling").help_text,
        label="Full text as in Source (standardized spelling)",
        required=False,
    )

    manuscript_full_text = CantusDBLatinField(
        widget=TextAreaWidget,
        label="Full text as in Source (source spelling)",
        help_text=Chant._meta.get_field("manuscript_full_text").help_text,
        required=False,
    )

    folio = forms.CharField(
        required=True,
        widget=TextInputWidget,
        help_text="Binding order",
    )

    c_sequence = forms.IntegerField(
        required=True,
        widget=TextInputWidget,
        help_text="Each folio starts with '1'.",
    )

    project = SelectWidgetNameModelChoiceField(
        queryset=Project.objects.all().order_by("id"),
        help_text="Select the project (if any) that the chant belongs to.",
        required=False,
    )

    def clean_manuscript_full_text_std_spelling(self) -> Optional[str]:
        """
        Provide a custom validation function for the
        manuscript_full_text_std_spelling field to ensure that
        if it initially contained text, it cannot be made blank.
        """
        if (
            self["manuscript_full_text_std_spelling"].initial
            and not self["manuscript_full_text_std_spelling"].data
        ):
            raise forms.ValidationError(
                "This field cannot be blank for this chant.",
                code="txt-req-prev-existing",
            )
        entered_text: str = self["manuscript_full_text_std_spelling"].data
        return entered_text

    def clean(self) -> dict[str, Any]:
        """
        Custom validation to ensure that the edited chant does not duplicate
        the folio and c_sequence of an already-existing chant.
        """
        # Call super().clean() to ensure that the form's built-in validation
        # is run before our custom validation.
        super().clean()
        folio = self.cleaned_data["folio"]
        c_sequence = self.cleaned_data["c_sequence"]
        source = self.cleaned_data["source"]
        if (
            source.chant_set.exclude(id=self.instance.id)
            .filter(folio=folio, c_sequence=c_sequence)
            .exists()
        ):
            raise forms.ValidationError(
                "A chant with this folio and sequence already exists.",
                code="duplicate-folio-sequence",
            )
        return self.cleaned_data


class SourceEditForm(forms.ModelForm):
    class Meta:
        model = Source
        fields = [
            # "title",
            # "siglum",
            "holding_institution",
            "shelfmark",
            "name",
            "segment_m2m",
            "provenance",
            "provenance_notes",
            "full_source",
            "date",
            "century",
            "cursus",
            "complete_inventory",
            "summary",
            "liturgical_occasions",
            "description",
            "selected_bibliography",
            "image_link",
            "fragmentarium_id",
            "dact_id",
            "indexing_notes",
            "melodies_entered_by",
            "inventoried_by",
            "full_text_entered_by",
            "description_entered_by",
            "proofreaders",
            "other_editors",
            "source_data_contributed_by",
            "production_method",
            "source_completeness",
        ]
        widgets = {
            "holding_institution": autocomplete.ModelSelect2(
                url="holding-autocomplete"
            ),
            "shelfmark": TextInputWidget(),
            "segment_m2m": CheckboxSelectMultiple(),
            "name": TextInputWidget(),
            "provenance": autocomplete.ModelSelect2(url="provenance-autocomplete"),
            "provenance_notes": TextInputWidget(),
            "date": TextInputWidget(),
            "cursus": SelectWidget(),
            "summary": TextAreaWidget(),
            "liturgical_occasions": TextAreaWidget(),
            "description": MarkdownWidget(),
            "selected_bibliography": MarkdownWidget(),
            "image_link": TextInputWidget(),
            "fragmentarium_id": TextInputWidget(),
            "dact_id": TextInputWidget(),
            "indexing_notes": TextAreaWidget(),
            "melodies_entered_by": autocomplete.ModelSelect2Multiple(
                url="all-users-autocomplete"
            ),
            "century": autocomplete.ModelSelect2Multiple(url="century-autocomplete"),
            "inventoried_by": autocomplete.ModelSelect2Multiple(
                url="all-users-autocomplete"
            ),
            "full_text_entered_by": autocomplete.ModelSelect2Multiple(
                url="all-users-autocomplete"
            ),
            "description_entered_by": autocomplete.ModelSelect2Multiple(
                url="all-users-autocomplete"
            ),
            "proofreaders": autocomplete.ModelSelect2Multiple(
                url="all-users-autocomplete"
            ),
            "other_editors": autocomplete.ModelSelect2Multiple(
                url="all-users-autocomplete"
            ),
            "source_data_contributed_by": autocomplete.ModelSelect2Multiple(
                url="all-users-autocomplete"
            ),
            "production_method": SelectWidget(),
            "source_completeness": SelectWidget(),
        }
        field_classes = {
            "segment_m2m": CheckboxNameModelMultipleChoiceField,
        }

    complete_inventory = StyledChoiceField(
        choices=COMPLETE_INVENTORY_FORM_CHOICES, required=False
    )

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        # "Benedicamus Domino" is a chant-level project designation, not a
        # source segment, so it's excluded here (see #2131).
        self.fields["segment_m2m"].queryset = Segment.objects.exclude(
            id=settings.BENEDICAMUS_DOMINO_SEGMENT_ID
        )


class ChantSearchForm(forms.Form):
    feast = forms.ModelChoiceField(
        queryset=Feast.objects.all(),
        required=False,
        widget=autocomplete.ModelSelect2(url="feast-autocomplete"),
    )


class SourceBrowseChantsProofreadForm(forms.Form):
    manuscript_full_text_std_proofread = forms.ChoiceField(
        label="Full text as in Source (standardized spelling) proofread",
        choices=PROOFREAD_CHOICES,
        widget=forms.RadioSelect,
        required=False,
    )
    manuscript_full_text_proofread = forms.ChoiceField(
        label="Full text as in Source (source spelling) proofread",
        choices=PROOFREAD_CHOICES,
        widget=forms.RadioSelect,
        required=False,
    )

    volpiano_proofread = forms.ChoiceField(
        label="Volpiano proofread",
        choices=PROOFREAD_CHOICES,
        widget=forms.RadioSelect,
        required=False,
    )

    other_fields_proofread = forms.ChoiceField(
        label="Other fields proofread",
        choices=PROOFREAD_CHOICES,
        widget=forms.RadioSelect,
        required=False,
    )


class SequenceEditForm(forms.ModelForm):
    class Meta:
        model = Sequence
        fields = [
            "title",
            # "siglum",
            "incipit",
            "folio",
            "s_sequence",
            "genre",
            "rubrics",
            "analecta_hymnica",
            "indexing_notes",
            "date",
            "col1",
            "col2",
            "col3",
            "ah_volume",
            "source",
            "cantus_id",
            "image_link",
        ]
        widgets = {
            "title": TextInputWidget(),
            # "siglum": TextInputWidget(),
            "incipit": TextInputWidget(),
            "folio": TextInputWidget(),
            "s_sequence": TextInputWidget(),
            "rubrics": TextInputWidget(),
            "analecta_hymnica": TextInputWidget(),
            "indexing_notes": TextAreaWidget(),
            "date": TextInputWidget(),
            "col1": TextInputWidget(),
            "col2": TextInputWidget(),
            "col3": TextInputWidget(),
            "ah_volume": TextInputWidget(),
            "cantus_id": TextInputWidget(),
            "image_link": TextInputWidget(),
        }

    # We use NameModelChoiceField here so the dropdown list of genres displays the name
    # instead of [name] + description
    genre = NameModelChoiceField(
        queryset=Genre.objects.all().order_by("name"), required=False
    )
    genre.widget.attrs.update({"class": "form-control custom-select custom-select-sm"})

    # select_related avoids an N+1 query: rendering each option calls
    # Source.__str__, which reads source.holding_institution (see #2039).
    source = forms.ModelChoiceField(
        queryset=Source.objects.select_related("holding_institution").order_by("title"),
        required=False,
    )
    source.widget.attrs.update({"class": "form-control custom-select custom-select-sm"})


class ChantEditSyllabificationForm(forms.ModelForm):
    class Meta:
        model = Chant
        fields = [
            "manuscript_full_text",
            "manuscript_syllabized_full_text",
        ]

    manuscript_full_text = CantusDBLatinField(
        widget=TextAreaWidget, label="Full text as in Source (source spelling)"
    )

    manuscript_syllabized_full_text = CantusDBSyllabifiedLatinField(
        widget=TextAreaWidget, label="Syllabized full text"
    )


class AdminCenturyForm(forms.ModelForm):
    class Meta:
        model = Century
        fields = "__all__"

    name = forms.CharField(required=True, widget=TextInputWidget)


class AdminChantForm(forms.ModelForm):
    class Meta:
        model = Chant
        fields = "__all__"
        widgets = {
            "volpiano": VolpianoAreaWidget(),
            "indexing_notes": TextAreaWidget(),
            "manuscript_full_text_std_proofread": CheckboxWidget(),
            "manuscript_full_text_proofread": CheckboxWidget(),
            "volpiano_proofread": CheckboxWidget(),
            "other_fields_proofread": CheckboxWidget(),
            "chant_range": VolpianoAreaWidget(),
        }

    manuscript_full_text_std_spelling = forms.CharField(
        required=True,
        widget=TextAreaWidget,
        help_text="Manuscript full text with standardized spelling. Enter the words "
        "according to the manuscript but normalize their spellings following "
        "Classical Latin forms. Use upper-case letters for proper nouns, "
        'the first word of each chant, and the first word after "Alleluia" for '
        "Mass Alleluias. Punctuation is omitted.",
    )
    # Django's default text area widget selection for form inputs is non-intuitive
    # and manual updates to fields (e.g., changing required=True) affect widget properties unexpectedly;
    # this workaround is our current best solution.
    manuscript_full_text_std_spelling.widget.attrs.update(
        {"style": "width: 610px; height: 170px;"}
    )

    folio = forms.CharField(
        required=True,
        widget=TextInputWidget,
        help_text="Binding order",
    )

    c_sequence = forms.CharField(
        required=True,
        widget=TextInputWidget,
        help_text="Each folio starts with '1'.",
        label="Sequence",
    )

    # We use NameModelChoiceField here so the dropdown list of service/mass displays the name
    # instead of [name] + description
    service = NameModelChoiceField(
        queryset=Service.objects.all().order_by("name"),
        required=False,
    )
    # We use NameModelChoiceField here so the dropdown list of genres displays the name
    # instead of [name] + description
    genre = NameModelChoiceField(
        queryset=Genre.objects.all().order_by("name"), required=False
    )

    proofread_by = forms.ModelMultipleChoiceField(
        queryset=get_user_model()
        .objects.filter(Q(is_superuser=True) | Q(groups_new__name="editor"))
        .distinct()
        .order_by("last_name"),
        required=False,
        widget=FilteredSelectMultiple(verbose_name="proofread by", is_stacked=False),
    )


class AdminFeastForm(forms.ModelForm):
    class Meta:
        model = Feast
        fields = "__all__"

    name = forms.CharField(required=True, widget=TextInputWidget)


class AdminGenreForm(forms.ModelForm):
    class Meta:
        model = Genre
        fields = "__all__"

    name = forms.CharField(required=True, widget=TextInputWidget)
    description = forms.CharField(required=True, widget=TextAreaWidget)


class AdminNotationForm(forms.ModelForm):
    class Meta:
        model = Notation
        fields = "__all__"

    name = forms.CharField(required=True, widget=TextInputWidget)
    name.widget.attrs.update({"style": "width: 400px;"})


class AdminServiceForm(forms.ModelForm):
    class Meta:
        model = Service
        fields = "__all__"

    name = forms.CharField(required=True, widget=TextInputWidget)
    description = forms.CharField(required=True, widget=TextAreaWidget)


class AdminProvenanceForm(forms.ModelForm):
    class Meta:
        model = Provenance
        fields = "__all__"

    name = forms.CharField(required=True, widget=TextInputWidget)


class AdminSegmentForm(forms.ModelForm):
    class Meta:
        model = Segment
        fields = "__all__"

    name = forms.CharField(required=True, widget=TextInputWidget)
    name.widget.attrs.update({"style": "width: 400px;"})


class AdminSequenceForm(forms.ModelForm):
    class Meta:
        model = Sequence
        fields = "__all__"
        widgets = {
            "volpiano": VolpianoAreaWidget(),
            "indexing_notes": TextAreaWidget(),
            "manuscript_full_text_std_proofread": CheckboxWidget(),
            "manuscript_full_text_proofread": CheckboxWidget(),
            "volpiano_proofread": CheckboxWidget(),
            "other_fields_proofread": CheckboxWidget(),
            "chant_range": VolpianoAreaWidget(),
        }

    # We use NameModelChoiceField here so the dropdown list of service/mass displays the name
    # instead of [name] + description
    service = NameModelChoiceField(
        queryset=Service.objects.all().order_by("name"),
        required=False,
    )
    # We use NameModelChoiceField here so the dropdown list of genres displays the name
    # instead of [name] + description
    genre = NameModelChoiceField(
        queryset=Genre.objects.all().order_by("name"), required=False
    )

    proofread_by = forms.ModelMultipleChoiceField(
        queryset=get_user_model()
        .objects.filter(Q(is_superuser=True) | Q(groups_new__name="editor"))
        .distinct()
        .order_by("last_name"),
        required=False,
        widget=FilteredSelectMultiple(verbose_name="proofread by", is_stacked=False),
    )


# class AdminSourceForm(forms.ModelForm):
#     class Meta:
#         model = Source
#         fields = "__all__"
#
#     # title = forms.CharField(
#     #     required=True,
#     #     widget=TextInputWidget,
#     #     help_text="Full Source Identification (City, Archive, Shelf-mark)",
#     # )
#     # title.widget.attrs.update({"style": "width: 610px;"})
#     #
#     # siglum = forms.CharField(
#     #     required=True,
#     #     widget=TextInputWidget,
#     #     help_text="RISM-style siglum + Shelf-mark (e.g. GB-Ob 202).",
#     # )
#
#     shelfmark = forms.CharField(
#         required=True,
#         widget=TextInputWidget,
#     )
#
#     name = forms.CharField(required=False, widget=TextInputWidget)
#
#     holding_institution = forms.ModelChoiceField(
#         queryset=Institution.objects.all().order_by("city", "name"),
#         required=False,
#     )
#
#     provenance = forms.ModelChoiceField(
#         queryset=Provenance.objects.all().order_by("name"),
#         required=False,
#     )
#
#     century = forms.ModelMultipleChoiceField(
#         queryset=Century.objects.all().order_by("name"),
#         required=False,
#         widget=FilteredSelectMultiple(verbose_name="Century", is_stacked=False),
#     )
#
#     current_editors = forms.ModelMultipleChoiceField(
#         queryset=get_user_model()
#         .objects.filter(
#             Q(groups__name="project manager")
#             | Q(groups__name="editor")
#             | Q(groups__name="contributor")
#         )
#         .distinct()
#         .order_by("full_name"),
#         required=False,
#         widget=FilteredSelectMultiple(verbose_name="current editors", is_stacked=False),
#     )
#
#     inventoried_by = forms.ModelMultipleChoiceField(
#         queryset=get_user_model().objects.all().order_by("full_name"),
#         required=False,
#         widget=FilteredSelectMultiple(verbose_name="inventoried by", is_stacked=False),
#     )
#
#     full_text_entered_by = forms.ModelMultipleChoiceField(
#         queryset=get_user_model().objects.all().order_by("full_name"),
#         required=False,
#         widget=FilteredSelectMultiple(
#             verbose_name="full text entered by", is_stacked=False
#         ),
#     )
#
#     description_entered_by = forms.ModelMultipleChoiceField(
#         queryset=get_user_model().objects.all().order_by("full_name"),
#         required=False,
#         widget=FilteredSelectMultiple(
#             verbose_name="description entered by", is_stacked=False
#         ),
#     )
#
#     melodies_entered_by = forms.ModelMultipleChoiceField(
#         queryset=get_user_model().objects.all().order_by("full_name"),
#         required=False,
#         widget=FilteredSelectMultiple(
#             verbose_name="melodies entered by", is_stacked=False
#         ),
#     )
#
#     proofreaders = forms.ModelMultipleChoiceField(
#         queryset=get_user_model().objects.all().order_by("full_name"),
#         required=False,
#         widget=FilteredSelectMultiple(verbose_name="proofreaders", is_stacked=False),
#     )
#
#     other_editors = forms.ModelMultipleChoiceField(
#         queryset=get_user_model().objects.all().order_by("full_name"),
#         required=False,
#         widget=FilteredSelectMultiple(verbose_name="other editors", is_stacked=False),
#     )
#
#     complete_inventory = forms.ChoiceField(
#         choices=COMPLETE_INVENTORY_FORM_CHOICES, required=False
#     )


class AdminUserChangeForm(forms.ModelForm):
    class Meta:
        model = get_user_model()
        fields = "__all__"

    email = forms.CharField(
        required=True,
        widget=TextInputWidget,
    )
    email.widget.attrs.update({"style": "width: 300px;"})

    password = ReadOnlyPasswordHashField(
        help_text=(
            "Raw passwords are not stored, so there is no way to see "
            "this user's password, but you can change the password "
            'using <a href="../password/">this form</a>.'
        )
    )


class ImageLinkForm(forms.Form):
    """
    Subclass of Django's Form class that creates the form we use for
    adding image links to chants in a source.

    Initialize the Form with a field for every folio in the source,
    passed as the "initial" parameter, which is a dictionary with a key
    for every folio and a blank value.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        initial = kwargs.get("initial")
        if initial:
            for folio in initial:
                self.fields[folio] = NormalizedURLFormField(
                    widget=HiddenInput(attrs={"class": "img-link-input"}),
                    required=False,
                )

    def save(self, source: Source) -> None:
        """
        Save the image links to the database.

        Args:
            source: The source to which the image links belong.
        """
        cleaned_data = self.cleaned_data
        for folio, image_link in cleaned_data.items():
            if image_link != "":
                source.chant_set.filter(folio=folio).update(image_link=image_link)


class BrowseChantsBulkEditForm(forms.ModelForm):
    class Meta:
        model = Chant
        fields = [
            "id",
            "folio",
            "c_sequence",
            "manuscript_full_text_std_spelling",
            "feast",
            "service",
            "genre",
            "position",
            "cantus_id",
            "mode",
        ]
        widgets = {
            "id": HiddenInput(),
            "position": TextInputWidget(),
            "cantus_id": TextInputWidget(),
            "mode": TextInputWidget(),
        }

    folio = forms.CharField(
        required=True,
        widget=TextInputWidget,
    )

    c_sequence = forms.IntegerField(
        required=True,
        widget=TextInputWidget,
    )

    manuscript_full_text_std_spelling = CantusDBLatinField(
        widget=TextAreaWidget,
        required=True,
    )

    feast = forms.ChoiceField(
        widget=autocomplete.Select2(url="feast-autocomplete"), required=False
    )

    service = forms.ChoiceField(
        widget=autocomplete.Select2(url="service-autocomplete"), required=False
    )

    genre = forms.ChoiceField(
        widget=autocomplete.Select2(url="genre-autocomplete"), required=False
    )

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        field_choices = kwargs.pop("field_choices")
        self.field_objects: Dict[str, Dict[int, Model]] = kwargs.pop("field_objects")
        super().__init__(*args, **kwargs)
        self.fields["feast"].choices = field_choices["feast"]
        self.fields["service"].choices = field_choices["service"]
        self.fields["genre"].choices = field_choices["genre"]

    def _clean_fk_field(self, field: str) -> Optional[Model]:
        id_str = self.cleaned_data[field]
        if id_str == "":
            return None
        obj = self.field_objects[field][int(id_str)]
        return obj

    def clean_feast(self) -> Optional[Feast]:
        return self._clean_fk_field("feast")

    def clean_genre(self) -> Optional[Genre]:
        return self._clean_fk_field("genre")

    def clean_service(self) -> Optional[Service]:
        return self._clean_fk_field("service")


class BaseBrowseChantsBulkEditFormset(forms.BaseModelFormSet):

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """
        Override the formset initialization to do a single
        query for the field choices instead of one query
        for each form in the formset.
        """
        form_kwargs = kwargs.get("form_kwargs", {})
        feasts = Feast.objects.all().in_bulk()
        services = Service.objects.all().in_bulk()
        genres = Genre.objects.all().in_bulk()
        form_kwargs["field_choices"] = {
            "feast": [(feast.id, feast.name) for feast in feasts.values()],
            "service": [(service.id, service.name) for service in services.values()],
            "genre": [(genre.id, genre.name) for genre in genres.values()],
        }
        form_kwargs["field_objects"] = {
            "feast": feasts,
            "service": services,
            "genre": genres,
        }
        kwargs["form_kwargs"] = form_kwargs
        kwargs["prefix"] = "chant_set"
        super().__init__(*args, **kwargs)


BrowseChantsBulkEditFormset = forms.modelformset_factory(
    Chant,
    form=BrowseChantsBulkEditForm,
    formset=BaseBrowseChantsBulkEditFormset,
    extra=0,
    can_delete=False,
    can_order=False,
)
