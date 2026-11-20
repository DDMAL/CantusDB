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
    new = ("main_app", "0050_remove_institution_country_text")
    reversion = ("reversion", "0002_add_index_on_version_for_content_type_and_db")

    def migrate(self, target):
        executor = MigrationExecutor(connection)
        targets = [target, self.reversion]
        executor.migrate(targets)
        return executor.loader.project_state(targets).apps

    def test_upgrade_and_rollback_of_institutions_and_saved_revisions(self):
        apps = self.migrate(self.old)
        self.addCleanup(self.migrate, self.new)
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

        apps = self.migrate(self.new)
        Institution = apps.get_model("main_app", "Institution")
        Country = apps.get_model("main_app", "Country")
        us, duplicate, blank, local, canada = (
            Institution.objects.get(pk=pk) for pk in institutions
        )
        self.assertEqual(us.country_id, 36)
        self.assertEqual(duplicate.country_id, us.country_id)
        self.assertIsNone(blank.country_id)
        self.assertEqual(canada.country_id, 6)
        self.assertGreater(local.country_id, 36)
        self.assertEqual(us.country.name, "United States of America")
        self.assertEqual(us.country.authorities, {})
        self.assertSetEqual(
            set(Country.objects.values_list("name", flat=True)),
            {
                "United States of America",
                "Holy See",
                "Canada",
                "Unknown",
                "Local territory",
            },
        )
        for pk, expected in zip(
            versions,
            [16, Country.objects.get(name="Unknown").pk, None, local.country_id, 6],
        ):
            self.assertEqual(
                LiveVersion.objects.get(pk=pk)._object_version.object.country_id,
                expected,
            )

        call_command("load_countries", stdout=StringIO())
        self.assertEqual(Country.objects.get(pk=36).rism_code, "US")
        self.assertEqual(
            Country.objects.get(pk=16).authorities["Wikidata"],
            "https://www.wikidata.org/wiki/Q237",
        )
        LiveVersion.objects.get(pk=versions[0]).revert()
        us.refresh_from_db()
        self.assertEqual(us.country_id, 16)

        apps = self.migrate(self.old)
        records = apps.get_model("main_app", "Institution").objects
        self.assertEqual(records.get(pk=us.pk).country, "Holy See")
        self.assertEqual(
            records.get(pk=duplicate.pk).country, "United States of America"
        )
        self.assertEqual(records.get(pk=blank.pk).country, "[No Country]")
        for pk, name in zip(
            versions,
            ["Holy See", "Unknown", "[No Country]", "Local territory", "Canada"],
        ):
            data = (
                apps.get_model("reversion", "Version")
                .objects.get(pk=pk)
                .serialized_data
            )
            self.assertEqual(json.loads(data)[0]["fields"]["country"], name)
