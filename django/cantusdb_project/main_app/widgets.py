from django.forms.widgets import TextInput, Select, Textarea, CheckboxInput
from django.utils.safestring import mark_safe


class TextInputWidget(TextInput):
    def __init__(self):
        self.attrs = {"class": "form-control form-control-sm"}


class SelectWidget(Select):
    """
    not used, this widget does work, but we cannot order the choices by name
    """

    def __init__(self):
        attrs = {"class": "form-control custom-select custom-select-sm"}
        super().__init__(attrs=attrs)
        # super().choices = choices
        # self.choices = super().choices


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


class AdminTextAreaWidget(Textarea):
    def __init__(self):
        self.attrs = {"class": "form-control", "rows": 10, "cols": 75}

    def render(self, name, value, attrs=None, renderer=None):
        return super().render(name, value, attrs=self.attrs) + mark_safe(
            '<span style="color: red; font-weight: bold;"> &nbsp;* </span>'
        )


class AdminTextInputWidget(TextInputWidget):
    def render(self, name, value, attrs=None, renderer=None):
        return super().render(name, value) + mark_safe(
            '<span style="color: red; font-weight: bold;"> &nbsp;* </span>'
        )
