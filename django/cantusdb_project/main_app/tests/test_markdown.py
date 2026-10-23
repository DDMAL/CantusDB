from django.test import SimpleTestCase
from html.parser import HTMLParser

from main_app.markdown import render_markdown


class Elements(HTMLParser):
    def __init__(self, html: str) -> None:
        super().__init__()
        self.elements: list[tuple[str, dict[str, str | None]]] = []
        self.feed(html)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.elements.append((tag, dict(attrs)))


class MarkdownRenderingTest(SimpleTestCase):
    def test_legacy_html_keeps_authored_line_breaks(self) -> None:
        cases = [
            (
                "<p>Material: Parchment\nSource type: Antiphonal</p>",
                "Parchment<br>\nSource",
            ),
            ("<div>First\nSecond</div>", "First<br>\nSecond"),
            ("<center>First\nSecond</center>", "First<br>\nSecond"),
            ("<ul>First\nSecond<li>Item</li></ul>", "First<br>\nSecond"),
            ("<table><tr><td>First\nSecond</td></tr></table>", "First<br>\nSecond"),
            ("<p>First <i>title</i>\n<i>Second</i></p>", "</i><br>\n<i>Second"),
            ("> <p>First\n> Second</p>", "First<br>\nSecond"),
        ]
        for value, expected in cases:
            with self.subTest(value=value):
                self.assertIn(expected, render_markdown(value))

    def test_line_break_preservation_does_not_double_markdown_breaks(self) -> None:
        html = render_markdown("First *title*\nSecond\n\n<p>Legacy\ntext</p>")
        self.assertIn("<em>title</em><br>\nSecond", html)
        self.assertIn("Legacy<br>\ntext", html)
        self.assertEqual(html.count("<br>"), 2)

    def test_line_break_preservation_keeps_code_and_entities(self) -> None:
        html = render_markdown("<div><pre>First\nSecond</pre>&lt;safe&gt;</div>")
        self.assertIn("<pre>First\nSecond</pre>", html)
        self.assertIn("&lt;safe&gt;", html)
        self.assertNotIn("<br", html)

    def test_unclosed_legacy_block_does_not_double_later_markdown_breaks(self) -> None:
        html = render_markdown(
            "<p>Material: Parchment\n\nWritten in the 12th century\n200 folios"
        )
        self.assertIn("Written in the 12th century<br>\n200 folios", html)
        self.assertNotIn("<br><br>", html)
        self.assertEqual(html.count("<br>"), 2)
        self.assertNotIn("</p><br>", html)

    def test_legacy_ampersands_keep_their_authored_text(self) -> None:
        html = render_markdown("<p>Antiphonale &c. by R&D Press &amp; Co.</p>")
        self.assertIn("Antiphonale &amp;c. by R&amp;D Press &amp; Co.", html)
        self.assertNotIn("&amp;c;", html)

    def test_malformed_legacy_declaration_still_renders_and_is_sanitized(self) -> None:
        html = render_markdown(
            '<div>Before<![foo]>After<img src="x" onerror="alert(1)"></div>'
        )
        self.assertIn("Before", html)
        self.assertIn("After", html)
        self.assertNotIn("onerror", html)

    def test_authored_numbers_in_nested_and_quoted_lists(self) -> None:
        cases = [
            ("1. First\n4. Fourth\n9. Ninth", [1, 4, 9]),
            ("> 3. Third\n> 7. Seventh", [3, 7]),
            ("- Outer\n\n  3. Third\n  7. Seventh", [3, 7]),
            ("1. First\r\n4. Fourth\r\n9. Ninth", [1, 4, 9]),
            ("1. First\n1. Another first", [1, 1]),
        ]
        for markdown, numbers in cases:
            with self.subTest(markdown=markdown):
                html = render_markdown(markdown)
                for number in numbers:
                    self.assertIn(f'<li value="{number}">', html)
                self.assertEqual(html.count('<li value="'), len(numbers))
                self.assertNotIn("data-sourcepos", html)

    def test_numbered_text_in_code_is_not_a_list(self) -> None:
        html = render_markdown("```\n1. First\n4. Fourth\n```")
        self.assertIn("1. First\n4. Fourth", html)
        self.assertNotIn("<li", html)

    def test_existing_html_list_keeps_its_numbers(self) -> None:
        html = render_markdown('<ol start="4"><li value="9">Ninth</li></ol>')
        self.assertIn('<ol start="4">', html)
        self.assertIn('<li value="9">Ninth</li>', html)

    def test_removes_executable_html_and_unsafe_links(self) -> None:
        cases = [
            '<img src="x" onerror="alert(1)">',
            '<svg onload="alert(1)"><a href="javascript:alert(1)">link</a></svg>',
            '<a href="java&#x73;cript:alert(1)" onclick="alert(2)">link</a>',
            '<a href="java&#10;script:alert(1)">link</a>',
            "[link](javascript:alert%281%29)",
            '<img src="data:image/svg+xml,evil">',
            '<iframe srcdoc="<script>alert(1)</script>"></iframe>',
            '<object data="javascript:alert(1)">text</object>',
            '<p style="position:fixed" onmouseover="alert(1)">text</p>',
            "<script>alert(1)</script>",
        ]
        for markdown in cases:
            with self.subTest(markdown=markdown):
                for tag, attrs in Elements(render_markdown(markdown)).elements:
                    self.assertNotIn(
                        tag, {"script", "svg", "iframe", "object", "embed"}
                    )
                    for name, value in attrs.items():
                        self.assertFalse(name.startswith("on"))
                        self.assertNotEqual(name, "style")
                        if name in {"href", "src"}:
                            self.assertFalse(value.startswith(("javascript:", "data:")))

    def test_preserves_useful_markdown_and_legacy_html(self) -> None:
        html = render_markdown(
            "**bold** and *italic*\nsecond line\n\n"
            '<table><tr><td colspan="2">A <i>legacy</i> citation '
            '<a href="https://example.com">link</a></td></tr></table>'
        )
        self.assertIn("<strong>bold</strong>", html)
        self.assertIn("<em>italic</em>", html)
        self.assertIn("<br>", html)
        self.assertIn('<td colspan="2">', html)
        self.assertIn("<i>legacy</i>", html)
        self.assertIn('href="https://example.com"', html)
