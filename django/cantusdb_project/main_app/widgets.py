from django.forms.widgets import TextInput, Select, Textarea
from .models import Office
class TextInputWidget(TextInput):

    def __init__(self):
        self.attrs = {"class": "form-control form-control-sm"}

class SelectWidget(Select):

    # class Media:
    #     # potentially put js and css here
    #     pass

    def __init__(self, choices):
        #super().__init__(self, attrs)
        self.attrs = {"class": "form-control custom-select custom-select-sm"}
        self.choices = choices
    # def get_context(self, name value, attrs):
    #     pass

class TextAreaWidget(Textarea):
    def __init__(self):
        self.attrs = {"class": "form-control", "rows": "3"}

class VolpianoWidget(Textarea):
    def __init__(self):
        self.attrs = {
            "class": "form-control", 
            "rows": "1.5", 
            "style": "font-family: Volpiano; font-size: xx-large"
            }