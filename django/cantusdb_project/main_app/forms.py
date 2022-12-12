from django import forms
from .models import Chant, Office, Genre, Feast, Source, RismSiglum, Provenance, Century, Sequence
from .widgets import (TextInputWidget,
                VolpianoInputWidget,
                TextAreaWidget,
                VolpianoAreaWidget,
                SelectWidget,
                CheckboxWidget,
)
from django.contrib.auth import get_user_model
from django.db.models import Q

# ModelForm allows to build a form directly from a model
# see https://docs.djangoproject.com/en/3.0/topics/forms/modelforms/

"""
# 3 ways of doing it
#1 worst, helptext in the model will be missing
class CommetnForm(forms.Form):
    marginalia = forms.CharField(
        label="Marginalia", widget=forms.TextInput(), help_text="help"
    )
    url = forms.URLField()
    comment = forms.CharField()

    url.widget.attrs.update({'class': 'special'})
    comment.widget.attrs.update(size='40')
#2
class CommentForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['name'].widget.attrs.update({'class': 'special'})
        self.fields['comment'].widget.attrs.update(size='40')
"""
# 3 best
class ChantCreateForm(forms.ModelForm):
    class Meta:
        model = Chant
        # specify either 'fields' or 'excludes' so that django knows which fields to use
        fields = [
            "marginalia",
            "folio",
            "c_sequence",
            "office",
            "genre",
            "position",
            "cantus_id",
            "feast",
            "mode",
            "differentia",
            "differentia_new",
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
        ]
        widgets = {
            "marginalia": TextInputWidget(),
            # the widgets dictionary is ignored for a model field with a non-empty choices attribute.
            # In this case, you must override the form field to use a different widget.
            # this goes for all foreignkey fields here, which are written explicitly below to override form field
            "position": TextInputWidget(),
            "cantus_id": TextInputWidget(),
            #'feast': SelectWidget(),
            "mode": TextInputWidget(),
            "differentia": TextInputWidget(),
            "differentia_new": TextInputWidget(),
            "finalis": TextInputWidget(),
            "extra": TextInputWidget(),
            "chant_range": VolpianoInputWidget(),
            "manuscript_full_text": TextAreaWidget(),
            "volpiano": VolpianoAreaWidget(),
            "image_link": TextInputWidget(),
            "melody_id": TextInputWidget(),
            "content_structure": TextInputWidget(),
            "indexing_notes": TextAreaWidget(),
            "addendum": TextInputWidget(),
        }
        # error_messages = {
        #     # specify custom error messages for each field here
        # }

    manuscript_full_text_std_spelling = forms.CharField(
        required=True,
        widget=TextAreaWidget,
        help_text="Manuscript full text with standardized spelling. Enter the words "
        "according to the manuscript but normalize their spellings following "
        "Classical Latin forms. Use upper-case letters for proper nouns, "
        'the first word of each chant, and the first word after "Alleluia" for '
        "Mass Alleluias. Punctuation is omitted.",
    )

    folio = forms.CharField(
        required=True, widget=TextInputWidget, help_text="Binding order",
    )

    c_sequence = forms.CharField(
        required=True, widget=TextInputWidget, help_text="Each folio starts with '1'.",
    )

    office = forms.ModelChoiceField(
        queryset=Office.objects.all().order_by("name"), required=False
    )
    office.widget.attrs.update({"class": "form-control custom-select custom-select-sm"})

    genre = forms.ModelChoiceField(
        queryset=Genre.objects.all().order_by("name"), required=False
    )
    genre.widget.attrs.update({"class": "form-control custom-select custom-select-sm"})

    feast = forms.ModelChoiceField(
        queryset=Feast.objects.all().order_by("name"), required=False
    )
    feast.widget.attrs.update({"class": "form-control custom-select custom-select-sm"})

    # automatically computed fields
    # source and incipit are mandatory fields in model,
    # but have to be optional in the form, otherwise the field validation won't pass
    source = forms.ModelChoiceField(
        queryset=Source.objects.all().order_by("title"),
        required=False,
        error_messages={
            "invalid_choice": "This source does not exist, please switch to a different source."
        },
    )
    incipit = forms.CharField(required=False)


