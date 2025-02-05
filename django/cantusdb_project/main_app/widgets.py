from django.forms.widgets import TextInput, Select, Textarea, CheckboxInput


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

    class Media:
        js = [
            "https://cdn.jsdelivr.net/npm/marked/marked.min.js",
            "js/markdown_widget.js",
        ]
        css = {"all": ["stylesheets/markdown_widget.css"]}
