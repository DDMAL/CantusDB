from django import forms
from .models import Chant, Office
from .widgets import TextInputWidget, SelectWidget, TextAreaWidget
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
            ]
        widgets = {
            # 'marginalia': forms.TextInput(attrs={'class':'form-control form-control-sm'}),
            'marginalia': TextInputWidget(),
            # 'folio': forms.TextInput(attrs={'class':'form-control form-control-sm'}),
            'folio': TextInputWidget(),
            'sequence_number': TextInputWidget(),
            #'office': forms.Select(attrs={'class': 'form-control custom-select custom-select-sm'})
            #'office': SelectWidget(attrs={'choices': Office.objects.all().order_by("name").values("id", "name")}),
            'office': SelectWidget(choices=Office.objects.values_list()),
            'genre': SelectWidget(choices=Office.objects.all().values("id").order_by('name')),
            'position': TextInputWidget(),
            'cantus_id': TextInputWidget(),
            'feast': TextInputWidget(),
            'mode': TextInputWidget(),
            'differentia': TextInputWidget(),
            'finalis': TextInputWidget(),
            'extra': TextInputWidget(),
            'chant_range': TextInputWidget(),
            'manuscript_full_text_std_spelling': TextAreaWidget(),
            'manuscript_full_text': TextAreaWidget(),
            
        }
