from django.forms.widgets import TextInput, Select, Textarea, CheckboxInput, Media
from django.templatetags.static import static


class TextInputWidget(TextInput):
    def __init__(self) -> None:
        self.attrs = {"class": "form-control form-control-sm"}


class SelectWidget(Select):
    def __init__(self) -> None:
        attrs = {"class": "form-select form-select-sm"}
        super().__init__(attrs=attrs)


class TextAreaWidget(Textarea):
    def __init__(self) -> None:
        self.attrs = {"class": "form-control", "rows": "3"}


class VolpianoAreaWidget(Textarea):
    def __init__(self) -> None:
        self.attrs = {
            "class": "form-control",
            "rows": "1.5",
            "style": "font-family: Volpiano; font-size: xx-large",
        }


class VolpianoInputWidget(TextInput):
    def __init__(self) -> None:
        self.attrs = {
            "class": "form-control form-control-sm",
            "style": "font-family: Volpiano; font-size: xx-large",
        }


class CheckboxWidget(CheckboxInput):
    pass


class MarkdownWidget(TextAreaWidget):
    template_name = "widgets/markdown_widget.html"

    @property
    def media(self) -> Media:
        # Fetch the matching assets when replacing the old marked-based widget.
        # Resolve static paths before appending queries so storage does not
        # escape the query into the filename.
        return Media(
            js=[f"{static('js/markdown_widget.js')}?v=server-preview-1"],
            css={"all": [f"{static('css/markdown_widget.css')}?v=server-preview-1"]},
        )
