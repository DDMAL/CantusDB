from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from main_app.html_to_markdown import html_to_markdown
from main_app.models import Source
from main_app.templatetags.helper_tags import contains_html_tags, render_markdown
from main_app.tests.make_fakes import make_fake_source


def convert(*args):
    """Runs the command with stdout captured, returning what it printed."""
    out = StringIO()
    call_command("convert_html_to_markdown", *args, stdout=out)
    return out.getvalue()


class TestHtmlToMarkdown(TestCase):
    """Unit tests for the converter itself, per tag family."""

    def test_inline_emphasis(self):
        self.assertEqual(html_to_markdown("<p><b>Bold</b></p>"), "**Bold**")
        self.assertEqual(html_to_markdown("<p><strong>Bold</strong></p>"), "**Bold**")
        self.assertEqual(html_to_markdown("<p><i>Ital</i></p>"), "*Ital*")
        self.assertEqual(html_to_markdown("<p><em>Ital</em></p>"), "*Ital*")

    def test_italic_span(self):
        self.assertEqual(
            html_to_markdown('<p><span style="font-style: italic;">Ital</span></p>'),
            "*Ital*",
        )
        # A span with any other styling is just unwrapped.
        self.assertEqual(
            html_to_markdown('<p><span style="color: red;">Plain</span></p>'), "Plain"
        )

    def test_link(self):
        self.assertEqual(
            html_to_markdown('<a href="https://example.com">Text</a>'),
            "[Text](https://example.com)",
        )
        # No inner text: keep the bare URL rather than emitting an empty label.
        self.assertEqual(
            html_to_markdown('<a href="https://example.com"></a>'),
            "https://example.com",
        )
        # No href: keep the text rather than emitting a broken link.
        self.assertEqual(html_to_markdown("<a>Text</a>"), "Text")

    def test_headings(self):
        self.assertEqual(html_to_markdown("<h1>One</h1>"), "# One")
        self.assertEqual(html_to_markdown("<h3>Three</h3>"), "### Three")

    def test_blockquote(self):
        self.assertEqual(html_to_markdown("<blockquote>Cited</blockquote>"), "> Cited")

    def test_paragraphs_are_separated_by_blank_lines(self):
        self.assertEqual(html_to_markdown("<p>One</p><p>Two</p>"), "One\n\nTwo")

    def test_br_becomes_a_hard_break(self):
        # `render_markdown` runs cmark with CMARK_OPT_HARDBREAKS, so a plain
        # newline is already a hard break -- no backslash needed.
        markdown = html_to_markdown("<p>Line one<br>Line two</p>")
        self.assertEqual(markdown, "Line one\nLine two")
        self.assertIn("<br", render_markdown(markdown))

    def test_trailing_br_leaves_no_visible_backslash(self):
        # CommonMark can't end a block with a hard break, so the old
        # backslash-newline form left a stray "\" on the page (#1219).
        markdown = html_to_markdown("<p>Bibliography:<br></p>")
        self.assertEqual(markdown, "Bibliography:")
        self.assertNotIn("\\", render_markdown(markdown))

    def test_repeated_trailing_br_before_a_table(self):
        # The #1219 shape: <br>s padding the end of a block push the table down
        # the page and leave a backslash behind.
        markdown = html_to_markdown(
            "<p>Contents:<br><br><br></p><table><tr><td>A</td></tr></table>"
        )
        self.assertTrue(markdown.startswith("Contents:\n\n|"), markdown)
        self.assertNotIn("\\", render_markdown(markdown))

    def test_br_between_blocks_is_not_a_stray_backslash(self):
        markdown = html_to_markdown("<p>One</p>\n<br>\n<p>Two</p>")
        self.assertEqual(markdown, "One\n\nTwo")

    def test_emphasis_keeps_the_space_that_sat_inside_the_tag(self):
        # `<em>Antiphonale </em>(1934)` used to be stripped to
        # `_Antiphonale_(1934)`, losing the space (#1957).
        self.assertEqual(
            html_to_markdown("<p><em>Antiphonale </em>(1934)</p>"),
            "*Antiphonale* (1934)",
        )
        self.assertEqual(html_to_markdown("<p><b>Note </b>added</p>"), "**Note** added")

    def test_italics_survive_next_to_a_word(self):
        # `<i>AH</i>but` has no space to move out, and `_` can't close inside a
        # word -- it would render as literal underscores. `*` can.
        markdown = html_to_markdown("<p><i>AH</i>but</p>")
        self.assertEqual(markdown, "*AH*but")
        self.assertIn("<em>AH</em>but", render_markdown(markdown))

    def test_italic_span_next_to_a_word(self):
        markdown = html_to_markdown(
            '<p><span style="font-style: italic;">Kyrie </span>eleison</p>'
        )
        self.assertEqual(markdown, "*Kyrie* eleison")
        self.assertNotIn("_", render_markdown(markdown))

    def test_pretty_printed_indent_does_not_become_a_code_block(self):
        # Legacy markup wraps lines as "<br />\r\n\t", and that tab would start
        # the next markdown line at column four -- an indented code block.
        markdown = html_to_markdown("<p>One<br />\r\n\tTwo</p>")
        self.assertNotRegex(markdown, r"^[ \t]{4,}", "indent survived")
        self.assertNotIn("<pre>", render_markdown(markdown))

    def test_colspan_title_row_does_not_truncate_the_table(self):
        # A spanning title cell would otherwise make the header one column wide,
        # and GFM silently truncates every later row to the header's width.
        markdown = html_to_markdown(
            "<table>"
            '<tr><td colspan="3">Title</td></tr>'
            "<tr><td>a</td><td>b</td><td>c</td></tr>"
            "</table>"
        )
        self.assertEqual(
            markdown,
            "| Title |  |  |\n| --- | --- | --- |\n| a | b | c |",
        )
        rendered = render_markdown(markdown)
        for cell in ("Title", "a", "b", "c"):
            self.assertIn(f">{cell}<", rendered)

    def test_unordered_list(self):
        self.assertEqual(
            html_to_markdown("<ul><li>One</li><li>Two</li></ul>"), "* One\n* Two"
        )

    def test_ordered_list_is_numbered(self):
        self.assertEqual(
            html_to_markdown("<ol><li>One</li><li>Two</li></ol>"), "1. One\n2. Two"
        )

    def test_br_inside_list_item_keeps_the_hard_break(self):
        # Continuation lines are indented to the item's content column so the
        # break survives; collapsing them onto one line used to drop the break
        # and leave the backslash visible in the rendered text.
        markdown = html_to_markdown("<ul><li>Line one<br>Line two</li></ul>")
        self.assertEqual(markdown, "* Line one\n  Line two")
        html = render_markdown(markdown)
        self.assertIn("<br", html)
        self.assertNotIn("\\", html)

    def test_br_inside_ordered_list_item_keeps_the_hard_break(self):
        markdown = html_to_markdown("<ol><li>Line one<br>Line two</li></ol>")
        self.assertEqual(markdown, "1. Line one\n   Line two")
        html = render_markdown(markdown)
        self.assertIn("<br", html)
        self.assertNotIn("\\", html)

    def test_list_keeps_stray_children(self):
        # Invalid HTML, but present in the legacy data: content sitting directly
        # inside <ul> before any <li>. It must not be silently dropped.
        self.assertEqual(
            html_to_markdown("<ul><b>Label:</b><li>One</li></ul>"),
            "**Label:**\n* One",
        )

    def test_table_becomes_a_pipe_table(self):
        self.assertEqual(
            html_to_markdown(
                "<table><tr><td>A</td><td>B</td></tr>"
                "<tr><td>C</td><td>D</td></tr></table>"
            ),
            "| A | B |\n| --- | --- |\n| C | D |",
        )

    def test_table_cell_pipes_are_escaped(self):
        self.assertIn(r"A \| B", html_to_markdown("<table><tr><td>A | B</td></tr>"))

    def test_styling_only_tags_are_unwrapped(self):
        # Markdown has no equivalent, so styling is dropped but text is kept.
        self.assertEqual(
            html_to_markdown("<p><font color='red'><u>Text</u></font></p>"), "Text"
        )

    def test_image_becomes_a_markdown_image(self):
        self.assertEqual(
            html_to_markdown('<img src="plate.png" alt="Plate 1">'),
            "![Plate 1](plate.png)",
        )
        self.assertEqual(html_to_markdown('<img src="plate.png">'), "![](plate.png)")

    def test_horizontal_rule(self):
        self.assertEqual(
            html_to_markdown("<p>One</p><hr><p>Two</p>"), "One\n\n---\n\nTwo"
        )

    def test_unknown_tag_is_unwrapped(self):
        self.assertEqual(html_to_markdown("<p><marquee>Text</marquee></p>"), "Text")

    def test_void_element_is_not_silently_dropped(self):
        # An unknown void element has no children, so unwrapping it would erase
        # it without trace. It must survive as raw markup so the caller's
        # `contains_html_tags` check flags the field for manual review.
        markdown = html_to_markdown('<p>Text <input type="text"> more</p>')
        self.assertTrue(contains_html_tags(markdown))
        self.assertIn("input", markdown)

    def test_embedded_media_is_flagged(self):
        # No markdown equivalent -- unwrapping would discard what they point
        # at, so they have to surface for manual review. <embed> in particular
        # is not treated as void by lxml (it swallows the following text as a
        # child), so the void-element guard alone would not catch it.
        for html in (
            '<p>Text <embed src="x.swf"> more</p>',
            '<p>Text <iframe src="x"></iframe> more</p>',
            '<p>Text <video src="x"></video> more</p>',
        ):
            with self.subTest(html=html):
                markdown = html_to_markdown(html)
                self.assertTrue(contains_html_tags(markdown))
                self.assertIn("more", markdown)

    def test_image_without_src_is_flagged_rather_than_emitted(self):
        markdown = html_to_markdown("<p>Text <img alt='broken'> more</p>")
        self.assertTrue(contains_html_tags(markdown))

    def test_output_has_no_runs_of_blank_lines(self):
        self.assertEqual(
            html_to_markdown("<p>One</p><div></div><p>Two</p>"), "One\n\nTwo"
        )


