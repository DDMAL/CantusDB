"""
Best-effort converter from the raw HTML found in legacy Source.description /
Source.selected_bibliography values to GitHub-flavored markdown, for #1239.

Written for the actual set of tags found in the affected fields (see
`convert_html_to_markdown` management command), not as a general-purpose
HTML-to-markdown library: p/div, br, ul/li, table/tr/td, a, b/strong, i/em,
span (only font-style: italic is meaningful here), font/u/sup/center
(unwrapped -- markdown has no equivalent, styling is dropped but text is
kept), h1-h6, blockquote.

Uses only beautifulsoup4/lxml, both already project dependencies -- adding a
dedicated HTML-to-markdown package for a one-time data migration wasn't
worth it.
"""

import re

from bs4 import BeautifulSoup, NavigableString, Tag

_UNWRAP_TAGS = {"font", "u", "sup", "center", "html", "body", "tbody", "thead"}

# Embedded-media tags have no markdown equivalent, and unwrapping one would
# discard the thing it points at. They are emitted as raw markup so that
# `contains_html_tags` sees them in the output and the caller flags the field
# for manual review. Most would also be caught by the void-element guard at the
# end of `_render`, but not `<embed>`: lxml does not treat it as void, so it
# swallows the following text as a child and renders non-empty. Listing them
# explicitly keeps the behaviour independent of parser quirks.
_FLAG_TAGS = {"embed", "object", "iframe", "video", "audio", "applet"}


def _render_children(node) -> str:
    return "".join(_render(child) for child in node.children)


def _split_edge_whitespace(text: str) -> tuple[str, str, str]:
    """
    Split `text` into (leading whitespace, content, trailing whitespace).

    Emphasis handlers can't just `.strip()`: markdown only closes emphasis when
    the marker is followed by punctuation or whitespace, so dropping a space
    that sat inside the tag welds `<em>Antiphonale </em>(1934)` into
    `_Antiphonale_(1934)` -- and `<span ...>Kyrie </span>eleison` into
    `_Kyrie_eleison`, which renders as literal underscores (#1957). Keeping the
    whitespace *outside* the markers preserves both the spacing and the
    emphasis.

    Where the legacy HTML has no space at all (`<i>AH</i>but`, which the old
    page rendered just as tightly) there is nothing to move out, so italics use
    `*` rather than `_`: CommonMark lets `*` close inside a word, while `_`
    would be left visible as literal underscores.
    """
    stripped = text.strip()
    if not stripped:
        return "", "", ""
    return (
        text[: len(text) - len(text.lstrip())],
        stripped,
        text[len(text.rstrip()) :],
    )


def _emphasise(node, left: str, right: str) -> str:
    lead, inner, trail = _split_edge_whitespace(_render_children(node))
    return f"{lead}{left}{inner}{right}{trail}" if inner else ""


