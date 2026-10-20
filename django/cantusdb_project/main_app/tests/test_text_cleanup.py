"""Observable storage, form, search and migration behavior for issue #1585."""

import importlib
import csv
import io
from unittest.mock import patch

from django.conf import settings
from django.apps.registry import Apps
from django.db import connection, IntegrityError, transaction
from django.db.migrations.executor import MigrationExecutor
from django.forms import modelform_factory
from django.test import TestCase, TransactionTestCase
from django.urls import reverse

from main_app.forms import ChantEditForm
from main_app.models import Chant, Sequence, Source, Segment

CHANT_FIELDS = (
    "manuscript_full_text",
    "manuscript_full_text_std_spelling",
    "manuscript_syllabized_full_text",
    "image_link",
    "indexing_notes",
    "volpiano",
    "volpiano_notes",
    "volpiano_intervals",
)
SOURCE_FIELDS = ("description", "selected_bibliography", "summary")


class TextNormalizationTest(TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        cls.source = Source.objects.create(shelfmark="Text cleanup", published=True)

    def test_missing_values_on_save(self) -> None:
        for model in (Chant, Sequence):
            for value in (None, "", " \t\r\n\u00a0"):
                with self.subTest(model=model.__name__, value=value):
                    obj = model.objects.create(
                        source=self.source,
                        **dict.fromkeys(CHANT_FIELDS, value),
                    )
                    # Signals receive the same normalized values as the DB.
                    self.assertEqual(obj.volpiano, "")
                    obj.refresh_from_db()
                    for field in CHANT_FIELDS:
                        self.assertEqual(getattr(obj, field), "", field)
        for value in (None, "", " \t\r\n\u00a0"):
            source = Source.objects.create(
                shelfmark="Empty prose", **dict.fromkeys(SOURCE_FIELDS, value)
            )
            source.refresh_from_db()
            for field in SOURCE_FIELDS:
                self.assertEqual(getattr(source, field), "", field)

    def test_text_trimming_preserves_interior_and_note_formatting(self) -> None:
        text = "Laudate  dominum\nomnes"
        notes = "    indented note\nline with a hard break  \n"
        for model in (Chant, Sequence):
            obj = model.objects.create(
                source=self.source,
                manuscript_full_text=" \r\n" + text + "\t ",
                manuscript_full_text_std_spelling="\u00a0Benedictus dominus\u00a0",
                manuscript_syllabized_full_text="\nLau-da-te do-mi-num \n",
                indexing_notes=notes,
                image_link=" https://example.com/page one \n",
            )
            obj.refresh_from_db()
            self.assertEqual(obj.manuscript_full_text, text)
            self.assertEqual(
                obj.manuscript_full_text_std_spelling, "Benedictus dominus"
            )
            self.assertEqual(obj.manuscript_syllabized_full_text, "Lau-da-te do-mi-num")
            self.assertEqual(obj.indexing_notes, notes)
            self.assertEqual(obj.image_link, "https://example.com/page%20one")
        source = Source.objects.create(
            shelfmark="Formatted prose", **dict.fromkeys(SOURCE_FIELDS, notes)
        )
        source.refresh_from_db()
        for field in SOURCE_FIELDS:
            self.assertEqual(getattr(source, field), notes)

    def test_literal_orm_updates_and_bulk_operations(self) -> None:
        for model in (Chant, Sequence):
            obj = model(source=self.source, **dict.fromkeys(CHANT_FIELDS, None))
            model.objects.bulk_create([obj])
            obj.refresh_from_db()
            for field in CHANT_FIELDS:
                self.assertEqual(getattr(obj, field), "")
            model.objects.filter(pk=obj.pk).update(
                **dict.fromkeys(CHANT_FIELDS, " \r\n")
            )
            obj.refresh_from_db()
            for field in CHANT_FIELDS:
                self.assertEqual(getattr(obj, field), "")
                setattr(obj, field, None)
            model.objects.bulk_update([obj], CHANT_FIELDS)
            obj.refresh_from_db()
            for field in CHANT_FIELDS:
                self.assertEqual(getattr(obj, field), "")
            model.objects.filter(pk=obj.pk).update(manuscript_full_text="  Gloria  ")
            obj.refresh_from_db()
            self.assertEqual(obj.manuscript_full_text, "Gloria")
        Source.objects.filter(pk=self.source.pk).update(
            **dict.fromkeys(SOURCE_FIELDS, None)
        )
        self.source.refresh_from_db()
        for field in SOURCE_FIELDS:
            self.assertEqual(getattr(self.source, field), "")

    def test_lookup_values_keep_significant_spaces(self) -> None:
        word = Chant.objects.create(
            source=self.source, manuscript_full_text="Pater et filius"
        )
        substring = Chant.objects.create(
            source=self.source, manuscript_full_text="Aeternum"
        )
        self.assertEqual(
            list(Chant.objects.filter(manuscript_full_text__icontains=" et ")), [word]
        )
        self.assertEqual(
            set(Chant.objects.filter(manuscript_full_text__icontains="et")),
            {word, substring},
        )

    def test_database_rejects_null_from_raw_sql(self) -> None:
        for model, field in (
            (Chant, "volpiano"),
            (Sequence, "image_link"),
            (Source, "summary"),
        ):
            obj = (
                self.source
                if model is Source
                else model.objects.create(source=self.source)
            )
            with self.subTest(model=model.__name__), self.assertRaises(IntegrityError):
                with transaction.atomic(), connection.cursor() as cursor:
                    cursor.execute(
                        f'UPDATE "{model._meta.db_table}" SET "{field}" = NULL WHERE id = %s',
                        [obj.pk],
                    )

    def test_model_forms_accept_empty_fields_and_preserve_notes(self) -> None:
        for model, fields in (
            (Chant, CHANT_FIELDS),
            (Sequence, CHANT_FIELDS),
            (Source, SOURCE_FIELDS),
        ):
            form_class = modelform_factory(model, fields=fields)
            form = form_class(data=dict.fromkeys(fields, " \r\n"))
            self.assertTrue(form.is_valid(), form.errors)
            obj = form.save(commit=False)
            if model is Source:
                obj.shelfmark = "Form prose"
            else:
                obj.source = self.source
            obj.save()
            obj.refresh_from_db()
            for field in fields:
                self.assertEqual(getattr(obj, field), "")
        notes = "    preserve indentation\nlast line  "
        form = modelform_factory(Source, fields=SOURCE_FIELDS)(
            data=dict.fromkeys(SOURCE_FIELDS, notes), instance=self.source
        )
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.source.refresh_from_db()
        self.assertEqual(self.source.description, notes)

    def test_chant_edit_uses_cleaned_text_and_cannot_clear_existing_text(self) -> None:
        chant = Chant.objects.create(
            source=self.source,
            folio="001r",
            c_sequence=1,
            manuscript_full_text_std_spelling="Benedictus dominus",
        )
        data = {
            "source": self.source.pk,
            "folio": "001r",
            "c_sequence": 1,
            "manuscript_full_text_std_spelling": " \r\nGloria patri \n",
        }
        form = ChantEditForm(data=data, instance=chant)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(
            form.cleaned_data["manuscript_full_text_std_spelling"], "Gloria patri"
        )
        form.save()
        chant.refresh_from_db()
        self.assertEqual(chant.manuscript_full_text_std_spelling, "Gloria patri")
        for blank in ("", " \r\n\t"):
            form = ChantEditForm(
                data={**data, "manuscript_full_text_std_spelling": blank},
                instance=chant,
            )
            self.assertFalse(form.is_valid())
            self.assertEqual(
                form.errors.as_data()["manuscript_full_text_std_spelling"][0].code,
                "txt-req-prev-existing",
            )

    def test_clearing_melody_clears_search_fields_and_source_count(self) -> None:
        chant = Chant.objects.create(source=self.source, volpiano="\r\n1--a--b--4 \n")
        chant.refresh_from_db()
        self.assertEqual((chant.volpiano_notes, chant.volpiano_intervals), ("ab", "1"))
        self.source.refresh_from_db()
        self.assertEqual(self.source.number_of_melodies, 1)
        chant.volpiano = None
        chant.save()
        chant.refresh_from_db()
        self.source.refresh_from_db()
        self.assertEqual(
            (chant.volpiano, chant.volpiano_notes, chant.volpiano_intervals),
            ("", "", ""),
        )
        self.assertEqual(self.source.number_of_melodies, 0)


class TextCleanupConsumerTest(TestCase):
    def setUp(self) -> None:
        self.source = Source.objects.create(shelfmark="Search cleanup", published=True)
        self.chant = Chant.objects.create(
            source=self.source,
            cantus_id="158500",
            folio="001r",
            c_sequence=1,
            manuscript_full_text="  Benedictus dominus  ",
            volpiano="1--a--b--4",
            image_link="https://example.com/image",
        )
        self.empty = [
            Chant.objects.create(
                source=self.source,
                cantus_id="158500",
                folio="001r",
                c_sequence=i + 2,
                manuscript_full_text=value,
                volpiano=value,
                image_link=value,
            )
            for i, value in enumerate((None, "", " \r\n"))
        ]
        self.private_source = Source.objects.create(shelfmark="Private cleanup")
        self.private_chant = Chant.objects.create(
            source=self.private_source, cantus_id="158500", volpiano="1--c--d--4"
        )

    def test_melody_filters_and_permissions(self) -> None:
        for url in (
            reverse("chant-search"),
            reverse("chant-search-ms", args=[self.source.pk]),
        ):
            for value, expected in (
                ("true", {self.chant.pk}),
                ("false", {obj.pk for obj in self.empty}),
            ):
                response = self.client.get(url, {"melodies": value})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(
                    {obj.pk for obj in response.context["chants"]}, expected
                )

    def test_sequence_melody_filters(self) -> None:
        source = Source.objects.create(shelfmark="Sequences", published=True)
        segment, _ = Segment.objects.get_or_create(
            pk=settings.BOWER_SEGMENT_ID, defaults={"name": "Bower Sequence Database"}
        )
        source.segment_m2m.add(segment)
        melody = Sequence.objects.create(source=source, volpiano="1--a--b--4")
        empty = Sequence.objects.create(source=source, volpiano=" \n")
        for value, expected in (("true", {melody.pk}), ("false", {empty.pk})):
            response = self.client.get(
                reverse("chant-search-ms", args=[source.pk]), {"melodies": value}
            )
            self.assertEqual({obj.pk for obj in response.context["chants"]}, expected)
        response = self.client.get(
            reverse("chant-search"), {"melodies": "true", "segment": segment.pk}
        )
        self.assertEqual(
            [(obj.source_id, obj.pk) for obj in response.context["chants"]],
            [(source.pk, melody.pk)],
        )

    def test_presence_sort_groups_all_missing_values_together(self) -> None:
        missing = {obj.pk for obj in self.empty}
        for url in (
            reverse("chant-search"),
            reverse("chant-search-ms", args=[self.source.pk]),
        ):
            for order in ("has_fulltext", "has_melody", "has_image"):
                for direction in ("asc", "desc"):
                    with self.subTest(url=url, order=order, direction=direction):
                        response = self.client.get(
                            url,
                            {"cantus_id": "158500", "order": order, "sort": direction},
                        )
                        ids = [obj.pk for obj in response.context["chants"]]
                        self.assertEqual(
                            ids[0 if direction == "asc" else -1], self.chant.pk
                        )
                        self.assertEqual(
                            set(ids[1:] if direction == "asc" else ids[:-1]), missing
                        )

    def test_keyword_boundaries_use_trimmed_text(self) -> None:
        for url in (
            reverse("chant-search"),
            reverse("chant-search-ms", args=[self.source.pk]),
        ):
            for op, keyword in (
                ("starts_with", "Benedictus"),
                ("ends_with", "dominus"),
            ):
                response = self.client.get(url, {"op": op, "keyword": keyword})
                self.assertEqual(
                    [obj.pk for obj in response.context["chants"]], [self.chant.pk]
                )

    def test_json_melody_export_excludes_missing_and_private_melodies(self) -> None:
        response = self.client.get(reverse("json-melody-export", args=["158500"]))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual([item["nid"] for item in data], [self.chant.pk])
        self.assertEqual(data[0]["fulltext"], "")
        self.assertEqual(data[0]["syllabized_full_text"], "")
        self.assertEqual(
            set(data[0]),
            {
                "mid",
                "nid",
                "cid",
                "siglum",
                "srcnid",
                "folio",
                "incipit",
                "fulltext",
                "syllabized_full_text",
                "volpiano",
                "mode",
                "feast",
                "office",
                "genre",
                "position",
                "chantlink",
                "srclink",
            },
        )

    def test_ajax_melody_list_excludes_missing_and_private_melodies(self) -> None:
        response = self.client.get(reverse("ajax-melody", args=["158500"]))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(set(data), {"concordances", "concordance_count"})
        self.assertEqual(data["concordance_count"], 1)
        self.assertEqual(len(data["concordances"]), 1)
        self.assertEqual(
            data["concordances"][0]["chant_link"], self.chant.get_absolute_url()
        )
        self.assertEqual(data["concordances"][0]["volpiano"], self.chant.volpiano)

    def test_melody_search_excludes_missing_melodies_for_empty_patterns(self) -> None:
        for notes, transpose in (("", "false"), ("a", "true"), ("ab", "false")):
            with self.subTest(notes=notes, transpose=transpose):
                response = self.client.get(
                    reverse("ajax-melody-search"),
                    {"notes": notes, "transpose": transpose},
                )
                self.assertEqual(response.status_code, 200)
                data = response.json()
                self.assertEqual(data["result_count"], 1)
                self.assertEqual(
                    [item["id"] for item in data["results"]], [self.chant.pk]
                )

    def test_csv_keeps_empty_cells_and_private_source_access(self) -> None:
        response = self.client.get(reverse("csv-export", args=[self.source.pk]))
        rows = list(csv.DictReader(io.StringIO(response.content.decode())))
        by_id = {int(row["node_id"]): row for row in rows}
        self.assertEqual(set(by_id), {self.chant.pk, *(obj.pk for obj in self.empty)})
        for obj in self.empty:
            for field in (
                "fulltext_standardized",
                "fulltext_ms",
                "syllabized_full_text",
                "volpiano",
                "image_link",
            ):
                self.assertEqual(by_id[obj.pk][field], "")
        response = self.client.get(reverse("csv-export", args=[self.private_source.pk]))
        self.assertEqual(response.status_code, 403)


class TextCleanupMigrationTest(TransactionTestCase):
    old_target = [("main_app", "0044_alter_source_source_completeness")]
    new_target = [("main_app", "0046_canonical_empty_text")]

    def migrate(self, target: list[tuple[str, str]]) -> Apps:
        executor = MigrationExecutor(connection)
        executor.migrate(target)
        return executor.loader.project_state(target).apps

    def test_existing_data_cleanup_and_schema_rollback(self) -> None:
        self.addCleanup(self.migrate, self.new_target)
        old_apps = self.migrate(self.old_target)
        old_source = old_apps.get_model("main_app", "Source")
        formatting = "    indented paragraph\nlast line  \n"
        source = old_source.objects.create(
            pk=0,
            shelfmark="Legacy cleanup",
            description=formatting,
            selected_bibliography=" \r\n",
            summary=None,
            number_of_melodies=99,
        )
        unchanged_date = source.date_updated
        ids = {}
        for name in ("Chant", "Sequence"):
            model = old_apps.get_model("main_app", name)
            rows = [
                model.objects.create(
                    source_id=source.pk,
                    incipit="Curated incipit",
                    manuscript_full_text=" \r\nGloria  patri\nfilio \t",
                    manuscript_full_text_std_spelling="\u00a0Benedictus dominus\u00a0",
                    manuscript_syllabized_full_text=None,
                    image_link=None,
                    indexing_notes=formatting,
                    volpiano=melody,
                    volpiano_notes="stale",
                    volpiano_intervals="stale",
                )
                for melody in (None, "", " \t\r\n", "\r\n1--a--b--4\n")
            ]
            ids[name] = [(obj.pk, obj.date_updated) for obj in rows]
        migration = importlib.import_module(
            "main_app.migrations.0045_normalize_text_data"
        )
        with patch.object(migration, "BATCH_SIZE", 2):
            apps = self.migrate(self.new_target)
        for name, rows in ids.items():
            model = apps.get_model("main_app", name)
            for index, (pk, date) in enumerate(rows):
                obj = model.objects.get(pk=pk)
                self.assertEqual(obj.manuscript_full_text, "Gloria  patri\nfilio")
                self.assertEqual(
                    obj.manuscript_full_text_std_spelling, "Benedictus dominus"
                )
                self.assertEqual(obj.manuscript_syllabized_full_text, "")
                self.assertEqual(obj.image_link, "")
                self.assertEqual(obj.indexing_notes, formatting)
                self.assertEqual(obj.incipit, "Curated incipit")
                self.assertEqual(obj.date_updated, date)
                self.assertEqual(
                    (obj.volpiano, obj.volpiano_notes, obj.volpiano_intervals),
                    ("1--a--b--4", "ab", "1") if index == 3 else ("", "", ""),
                )
        cleaned_source = apps.get_model("main_app", "Source").objects.get(pk=source.pk)
        self.assertEqual(
            (
                cleaned_source.description,
                cleaned_source.selected_bibliography,
                cleaned_source.summary,
            ),
            (formatting, "", ""),
        )
        self.assertEqual(cleaned_source.number_of_melodies, 1)
        self.assertEqual(cleaned_source.date_updated, unchanged_date)
        before = {
            name: list(apps.get_model("main_app", name).objects.values().order_by("pk"))
            for name in ("Chant", "Sequence", "Source")
        }
        with connection.schema_editor() as editor:
            migration.normalize_text_data(apps, editor)
        after = {
            name: list(apps.get_model("main_app", name).objects.values().order_by("pk"))
            for name in before
        }
        self.assertEqual(before, after)
        # Schema reversal keeps cleaned data and permits NULL again. It does
        # not pretend to reconstruct the original whitespace or NULL values.
        old_apps = self.migrate(self.old_target)
        model = old_apps.get_model("main_app", "Chant")
        self.assertEqual(
            model.objects.get(pk=ids["Chant"][0][0]).manuscript_full_text,
            "Gloria  patri\nfilio",
        )
        model.objects.filter(pk=ids["Chant"][0][0]).update(manuscript_full_text=None)
        self.assertIsNone(model.objects.get(pk=ids["Chant"][0][0]).manuscript_full_text)