class TestMarkdownTemplateFilters(TestCase):
    def test_contains_html_tags(self):
        self.assertTrue(contains_html_tags("<p>Text</p>"))
        self.assertTrue(contains_html_tags("Text with a <br> in it"))
        self.assertFalse(contains_html_tags("**Markdown** only"))
        self.assertFalse(contains_html_tags(""))

    def test_autolinks_are_not_treated_as_html(self):
        # CommonMark autolinks are markdown, not raw HTML. Misreading them sent
        # the whole field down the legacy `safe|linebreaks` branch, so the link
        # never rendered.
        self.assertFalse(contains_html_tags("<https://example.com>"))
        self.assertFalse(contains_html_tags("<user@example.com>"))
        self.assertFalse(contains_html_tags("See <https://example.com> for more"))
        self.assertIn("<a href", render_markdown("<https://example.com>"))

    def test_contains_html_tags_still_detects_real_tags(self):
        for value in (
            "<p>x</p>",
            "<br>",
            "<br />",
            "</p>",
            "<img src='x'/>",
            "<a href='https://example.com'>y</a>",
            "<o:p>word</o:p>",
            "< p >",
        ):
            with self.subTest(value=value):
                self.assertTrue(contains_html_tags(value))

    def test_render_markdown_drops_raw_html(self):
        # cmark runs in safe mode, so raw HTML blocks are dropped rather than
        # passed through -- these fields are editable by many indexer accounts.
        # Note this is block-level: a value built entirely of HTML blocks loses
        # its *text* too, which is why source_detail.html falls back to the
        # legacy rendering for values that still contain HTML.
        self.assertNotIn("Legacy text", render_markdown("<p>Legacy text</p>"))

    def test_render_markdown_renders_markdown(self):
        self.assertIn("<strong>Bold</strong>", render_markdown("**Bold**"))

    def test_single_newline_is_a_hard_break(self):
        # Most legacy descriptions are line-per-fact with no blank line between
        # them ("Material: Parchment", "Source type: Antiphonal", ...). Without
        # CMARK_OPT_HARDBREAKS a lone newline is a CommonMark *soft* break and
        # the whole field collapses into one run-on line.
        rendered = render_markdown("Material: Parchment\nSource type: Antiphonal")
        self.assertIn("<br", rendered)

    def test_authored_backslash_hard_break_still_works(self):
        # Existing content already uses the CommonMark backslash hard break;
        # hardbreaks mode must not leave the backslash visible.
        rendered = render_markdown("Line one\\\nLine two")
        self.assertIn("<br", rendered)
        self.assertNotIn("\\", rendered)

    def test_blank_line_still_starts_a_new_paragraph(self):
        rendered = render_markdown("Para one\n\nPara two")
        self.assertIn("<p>Para one</p>", rendered)
        self.assertIn("<p>Para two</p>", rendered)

    def test_hardbreaks_do_not_break_block_structure(self):
        self.assertIn("<li>", render_markdown("* one\n* two"))
        self.assertIn("<td>", render_markdown("| a |\n| --- |\n| 1 |"))

    def test_hardbreaks_mode_still_drops_raw_html(self):
        # Turning on hardbreaks must not turn off cmark's safe mode.
        self.assertNotIn("<script", render_markdown("<script>alert(1)</script>"))


