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


def _render_children(node) -> str:
    return "".join(_render(child) for child in node.children)


def _render(node) -> str:
    if isinstance(node, NavigableString):
        return str(node)
    if not isinstance(node, Tag):
        return ""

    name = node.name

    if name == "br":
        # A single "\n" is a CommonMark *soft* break (rendered as just a
        # space) -- that silently collapsed multi-line content like a list
        # of date corrections onto one run-on line. Use a backslash-newline,
        # a CommonMark *hard* break, to actually preserve the line break.
        return "\\\n"

    if name in _UNWRAP_TAGS:
        return _render_children(node)

    if name in ("b", "strong"):
        inner = _render_children(node).strip()
        return f"**{inner}**" if inner else ""

    if name in ("i", "em"):
        inner = _render_children(node).strip()
        return f"_{inner}_" if inner else ""

    if name == "span":
        inner = _render_children(node)
        if "italic" in (node.get("style") or ""):
            stripped = inner.strip()
            return f"_{stripped}_" if stripped else ""
        return inner

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
                text = " ".join(text.split("\n"))
                if text:
                    prefix = f"{index}. " if name == "ol" else "* "
                    lines.append(prefix + text)
                    index += 1
            else:
                stray = _render(child).strip()
                if stray:
                    lines.append(stray)
        return f"\n\n{chr(10).join(lines)}\n\n" if lines else ""

    if name == "table":
        rows = node.find_all("tr")
        md_rows = []
        for i, tr in enumerate(rows):
            cells = tr.find_all(["td", "th"], recursive=False)
            cell_texts = [
                _render_children(cell).strip().replace("\n", " ").replace("|", "\\|")
                for cell in cells
            ]
            if not cell_texts:
                continue
            md_rows.append("| " + " | ".join(cell_texts) + " |")
            if i == 0:
                md_rows.append("| " + " | ".join(["---"] * len(cell_texts)) + " |")
        return f"\n\n{chr(10).join(md_rows)}\n\n" if md_rows else ""

    # Unknown tag: unwrap, keeping its text content.
    return _render_children(node)


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
