from django import forms
from .models import Chant, Office, Genre, Feast
from .widgets import *
# ModelForm allows to build a form directly from a model
# see https://docs.djangoproject.com/en/3.0/topics/forms/modelforms/

# CreateView is a combination of 
# several other classes that handle ModelForms and template rendering (TemplateView).

'''
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
'''
#3 best
class ChantCreateForm(forms.ModelForm):
    class Meta:
        model = Chant
        # sepcify either 'fields' or 'excludes' so that django knows which fields to use
        fields = [
            'marginalia', 'folio', 'sequence_number', 
            'office', 'genre', 'position', 'cantus_id', 'feast',
            'mode', 'differentia',
            'finalis', 'extra', 'chant_range',
            'manuscript_full_text_std_spelling',
            'manuscript_full_text',
            'volpiano',
            'melody_id',
            #'content_structure',
            'indexing_notes',
            ]
        widgets = {
            # 'marginalia': forms.TextInput(attrs={'class':'form-control form-control-sm'}),
            'marginalia': TextInputWidget(),
            # 'folio': forms.TextInput(attrs={'class':'form-control form-control-sm'}),
            'folio': TextInputWidget(),
            'sequence_number': TextInputWidget(),
            #'office': forms.Select(attrs={'class': 'form-control custom-select custom-select-sm'}, ),
            #'office': SelectWidget(),
            #'genre': SelectWidget(choices=Office.objects.all().values("id").order_by('name')),
            'position': TextInputWidget(),
            'cantus_id': TextInputWidget(),
            #'feast': SelectWidget(),
            'mode': TextInputWidget(),
            'differentia': TextInputWidget(),
            'finalis': TextInputWidget(),
            'extra': TextInputWidget(),
            'chant_range': VolpianoInputWidget(),
            'manuscript_full_text_std_spelling': TextAreaWidget(),
            'manuscript_full_text': TextAreaWidget(),
            'volpiano': VolpianoAreaWidget(),
            'melody_id': TextInputWidget(),
            #'content_structure': TextInputWidget(),
            'indexing_notes': TextAreaWidget()
            }
    
    office = forms.ModelChoiceField(
        queryset=Office.objects.all().order_by("name"),
        )
    office.widget.attrs.update({"class": "form-control custom-select custom-select-sm"})

    genre = forms.ModelChoiceField(
        queryset=Genre.objects.all().order_by("name"),
        )
    genre.widget.attrs.update({"class": "form-control custom-select custom-select-sm"})

    feast = forms.ModelChoiceField(
        queryset=Feast.objects.all().order_by("name"),
        )
    feast.widget.attrs.update({"class": "form-control custom-select custom-select-sm"})
