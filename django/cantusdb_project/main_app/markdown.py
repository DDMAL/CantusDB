"""Render source descriptions and editor previews through the same sanitizer."""

import re

from cmarkgfm import github_flavored_markdown_to_html
from cmarkgfm.cmark import Options
from django.utils.safestring import SafeString, mark_safe
import nh3

# Retain ordinary legacy HTML, including tables and explicit folio numbers.
# Event handlers, styles, embedded documents and unsafe URL schemes are removed.
_attributes = {tag: set(attrs) for tag, attrs in nh3.ALLOWED_ATTRIBUTES.items()}
_attributes["li"] = {"value"}
_attributes["*"] = {"title"}
_cleaner = nh3.Cleaner(
    attributes=_attributes,
    url_schemes={"http", "https", "mailto", "ftp"},
)


def render_markdown(value: str) -> SafeString:
    """Render Markdown and legacy HTML, then sanitize before marking it safe."""
    html = github_flavored_markdown_to_html(
        value,
        options=(
            # Many imported descriptions are entire HTML blocks. Keep them
            # through parsing so nh3 can remove unsafe parts without hiding
            # the surrounding content. Preserve existing single line breaks.
            Options.CMARK_OPT_UNSAFE
            | Options.CMARK_OPT_HARDBREAKS
            | Options.CMARK_OPT_SOURCEPOS
        ),
    )
    lines = value.replace("\r\n", "\n").replace("\r", "\n").split("\n")

    def number_item(match: re.Match[str]) -> str:
        # Folio lists can deliberately skip numbers. cmark identifies each
        # parsed item's original marker, including in nested/quoted lists.
        line, column = int(match[1]) - 1, int(match[2]) - 1
        if 0 <= line < len(lines) and column >= 0:
            marker = re.match(r"([0-9]{1,9})[.)](?:\s|$)", lines[line][column:])
            if marker:
                return f'<li value="{int(marker[1])}">'
        return "<li>"

    html = re.sub(
        r'<li data-sourcepos="(\d{1,9}):(\d{1,9})-\d{1,9}:\d{1,9}">', number_item, html
    )
    # Sanitizing last also removes cmark's source-position attributes.
    return mark_safe(_cleaner.clean(html))
