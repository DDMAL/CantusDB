from django import forms
from .models import Chant, Office, Genre, Feast, Source
from .widgets import *

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
            "sequence_number",
            "office",
            "genre",
            "position",
            "cantus_id",
            "feast",
            "mode",
            "differentia",
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
            "folio": TextInputWidget(),
            "sequence_number": TextInputWidget(),
            # the widgets dictionary is ignored for a model field with a non-empty choices attribute.
            # In this case, you must override the form field to use a different widget.
            # this goes for all foreignkey fields here, which are written explicitly below to override form field
            "position": TextInputWidget(),
            "cantus_id": TextInputWidget(),
            #'feast': SelectWidget(),
            "mode": TextInputWidget(),
            "differentia": TextInputWidget(),
            "finalis": TextInputWidget(),
            "extra": TextInputWidget(),
            "chant_range": VolpianoInputWidget(),
            "manuscript_full_text_std_spelling": TextAreaWidget(),
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


class ContactForm(forms.Form):
    name = forms.CharField(max_length=100)
    sender_email = forms.EmailField()
    subject = forms.CharField(max_length=100)
    message = forms.CharField(widget=forms.Textarea)
