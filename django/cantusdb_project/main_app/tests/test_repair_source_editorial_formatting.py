"""Tests for the bounded radiocarbon and Ridgefield data repair."""

from io import StringIO
from unittest import mock

from bs4 import BeautifulSoup
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from reversion.models import Revision, Version

from main_app.html_to_markdown import html_to_markdown
from main_app.markdown import render_markdown
from main_app.models import Source
from main_app.tests.make_fakes import make_fake_source

# Passages from the 2026-10-28 production snapshot and 2026-11-09 staging GETs.
DESCRIPTION = "Radiocarbon dating (Nelson, 14C Results [see below])."
BIBLIOGRAPHY = (
    "Nelson, Andrew. *14C Results for M1250 [sic] from External Lab UCIAMS-228787*. "
    "14C Laboratoire de Radiochronologie."
)
RIDGEFIELD = (
    "The fragments from the Ridgefield Project are:\n"
    "[Group G (Antiphoner):](https://fragmentarium.ms/view/page/F-k0iy)"
    "https://cantusdatabase.org/source/1000027\n\nLater editorial notes."
)
RIDGEFIELD_HTML = (
    '<a href="https://fragmentarium.ms/view/page/F-k0iy"> Group G (Antiphoner):  '
    "<i></a>https://cantusdatabase.org/source/1000027 </i>"
)