def _render(node) -> str:
    if isinstance(node, NavigableString):
        # Legacy markup is pretty-printed, so a `<br />` is followed by a real
        # newline and a tab. Carried through verbatim that tab starts the next
        # markdown line at column four, which CommonMark reads as an indented
        # code block, and the newline doubles the one `<br>` already emitted,
        # splitting the paragraph. A newline inside a text node is only
        # whitespace in HTML, so collapse each such run to a single space.
        return re.sub(r"[ \t]*(?:\r\n|\r|\n)[ \t]*", " ", str(node))
    if not isinstance(node, Tag):
        return ""

    name = node.name

    if name == "br":
        # A plain newline is enough: `render_markdown` runs cmark with
        # CMARK_OPT_HARDBREAKS, so every newline is a hard break. The
        # backslash-newline form CommonMark also accepts can't end a block --
        # `<p>Bibliography:<br></p>` would leave the backslash visible -- and
        # GFM's autolinker swallows one that follows a bare URL.
        return "\n"

    if name in _UNWRAP_TAGS:
        return _render_children(node)

    if name in _FLAG_TAGS:
        return str(node)

    if name in ("b", "strong"):
        return _emphasise(node, "**", "**")

    if name in ("i", "em"):
        return _emphasise(node, "*", "*")

    if name == "span":
        if "italic" in (node.get("style") or ""):
            return _emphasise(node, "*", "*")
        return _render_children(node)

    if name == "a":
        href = node.get("href") or ""
        inner = _render_children(node).strip()
        if not href:
            return inner
        return f"[{inner}]({href})" if inner else href

    if name and re.fullmatch(r"h[1-6]", name):
        level = int(name[1])
        inner = _render_children(node).strip()
        return f"\n\n{'#' * level} {inner}\n\n" if inner else ""

    if name in ("p", "div"):
        inner = _render_children(node).strip()
        return f"\n\n{inner}\n\n" if inner else ""

    if name == "blockquote":
        inner = _render_children(node).strip()
        if not inner:
            return ""
        quoted = "\n".join(f"> {line}" for line in inner.splitlines())
        return f"\n\n{quoted}\n\n"

    if name in ("ul", "ol"):
        # Real-world data sometimes has stray content as a direct child of
        # <ul>/<ol> before any <li> (invalid HTML, but present in legacy
        # descriptions -- e.g. a <b>label:</b> immediately inside a <ul>).
        # Walk all direct children in document order so nothing is silently
        # dropped, rather than only extracting <li> elements.
        lines = []
        index = 1
        for child in node.children:
            if isinstance(child, Tag) and child.name == "li":
                text = _render_children(child).strip()
                if text:
                    prefix = f"{index}. " if name == "ol" else "* "
                    # Indent continuation lines to the item's content column
                    # instead of collapsing them onto one line. Collapsing threw
                    # away the line break from a <br> and left its backslash
                    # sitting in the visible text.
                    item_lines = text.split("\n")
                    lines.append(prefix + item_lines[0])
                    lines.extend(" " * len(prefix) + line for line in item_lines[1:])
                    index += 1
            else:
                stray = _render(child).strip()
                if stray:
                    lines.append(stray)
        return f"\n\n{chr(10).join(lines)}\n\n" if lines else ""

    if name == "img":
        src = node.get("src") or ""
        alt = (node.get("alt") or "").strip()
        # No src: nothing to point at, so fall through to the void-element
        # handling below and get the source flagged for manual review rather
        # than emitting a broken image.
        if src:
            return f"![{alt}]({src})"
        return str(node)

    if name == "hr":
        return "\n\n---\n\n"

    if name == "table":
        # GFM sizes a table by its header row and silently truncates every later
        # row to that width. Legacy tables often open with a spanning title cell
        # (`<td colspan="5">`), which would make the header one column wide and
        # throw away four fifths of the table. Expand each colspan into that many
        # columns and pad every row to the widest one so no cell is dropped.
        parsed_rows = []
        for tr in node.find_all("tr"):
            cells = []
            for cell in tr.find_all(["td", "th"], recursive=False):
                text = (
                    _render_children(cell)
                    .strip()
                    .replace("\n", " ")
                    .replace("|", "\\|")
                )
                try:
                    span = max(1, int(cell.get("colspan") or 1))
                except ValueError:
                    span = 1
                cells.append(text)
                cells.extend("" for _ in range(span - 1))
            if cells:
                parsed_rows.append(cells)
        if not parsed_rows:
            return ""
        width = max(len(cells) for cells in parsed_rows)
        md_rows = []
        for i, cells in enumerate(parsed_rows):
            padded = cells + [""] * (width - len(cells))
            md_rows.append("| " + " | ".join(padded) + " |")
            if i == 0:
                md_rows.append("| " + " | ".join(["---"] * width) + " |")
        return f"\n\n{chr(10).join(md_rows)}\n\n"

    # Unknown tag: unwrap, keeping its text content. A void element (no
    # children, no text -- e.g. <input>, <embed>) would unwrap to nothing and
    # vanish silently, so emit its raw markup instead: `contains_html_tags`
    # then sees it in the output and the caller flags the field for manual
    # review rather than writing a lossy conversion.
    rendered = _render_children(node)
    if not rendered and not node.find(True):
        return str(node)
    return rendered


def html_to_markdown(value: str) -> str:
    """
    Best-effort conversion of `value` (assumed to contain raw HTML) to
    markdown. Callers should check the *output* with `contains_html_tags`
    (helper_tags.py) -- some inputs (deeply malformed markup, tags not
    handled above) may leave residual HTML that needs manual review.
    """
    soup = BeautifulSoup(value, "lxml")
    root = soup.body or soup
    markdown = _render_children(root)
    markdown = re.sub(r"[ \t]+\n", "\n", markdown)
    markdown = re.sub(r"\n{3,}", "\n\n", markdown)
    return markdown.strip()
