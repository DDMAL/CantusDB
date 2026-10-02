from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from main_app.tests.make_fakes import make_fake_chant, make_fake_source

FLAGS = [
    "volpiano_proofread",
    "manuscript_full_text_proofread",
    "manuscript_full_text_std_proofread",
]


def run_backfill(*args: str) -> str:
    out = StringIO()
    call_command("backfill_proofread_flags", *args, stdout=out)
    return out.getvalue()


class TestBackfillProofreadFlags(TestCase):
    def assert_flags(self, chant, expected) -> None:
        chant.refresh_from_db()
        for flag in FLAGS:
            self.assertEqual(getattr(chant, flag), expected, flag)

    def test_ticks_fields_with_content_in_published_sources(self):
        chant = make_fake_chant(source=make_fake_source(published=True))
        run_backfill()
        self.assert_flags(chant, True)

    def test_ticks_flags_that_were_never_set(self):
        chant = make_fake_chant(
            source=make_fake_source(published=True),
            volpiano_proofread=None,
            manuscript_full_text_proofread=None,
            manuscript_full_text_std_proofread=None,
        )
        run_backfill()
        self.assert_flags(chant, True)

    def test_skips_unpublished_sources(self):
        chant = make_fake_chant(source=make_fake_source(published=False))
        run_backfill()
        self.assert_flags(chant, False)

    def test_skips_empty_fields(self):
        source = make_fake_source(published=True)
        empty = make_fake_chant(
            source=source,
            volpiano="",
            manuscript_full_text="",
            manuscript_full_text_std_spelling="",
        )
        missing = make_fake_chant(
            source=source,
            volpiano=None,
            manuscript_full_text=None,
            manuscript_full_text_std_spelling=None,
        )
        run_backfill()
        self.assert_flags(empty, False)
        self.assert_flags(missing, False)

    def test_skips_excluded_sources(self):
        excluded = make_fake_chant(source=make_fake_source(published=True))
        included = make_fake_chant(source=make_fake_source(published=True))
        run_backfill("--exclude", str(excluded.source_id))
        self.assert_flags(excluded, False)
        self.assert_flags(included, True)

    def test_dry_run_reports_without_writing(self):
        chant = make_fake_chant(source=make_fake_source(published=True))
        output = run_backfill("--dry-run")
        self.assertIn(f"{chant.source_id}\t1\t1\t1", output)
        self.assertIn("Total\t1\t1\t1", output)
        self.assert_flags(chant, False)