class RepairSourceEditorialFormattingTests(TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        cls.radiocarbon = make_fake_source(
            id=123619,
            description=DESCRIPTION,
            selected_bibliography=BIBLIOGRAPHY,
            description_html_legacy=DESCRIPTION.replace("14C", "<sup>14</sup>C"),
            selected_bibliography_html_legacy="Original bibliography backup",
        )
        cls.ridgefield = make_fake_source(
            id=714555,
            description=RIDGEFIELD,
            description_html_legacy=RIDGEFIELD_HTML,
        )

    def run_repair(self, apply: bool = False) -> str:
        output = StringIO()
        call_command("repair_source_editorial_formatting", apply=apply, stdout=output)
        return output.getvalue()

    def test_dry_run_shows_exact_changes_without_changing_data_or_history(self) -> None:
        before = list(Source.objects.order_by("pk").values())
        output = self.run_repair()
        self.assertIn("-Radiocarbon dating (Nelson, 14C Results [see below]).", output)
        self.assertIn("+Radiocarbon dating (Nelson, ¹⁴C Results [see below]).", output)
        self.assertIn("Would update 2 source(s).", output)
        self.assertEqual(list(Source.objects.order_by("pk").values()), before)
        self.assertFalse(Revision.objects.exists())

    def test_repairs_rendered_values_and_preserves_other_fields_and_backups(
        self,
    ) -> None:
        unrelated = make_fake_source(description=DESCRIPTION)
        # An edit made after the original conversion must not be lost to a backup.
        Source.objects.filter(pk=123619).update(
            description=DESCRIPTION + " Additional editorial text.",
        )
        before = {s.pk: s for s in Source.objects.all()}
        self.assertIn("Updated 2 source(s).", self.run_repair(apply=True))
        for source in Source.objects.all():
            previous = before[source.pk]
            changed_fields = (
                {"description", "selected_bibliography"}
                if source.pk == 123619
                else {"description"} if source.pk == 714555 else set()
            )
            for field in source._meta.concrete_fields:
                if field.name not in changed_fields:
                    self.assertEqual(
                        getattr(source, field.attname),
                        getattr(previous, field.attname),
                        field.name,
                    )
        self.radiocarbon.refresh_from_db()
        self.ridgefield.refresh_from_db()
        self.assertEqual(
            self.radiocarbon.description,
            "Radiocarbon dating (Nelson, ¹⁴C Results [see below]). Additional editorial text.",
        )
        bibliography = render_markdown(self.radiocarbon.selected_bibliography)
        self.assertEqual(bibliography.count("¹⁴C"), 2)
        self.assertNotIn("14C", bibliography)
        soup = BeautifulSoup(
            render_markdown(self.ridgefield.description), "html.parser"
        )
        link = soup.find("a", href="https://cantusdatabase.org/source/1000027")
        self.assertIsNotNone(link.find_parent("em"))
        self.assertIn(
            "Group G (Antiphoner): https://cantusdatabase.org/source/1000027",
            soup.get_text(),
        )
        self.assertIn("Later editorial notes.", soup.get_text())
        unrelated.refresh_from_db()
        self.assertEqual(unrelated.description, DESCRIPTION)

    def test_original_html_repairs_survive_later_conversion_and_reruns(self) -> None:
        Source.objects.filter(pk=123619).update(
            description=DESCRIPTION.replace("14C", "<sup>14</sup>C"),
            selected_bibliography=BIBLIOGRAPHY.replace("14C", "<sup>14</sup>C"),
            description_html_legacy=None,
            selected_bibliography_html_legacy=None,
        )
        Source.objects.filter(pk=714555).update(
            description=RIDGEFIELD_HTML, description_html_legacy=None
        )
        self.run_repair(apply=True)
        self.assertIn("Updated 0 source(s).", self.run_repair(apply=True))
        for source in Source.objects.all():
            changes = {"description": html_to_markdown(source.description)}
            if source.pk == 123619:
                changes["selected_bibliography"] = html_to_markdown(
                    source.selected_bibliography
                )
            Source.objects.filter(pk=source.pk).update(**changes)
        self.assertIn("Updated 0 source(s).", self.run_repair(apply=True))
        self.radiocarbon.refresh_from_db()
        self.ridgefield.refresh_from_db()
        self.assertIn(
            "¹⁴C Results [see below]", render_markdown(self.radiocarbon.description)
        )
        self.assertEqual(
            render_markdown(self.radiocarbon.selected_bibliography).count("¹⁴C"), 2
        )
        soup = BeautifulSoup(
            render_markdown(self.ridgefield.description), "html.parser"
        )
        self.assertIsNotNone(
            soup.find(
                "a", href="https://cantusdatabase.org/source/1000027"
            ).find_parent("em")
        )

    def test_rerun_keeps_history_unchanged_and_before_revision_restores_fields(
        self,
    ) -> None:
        self.run_repair(apply=True)
        self.assertEqual(Revision.objects.count(), 2)
        versions = Version.objects.get_for_object(self.radiocarbon)
        self.assertEqual(versions.count(), 2)
        self.assertEqual(versions.last().field_dict["description"], DESCRIPTION)
        self.assertEqual(
            versions.first().field_dict["description"],
            DESCRIPTION.replace("14C", "¹⁴C"),
        )
        self.assertIn("Updated 0 source(s).", self.run_repair(apply=True))
        self.assertEqual(Revision.objects.count(), 2)
        versions.last().revision.revert()
        self.radiocarbon.refresh_from_db()
        self.ridgefield.refresh_from_db()
        self.assertEqual(self.radiocarbon.description, DESCRIPTION)
        self.assertEqual(self.radiocarbon.selected_bibliography, BIBLIOGRAPHY)
        self.assertEqual(self.ridgefield.description, RIDGEFIELD)

    def test_partially_corrected_bibliography_keeps_existing_superscript(self) -> None:
        Source.objects.filter(pk=123619).update(
            selected_bibliography=BIBLIOGRAPHY.replace("14C Results", "¹⁴C Results")
        )
        self.run_repair(apply=True)
        self.radiocarbon.refresh_from_db()
        self.assertEqual(self.radiocarbon.selected_bibliography.count("¹⁴C"), 2)

    def test_unknown_or_duplicate_passage_aborts_all_changes(self) -> None:
        for value in ("Changed Group G wording", RIDGEFIELD + RIDGEFIELD, None):
            with self.subTest(value=value):
                Source.objects.filter(pk=714555).update(description=value)
                before = list(Source.objects.order_by("pk").values())
                with self.assertRaisesMessage(CommandError, "No changes applied"):
                    self.run_repair(apply=True)
                self.assertEqual(list(Source.objects.order_by("pk").values()), before)
                self.assertFalse(Revision.objects.exists())

    def test_missing_source_aborts_without_changes(self) -> None:
        self.ridgefield.delete()
        with self.assertRaisesMessage(CommandError, "Both sources"):
            self.run_repair(apply=True)
        self.radiocarbon.refresh_from_db()
        self.assertEqual(self.radiocarbon.description, DESCRIPTION)
        self.assertFalse(Revision.objects.exists())

    def test_failure_during_update_rolls_back_both_fields_and_history(self) -> None:
        from main_app.management.commands import repair_source_editorial_formatting

        before = list(Source.objects.order_by("pk").values())
        original_filter = Source.objects.filter

        def fail_second_update(*args, **kwargs):
            queryset = original_filter(*args, **kwargs)
            if kwargs == {"pk": 714555}:
                queryset.update = mock.Mock(side_effect=RuntimeError("test failure"))
            return queryset

        with mock.patch.object(
            repair_source_editorial_formatting.Source.objects,
            "filter",
            side_effect=fail_second_update,
        ):
            with self.assertRaisesMessage(RuntimeError, "test failure"):
                self.run_repair(apply=True)
        self.assertEqual(list(Source.objects.order_by("pk").values()), before)
        self.assertFalse(Revision.objects.exists())
