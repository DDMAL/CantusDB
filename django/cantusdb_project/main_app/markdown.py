"""Render source descriptions and editor previews through the same sanitizer."""

import re
from html import escape
from html.parser import HTMLParser

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


class _LegacyLineBreaks(HTMLParser):
    """Keep authored newlines inside raw HTML blocks, before sanitization.

    cmark applies HARDBREAKS only to Markdown. Its generated block elements have
    source positions; imported HTML elements do not. Preserve the old source
    page's line breaks inside those elements without doubling Markdown breaks
    or changing whitespace in code.
    """

    blocks = {
        "blockquote",
        "center",
        "dd",
        "div",
        "dt",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "li",
        "ol",
        "p",
        "td",
        "th",
        "ul",
    }
    voids = {
        "area",
        "base",
        "br",
        "col",
        "embed",
        "hr",
        "img",
        "input",
        "link",
        "meta",
        "param",
        "source",
        "track",
        "wbr",
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.stack: list[tuple[str, bool]] = []
        self.after_generated_block = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.after_generated_block = False
        self.parts.append(self.get_starttag_text())
        if tag not in self.voids:
            raw = tag in self.blocks and "data-sourcepos" not in dict(attrs)
            self.stack.append((tag, raw))

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.after_generated_block = False
        self.parts.append(self.get_starttag_text())

    def handle_endtag(self, tag: str) -> None:
        self.after_generated_block = False
        self.parts.append(f"</{tag}>")
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index][0] == tag:
                self.after_generated_block = (
                    tag in self.blocks and not self.stack[index][1]
                )
                del self.stack[index:]
                break

    def handle_data(self, data: str) -> None:
        if self.after_generated_block and not data.strip():
            # cmark emits a formatting newline after generated blocks. An
            # unclosed legacy ancestor must not turn it into a visible break.
            self.parts.append(data)
            return
        self.after_generated_block = False
        # A generated paragraph ends any inherited legacy context, even if an
        # earlier raw tag was never closed. cmark already added its breaks.
        raw_block = next(
            (raw for tag, raw in reversed(self.stack) if tag in self.blocks), False
        )
        # HTMLParser resolves character references. Escape text again so bare
        # ampersands retain their meaning without inventing entity semicolons.
        data = escape(data, quote=False)
        if raw_block and not any(
            tag in {"pre", "code", "script", "style", "textarea"}
            for tag, _ in self.stack
        ):
            data = data.replace("\n", "<br>\n")
        self.parts.append(data)

    def handle_comment(self, data: str) -> None:
        self.parts.append(f"<!--{data}-->")


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
    legacy = _LegacyLineBreaks()
    try:
        legacy.feed(html)
        legacy.close()
    except AssertionError:
        # HTMLParser rejects unknown declarations such as <![foo]>. Leave
        # malformed HTML to nh3's tolerant HTML5 parser instead of failing the
        # source page or returning a partially parsed description.
        pass
    else:
        html = "".join(legacy.parts)
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