class SourceCreateForm(forms.ModelForm):
    class Meta:
        model = Source
        fields = [
            "title",
            "rism_siglum",
            "siglum",
            "provenance",
            "provenance_notes",
            "full_source",
            "date",
            "century",
            "cursus",
            "current_editors",
            "melodies_entered_by",
            "complete_inventory",
            "summary",
            "description",
            "selected_bibliography",
            "image_link",
            "fragmentarium_id",
            "dact_id",
            "indexing_notes"
        ]
        widgets = {
            "title": TextInputWidget(),
            "siglum": TextInputWidget(),
            "provenance_notes": TextInputWidget(),
            "date": TextInputWidget(),
            "cursus": SelectWidget(),
            "summary": TextAreaWidget(),
            "description": TextAreaWidget(),
            "selected_bibliography": TextAreaWidget(),
            "image_link": TextInputWidget(),
            "fragmentarium_id": TextInputWidget(),
            "dact_id": TextInputWidget(),
            "indexing_notes": TextAreaWidget()
        }
    rism_siglum = forms.ModelChoiceField(
        queryset=RismSiglum.objects.all().order_by("name"), required=False
    )
    rism_siglum.widget.attrs.update({"class": "form-control custom-select custom-select-sm"})

    provenance = forms.ModelChoiceField(
        queryset=Provenance.objects.all().order_by("name"), required=False
    )
    provenance.widget.attrs.update({"class": "form-control custom-select custom-select-sm"})

    TRUE_FALSE_CHOICES_SOURCE = (
        (True, "Full source"), 
        (False, "Fragment or Fragmented")
    )

    full_source = forms.ChoiceField(
        choices=TRUE_FALSE_CHOICES_SOURCE, required=False
    )
    full_source.widget.attrs.update({"class": "form-control custom-select custom-select-sm"})

    century = forms.ModelMultipleChoiceField(
        queryset=Century.objects.all().order_by("name"), required=False
    )
    century.widget.attrs.update({"class": "form-control custom-select custom-select-sm"})

    current_editors = forms.ModelMultipleChoiceField(
        queryset=get_user_model().objects.filter(
            Q(groups__name="project manager")|
            Q(groups__name="editor")|
            Q(groups__name="contributor")).order_by("last_name"), required=False
    )
    current_editors.widget.attrs.update({"class": "form-control custom-select custom-select-sm"})

    melodies_entered_by = forms.ModelMultipleChoiceField(
        queryset=get_user_model().objects.all().order_by("full_name"), required=False
    )
    melodies_entered_by.widget.attrs.update({"class": "form-control custom-select custom-select-sm"})

    TRUE_FALSE_CHOICES_INVEN = (
        (True, "Complete"), 
        (False, "Incomplete")
    )

    complete_inventory = forms.ChoiceField(
        choices=TRUE_FALSE_CHOICES_INVEN, required=False
    )
    complete_inventory.widget.attrs.update({"class": "form-control custom-select custom-select-sm"})

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
            "office",
            "genre",
            "position",
            "cantus_id",
            "melody_id",
            "mode",
            "finalis",
            "differentia",
            "differentia_new",
            "extra",
            "image_link",
            "indexing_notes"
        ]
        widgets = {
            "manuscript_full_text": TextAreaWidget(),
            "volpiano": VolpianoAreaWidget(),
            "marginalia": TextInputWidget(),
            "position": TextInputWidget(),
            "cantus_id": TextInputWidget(),
            "melody_id": TextInputWidget(),
            "mode": TextInputWidget(),
            "finalis": TextInputWidget(),
            "differentia": TextInputWidget(),
            "differentia_new": TextInputWidget(),
            "extra": TextInputWidget(),
            "image_link": TextInputWidget(),
            "indexing_notes": TextAreaWidget()
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
    feast = forms.ModelChoiceField(
        queryset=Feast.objects.all().order_by("name"), required=False
    )
    feast.widget.attrs.update({"class": "form-control custom-select custom-select-sm"})

    office = forms.ModelChoiceField(
        queryset=Office.objects.all().order_by("name"), required=False
    )
    office.widget.attrs.update({"class": "form-control custom-select custom-select-sm"})

    genre = forms.ModelChoiceField(
        queryset=Genre.objects.all().order_by("name"), required=False
    )
    genre.widget.attrs.update({"class": "form-control custom-select custom-select-sm"})

    folio = forms.CharField(
        required=True, widget=TextInputWidget, help_text="Binding order",
    )

    c_sequence = forms.CharField(
        required=True, widget=TextInputWidget, help_text="Each folio starts with '1'.",
    )

class ChantProofreadForm(forms.ModelForm):
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
            "office",
            "genre",
            "position",
            "cantus_id",
            "melody_id",
            "mode",
            "finalis",
            "differentia",
            "extra",
            "image_link",
            "indexing_notes",
            # additional fields for the proofreading form
            "manuscript_full_text_std_proofread",
            "manuscript_full_text_proofread",
            "volpiano_proofread",
            "proofread_by",
            "manuscript_syllabized_full_text",
            "chant_range",
            "siglum",
            "addendum",
            "differentia_new"
        ]
        widgets = {
            "manuscript_full_text_std_spelling": TextAreaWidget(),
            "manuscript_full_text": TextAreaWidget(),
            "volpiano": VolpianoAreaWidget(),
            "marginalia": TextInputWidget(),
            "folio": TextInputWidget(),
            "c_sequence": TextInputWidget(),
            "office": TextInputWidget(),
            "genre": TextInputWidget(),
            "position": TextInputWidget(),
            "cantus_id": TextInputWidget(),
            "melody_id": TextInputWidget(),
            "mode": TextInputWidget(),
            "finalis": TextInputWidget(),
            "differentia": TextInputWidget(),
            "extra": TextInputWidget(),
            "image_link": TextInputWidget(),
            "indexing_notes": TextAreaWidget(),
            # additional fields for the proofreading form
            "manuscript_full_text_std_proofread": CheckboxWidget(),
            "manuscript_full_text_proofread": CheckboxWidget(),
            "volpiano_proofread": CheckboxWidget(),
            "manuscript_syllabized_full_text": TextAreaWidget(),
            "chant_range": VolpianoAreaWidget(),
            "siglum": TextInputWidget(),
            "addendum": TextInputWidget(),
            "differentia_new": TextInputWidget()
        }
    feast = forms.ModelChoiceField(
        queryset=Feast.objects.all().order_by("name"), required=False
    )
    feast.widget.attrs.update({"class": "form-control custom-select custom-select-sm"})

    proofread_by = forms.ModelMultipleChoiceField(
        queryset=get_user_model().objects.filter(
            Q(groups__name="project manager")|
            Q(groups__name="editor")
        ).order_by("last_name"), required=False
    )
    proofread_by.widget.attrs.update({"class": "form-control custom-select custom-select-sm"})