class TestConvertHtmlToMarkdownCommand(TestCase):
    def setUp(self):
        self.html = "<p><b>Bold</b> description</p>"
        self.markdown = "**Bold** description"
        self.source = make_fake_source(
            description=self.html, selected_bibliography=self.html
        )

    def refresh(self):
        return Source.objects.get(id=self.source.id)

    def test_dry_run_writes_nothing(self):
        output = convert()
        self.assertIn("Dry run only", output)

        source = self.refresh()
        self.assertEqual(source.description, self.html)
        self.assertIsNone(source.description_html_legacy)

    def test_apply_converts_and_backs_up_both_fields(self):
        convert("--apply")

        source = self.refresh()
        self.assertEqual(source.description, self.markdown)
        self.assertEqual(source.description_html_legacy, self.html)
        self.assertEqual(source.selected_bibliography, self.markdown)
        self.assertEqual(source.selected_bibliography_html_legacy, self.html)

    def test_revert_restores_the_original_html(self):
        convert("--apply")
        convert("--revert", "--apply")

        source = self.refresh()
        self.assertEqual(source.description, self.html)
        self.assertIsNone(source.description_html_legacy)
        self.assertEqual(source.selected_bibliography, self.html)
        self.assertIsNone(source.selected_bibliography_html_legacy)

    def test_revert_dry_run_writes_nothing(self):
        convert("--apply")
        output = convert("--revert")

        self.assertIn("Dry run only", output)
        self.assertEqual(self.refresh().description, self.markdown)

    def test_rerunning_apply_does_not_clobber_the_backup(self):
        convert("--apply")
        output = convert("--apply")

        source = self.refresh()
        self.assertEqual(source.description, self.markdown)
        self.assertEqual(source.description_html_legacy, self.html)
        self.assertIn("already converted (skipped): 1", output)

    def test_force_reconverts_from_the_backup(self):
        convert("--apply")
        # Simulate the live field having drifted; --force must reconvert from the
        # backed-up HTML, not from whatever is in the live field now.
        Source.objects.filter(id=self.source.id).update(description="drifted")

        convert("--apply", "--force")

        source = self.refresh()
        self.assertEqual(source.description, self.markdown)
        self.assertEqual(source.description_html_legacy, self.html)

    def test_field_without_html_is_left_alone(self):
        source = make_fake_source(
            description="Already **markdown**", selected_bibliography=""
        )
        convert("--apply")

        source.refresh_from_db()
        self.assertEqual(source.description, "Already **markdown**")
        # Null has to keep meaning "never converted", so no backup is written.
        self.assertIsNone(source.description_html_legacy)

    def test_residual_html_is_reported_and_left_untouched(self):
        # <embed> is a void element the converter has no markdown equivalent
        # for, so it survives conversion and the field must not be written.
        source = make_fake_source(
            description='<p>Text <embed src="x.swf"> more</p>',
            selected_bibliography="",
        )
        output = convert("--apply")

        source.refresh_from_db()
        self.assertEqual(source.description, '<p>Text <embed src="x.swf"> more</p>')
        self.assertIsNone(source.description_html_legacy)
        self.assertIn("needs manual review", output)
        self.assertIn(f"id={source.id}", output)

    def test_source_id_limits_the_scope(self):
        other = make_fake_source(description=self.html, selected_bibliography="")
        convert("--apply", "--source-id", str(self.source.id))

        self.assertEqual(self.refresh().description, self.markdown)
        other.refresh_from_db()
        self.assertEqual(other.description, self.html)

    def test_unknown_source_id_is_an_error(self):
        with self.assertRaises(CommandError):
            convert("--apply", "--source-id", "123456789")

    def test_force_with_revert_is_an_error(self):
        with self.assertRaises(CommandError):
            convert("--revert", "--force")

    def test_conversion_does_not_bump_date_updated(self):
        # bulk_update skips save(), so auto_now does not fire -- a bulk data
        # conversion should not surface as an editorial edit.
        before = self.refresh().date_updated
        convert("--apply")
        self.assertEqual(self.refresh().date_updated, before)
