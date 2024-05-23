from django.forms.widgets import TextInput, Select, Textarea, CheckboxInput
from django.utils.safestring import mark_safe


class TextInputWidget(TextInput):
    def __init__(self):
        self.attrs = {"class": "form-control form-control-sm"}


class SelectWidget(Select):
    def __init__(self):
        attrs = {"class": "form-control custom-select custom-select-sm"}
        super().__init__(attrs=attrs)


class TextAreaWidget(Textarea):
    def __init__(self):
        self.attrs = {"class": "form-control", "rows": "3"}


class VolpianoAreaWidget(Textarea):
    def __init__(self):
        self.attrs = {
            "class": "form-control",
            "rows": "1.5",
            "style": "font-family: Volpiano; font-size: xx-large",
        }


class VolpianoInputWidget(TextInput):
    def __init__(self):
        self.attrs = {
            "class": "form-control form-control-sm",
            "style": "font-family: Volpiano; font-size: xx-large",
        }


class CheckboxWidget(CheckboxInput):
    pass