class SourceEditForm(forms.ModelForm):
    class Meta:
        model = Source
        fields = [
            "title",
            "rism_siglum",
            "siglum",
            "provenance",
            "provenance_notes",
            "full_source",
            "date",
            "century",
            "cursus",
            "current_editors",
            "melodies_entered_by",
            "complete_inventory",
            "summary",
            "description",
            "selected_bibliography",
            "image_link",
            "fragmentarium_id",
            "dact_id",
            "indexing_notes"
        ]
        widgets = {
            "title": TextInputWidget(),
            "rism_siglum": TextInputWidget(),
            "siglum": TextInputWidget(),
            "provenance_notes": TextInputWidget(),
            "date": TextInputWidget(),
            "summary": TextAreaWidget(),
            "description": TextAreaWidget(),
            "selected_bibliography": TextAreaWidget(),
            "image_link": TextInputWidget(),
            "fragmentarium_id": TextInputWidget(),
            "dact_id": TextInputWidget(),
            "indexing_notes": TextAreaWidget(),
        }
    
    provenance = forms.ModelChoiceField(
        queryset=Provenance.objects.all().order_by("name"), required=False
    )
    provenance.widget.attrs.update({"class": "form-control custom-select custom-select-sm"}) # adds styling
    
    century = forms.ModelMultipleChoiceField(
        queryset=Century.objects.all().order_by("name"), required = False
    )
    century.widget.attrs.update({"class": "form-control custom-select custom-select-sm"})

    CHOICES_FULL_SOURCE = (
        (None, "None"),
        (True, "Full source"),
        (False, "Fragment or Fragmented"),        
    )
    full_source = forms.ChoiceField(
        choices=CHOICES_FULL_SOURCE, required=False
    )
    full_source.widget.attrs.update({"class": "form-control custom-select custom-select-sm"})

    CHOICES_CURSUS = (
        (None, "None"),
        ("Monastic", "Monastic"),
        ("Secular", "Secular"),
    )
    cursus = forms.ChoiceField(
        choices=CHOICES_CURSUS, required=False
    )
    cursus.widget.attrs.update({"class": "form-control custom-select custom-select-sm"})

    current_editors = forms.ModelMultipleChoiceField(
        queryset=get_user_model().objects.filter(
            Q(groups__name="project manager")|
            Q(groups__name="editor")|
            Q(groups__name="contributor")).order_by("last_name"), required=False
    )
    current_editors.widget.attrs.update({"class": "form-control custom-select custom-select-sm"})

    melodies_entered_by = forms.ModelMultipleChoiceField(
        queryset=get_user_model().objects.all().order_by("full_name"), required=False
    )
    melodies_entered_by.widget.attrs.update({"class": "form-control custom-select custom-select-sm"})

    CHOICES_COMPLETE_INV = (
        (True, "complete inventory"),
        (False, "partial inventory"),
    )
    complete_inventory = forms.ChoiceField(
        choices=CHOICES_COMPLETE_INV, required=False
    )
    complete_inventory.widget.attrs.update({"class": "form-control custom-select custom-select-sm"})

class SequenceEditForm(forms.ModelForm):
    class Meta:
        model = Sequence
        fields = [
            "title",
            "siglum",
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
            "siglum": TextInputWidget(),
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
    
    genre = forms.ModelChoiceField(
        queryset=Genre.objects.all().order_by("name"), required=False
    )
    genre.widget.attrs.update({"class": "form-control custom-select custom-select-sm"})
    
    source = forms.ModelChoiceField(
        queryset=Source.objects.all().order_by("title"), required = False
    )
    source.widget.attrs.update({"class": "form-control custom-select custom-select-sm"})

class ChantEditSyllabificationForm(forms.ModelForm):
    class Meta:
        model = Chant
        fields = [
            "manuscript_full_text",
            "manuscript_syllabized_full_text",
        ]
        widgets = {
            "manuscript_full_text": TextAreaWidget(),
            "manuscript_syllabized_full_text": TextAreaWidget(),
        }
