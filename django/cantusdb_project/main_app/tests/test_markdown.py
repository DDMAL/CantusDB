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
