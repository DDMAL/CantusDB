import json
from io import StringIO

from django.core import serializers
from django.core.management import call_command
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from django.utils import timezone
from reversion.models import Version as LiveVersion


class CountryMigrationTests(TransactionTestCase):
    old = ("main_app", "0047_notation_clavis_sequentiarum_labels")
    schema = ("main_app", "0048_create_country")
    new = ("main_app", "0049_link_institution_countries")
    reversion = ("reversion", "0002_add_index_on_version_for_content_type_and_db")

    def migrate(self, target):
        executor = MigrationExecutor(connection)
        targets = [target, self.reversion]
        executor.migrate(targets)
        return executor.loader.project_state(targets).apps

    def restore_schema(self):
        apps = self.migrate(self.old)
        apps.get_model("main_app", "Institution").objects.all().delete()
        apps.get_model("reversion", "Version").objects.filter(
            content_type__app_label="main_app", content_type__model="institution"
        ).delete()
        self.migrate(self.new)

    def test_upgrade_and_rollback_of_institutions_and_saved_revisions(self):
        apps = self.migrate(self.old)
        self.addCleanup(self.restore_schema)
        Institution = apps.get_model("main_app", "Institution")
        revision = apps.get_model("reversion", "Revision").objects.create(
            date_created=timezone.now()
        )
        content_type, _ = apps.get_model(
            "contenttypes", "ContentType"
        ).objects.get_or_create(app_label="main_app", model="institution")
        versions = []
        institutions = []
        for i, (current, historical) in enumerate(
            (
                ("USA", "Vatican City"),
                (" united STATES ", "Land O' Tests"),
                ("[No Country]", "[No Country]"),
                ("Local territory", "Local territory"),
                ("Canada", "Canada"),
                ("Unknown", "[Unknown Country]"),
            )
        ):
            institution = Institution.objects.create(
                name="Library", siglum=f"XX-{i}", country=current
            )
            institutions.append(institution.pk)
            data = json.loads(serializers.serialize("json", [institution]))
            data[0]["fields"]["country"] = historical
            version = apps.get_model("reversion", "Version").objects.create(
                revision=revision,
                object_id=str(institution.pk),
                content_type=content_type,
                db="default",
                format="json",
                serialized_data=json.dumps(data),
                object_repr="Library",
            )
            versions.append(version.pk)

        apps = self.migrate(self.schema)
        Country = apps.get_model("main_app", "Country")
        with self.assertRaisesMessage(ValueError, "load_countries"):
            self.migrate(self.new)
        call_command("load_countries", stdout=StringIO())
        with self.assertRaisesMessage(ValueError, "Land O' Tests") as error:
            self.migrate(self.new)
        self.assertIn("Local territory", str(error.exception))
        self.assertEqual(Institution.objects.get(pk=institutions[0]).country, "USA")
        self.assertEqual(
            json.loads(
                apps.get_model("reversion", "Version")
                .objects.get(pk=versions[1])
                .serialized_data
            )[0]["fields"]["country"],
            "Land O' Tests",
        )
        local_country = Country.objects.create(
            name="Local territory", aliases="Land O' Tests"
        )
        usa = Country.objects.get(rism_code="US")
        holy_see = Country.objects.get(rism_code="V")
        apps = self.migrate(self.new)
        Institution = apps.get_model("main_app", "Institution")
        us, duplicate, blank, local, canada, unknown = (
            Institution.objects.get(pk=pk) for pk in institutions
        )
        self.assertEqual(us.country_id, usa.pk)
        self.assertEqual(duplicate.country_id, usa.pk)
        self.assertIsNone(blank.country_id)
        self.assertEqual(canada.country_id, Country.objects.get(rism_code="CDN").pk)
        self.assertEqual(local.country_id, local_country.pk)
        self.assertEqual(unknown.country.name, "Unknown")
        self.assertEqual(us.country.name, "United States of America")
        for pk, expected in zip(
            versions,
            [
                holy_see.pk,
                local_country.pk,
                None,
                local_country.pk,
                canada.country_id,
                unknown.country_id,
            ],
            strict=True,
        ):
            self.assertEqual(
                LiveVersion.objects.get(pk=pk)._object_version.object.country_id,
                expected,
            )

        LiveVersion.objects.get(pk=versions[0]).revert()
        us.refresh_from_db()
        self.assertEqual(us.country_id, holy_see.pk)

        apps = self.migrate(self.old)
        records = apps.get_model("main_app", "Institution").objects
        self.assertEqual(records.get(pk=us.pk).country, "Holy See")
        self.assertEqual(
            records.get(pk=duplicate.pk).country, "United States of America"
        )
        self.assertEqual(records.get(pk=blank.pk).country, "[No Country]")
        for pk, name in zip(
            versions,
            [
                "Holy See",
                "Local territory",
                "[No Country]",
                "Local territory",
                "Canada",
                "Unknown",
            ],
        ):
            data = (
                apps.get_model("reversion", "Version")
                .objects.get(pk=pk)
                .serialized_data
            )
            self.assertEqual(json.loads(data)[0]["fields"]["country"], name)
