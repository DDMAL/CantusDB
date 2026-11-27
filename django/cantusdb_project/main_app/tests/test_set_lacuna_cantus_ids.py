import csv
import os
import tempfile
from io import StringIO

from django.conf import settings
from django.core.management import call_command
from django.test import TestCase
from reversion.models import Version

from main_app.models import Chant, Source
from main_app.tests.make_fakes import make_fake_chant, make_fake_feast


class SetLacunaCantusIdsTest(TestCase):
    def setUp(self):
        self.lacuna_feast = make_fake_feast(name="[Lacuna]")

    def lacuna(self, **kwargs):
        defaults = {
            "incipit": "LACUNA",
            "manuscript_full_text_std_spelling": "LACUNA",
            "manuscript_full_text": "LACUNA",
            "cantus_id": None,
            "feast": self.lacuna_feast,
        }
        return make_fake_chant(**{**defaults, **kwargs})

    def run_audit(self, *args):
        """A dry run: the report only."""
        return self.run_command("--dry-run", *args)

    def run_command(self, *args):
        out = StringIO()
        call_command("set_lacuna_cantus_ids", *args, stdout=out)
        return out.getvalue()

    def test_sorts_chants_by_what_the_rule_does(self):
        placeholder = self.lacuna()
        blank_string = self.lacuna(cantus_id="")
        lowercase = self.lacuna(cantus_id="lacuna")
        real_id = self.lacuna(cantus_id="g00760")
        other_spelling = make_fake_chant(incipit="Lacuna", cantus_id=None)
        real_chant = make_fake_chant(
            incipit="Ave maria", cantus_id="001234", feast=self.lacuna_feast
        )

        output = self.run_audit()

        self.assertIn("set to LACUNA: 2 chant(s)", output)
        self.assertIn(f"chant {lowercase.id} ", output)
        self.assertIn("change case to LACUNA: 1 chant(s)", output)
        self.assertIn(f"chant {real_id.id} ", output)
        self.assertIn("text is LACUNA but Cantus ID is g00760", output)
        self.assertIn(f"chant {other_spelling.id} ", output)
        self.assertIn("leave: real chant in the [Lacuna] feast: 1 chant(s)", output)
        self.assertIn("3 chant(s) would get the Cantus ID LACUNA", output)
        for chant, cantus_id in [
            (placeholder, None),
            (blank_string, ""),
            (lowercase, "lacuna"),
            (real_chant, "001234"),
        ]:
            chant.refresh_from_db()
            self.assertEqual(chant.cantus_id, cantus_id, "nothing is changed")

    def test_dry_run_lists_every_chant_that_would_change(self):
        plain = self.lacuna()
        odd = self.lacuna(manuscript_full_text="Exaltare dominum")
        output = self.run_audit()
        self.assertIn(f"chant {plain.id} in", output)
        self.assertNotIn(f"check: chant {plain.id} ", output)
        self.assertIn(f"check: chant {odd.id} in", output)

    def test_a_latin_sentence_using_the_word_is_left_alone(self):
        make_fake_chant(incipit="Ecce lacuna maris", cantus_id=None)
        output = self.run_audit()
        self.assertNotIn("set to LACUNA", output)
        self.assertIn("leave: not exactly LACUNA: 1 chant(s)", output)

    def test_flags_a_placeholder_whose_manuscript_text_differs(self):
        chant = self.lacuna(manuscript_full_text="Exaltare dominum")
        output = self.run_audit()
        self.assertIn(f"check: chant {chant.id} in", output)
        self.assertIn("manuscript text is 'Exaltare dominum', not LACUNA", output)

    def test_writes_a_csv_row_per_chant(self):
        chant = self.lacuna(folio="003v", c_sequence=2)
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "lacuna.csv")
            self.run_audit("--csv", path)
            with open(path, encoding="utf-8") as csv_file:
                rows = list(csv.DictReader(csv_file))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["id"], str(chant.id))
        self.assertEqual(rows[0]["action"], "set to LACUNA")
        self.assertEqual(rows[0]["folio"], "003v")

    def test_nothing_to_report(self):
        make_fake_chant(incipit="Ave maria")
        self.assertIn("0 chant(s) would get the Cantus ID LACUNA", self.run_audit())
        self.assertEqual(Chant.objects.filter(cantus_id="LACUNA").count(), 0)


class ApplyLacunaCantusIdsTest(TestCase):
    def setUp(self):
        self.lacuna_feast = make_fake_feast(name="[Lacuna]")

    def lacuna(self, **kwargs):
        defaults = {
            "incipit": "LACUNA",
            "manuscript_full_text": "LACUNA",
            "cantus_id": None,
            "feast": self.lacuna_feast,
        }
        return make_fake_chant(**{**defaults, **kwargs})

    def run_command(self, *args):
        out = StringIO()
        call_command("set_lacuna_cantus_ids", *args, stdout=out)
        return out.getvalue()

    def test_sets_lacuna_on_placeholders_only(self):
        placeholder = self.lacuna()
        lowercase = self.lacuna(cantus_id="lacuna")
        real_id = self.lacuna(cantus_id="g00760")
        other_spelling = make_fake_chant(incipit="Lacuna", cantus_id=None)
        real_chant = make_fake_chant(
            incipit="Ave maria", cantus_id="001234", feast=self.lacuna_feast
        )

        output = self.run_command()

        self.assertIn("Set the Cantus ID LACUNA on 2 chant(s).", output)
        for chant, expected in [
            (placeholder, "LACUNA"),
            (lowercase, "LACUNA"),
            (real_id, "g00760"),
            (other_spelling, None),
            (real_chant, "001234"),
        ]:
            chant.refresh_from_db()
            self.assertEqual(chant.cantus_id, expected)

    def test_dry_run_changes_nothing(self):
        chant = self.lacuna()
        self.run_command("--dry-run")
        chant.refresh_from_db()
        self.assertIsNone(chant.cantus_id)
        self.assertFalse(Version.objects.get_for_object(chant).exists())

    def test_each_chant_gets_its_own_before_and_after_revision(self):
        first, second = self.lacuna(), self.lacuna(cantus_id="lacuna")
        self.run_command()
        for chant, before in [(first, None), (second, "lacuna")]:
            versions = list(Version.objects.get_for_object(chant).order_by("pk"))
            self.assertEqual(len(versions), 2)
            self.assertEqual(versions[0].field_dict["cantus_id"], before)
            self.assertEqual(versions[1].field_dict["cantus_id"], "LACUNA")
            for version in versions:
                # a revision of its own, so restoring one chant reverts only it
                self.assertEqual(version.revision.version_set.count(), 1)
                self.assertIn("#2264", version.revision.comment)

    def test_leaves_last_modified_dates_alone(self):
        chant = self.lacuna()
        source_date = Source.objects.get(pk=chant.source_id).date_updated
        chant_date = Chant.objects.get(pk=chant.pk).date_updated
        self.run_command()
        self.assertEqual(
            Source.objects.get(pk=chant.source_id).date_updated, source_date
        )
        self.assertEqual(Chant.objects.get(pk=chant.pk).date_updated, chant_date)

    def test_lacuna_is_a_reserved_cantus_id(self):
        # so these chants don't show up as "not in Cantus Index"
        self.assertIn("LACUNA", settings.RESERVED_CANTUS_IDS)
