import json

from django.core import serializers
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from django.utils import timezone


class CountryMigrationTests(TransactionTestCase):
    old = [
        ("main_app", "0047_notation_clavis_sequentiarum_labels"),
        ("reversion", "0002_add_index_on_version_for_content_type_and_db"),
    ]
    new = [("main_app", "0048_getty_countries")]

    def migrate(self, target):
        executor = MigrationExecutor(connection)
        executor.migrate(target)
        return executor.loader.project_state(target).apps

    def tearDown(self):
        self.migrate(self.new)
        super().tearDown()

    def test_represented_countries_get_their_authority_ids_and_rism_aliases(self):
        from main_app.countries import find_country

        apps = self.migrate(self.old)
        Institution = apps.get_model("main_app", "Institution")
        represented = (
            ("Argentina", "RA", "7006477"),
            ("Japan", "J", "1000120"),
            ("South Africa", "ZA", "1000193"),
            ("Taiwan", "RC", "1000141"),
            ("United Kingdom", "GB", "7008591"),
        )
        for name, siglum, _ in represented:
            Institution.objects.create(
                name="Library", siglum=f"{siglum}-Test", country=name
            )

        self.migrate(self.new)
        for name, siglum, getty_id in represented:
            with self.subTest(country=name):
                country = find_country(siglum.lower())
                self.assertEqual(country.name, name)
                self.assertEqual(country.getty_id, getty_id)
        self.assertIsNone(find_country("SA"))
        self.assertIsNone(find_country("T"))

    def test_migration_discards_old_text_and_keeps_history_usable(self):
        apps = self.migrate(self.old)
        Institution = apps.get_model("main_app", "Institution")
        ContentType = apps.get_model("contenttypes", "ContentType")
        Revision = apps.get_model("reversion", "Revision")
        Version = apps.get_model("reversion", "Version")
        institution = Institution.objects.create(
            name="Library", siglum="US-Test", country="USA"
        )
        unknown = Institution.objects.create(
            name="Unknown", siglum="XX-Test", country="Unknown"
        )
        absent = Institution.objects.create(
            name="Unrecorded", siglum="XX-Missing", country="[No Country]"
        )
        duplicate = Institution.objects.create(
            name="Other library", siglum="US-Other", country="  united STATES  "
        )
        local = Institution.objects.create(
            name="Island library", siglum="XX-Island", country="Local territory"
        )
        content_type, _ = ContentType.objects.get_or_create(
            app_label="main_app", model="institution"
        )
        revision = Revision.objects.create(
            date_created=timezone.now(), comment="Original history"
        )
        original = json.loads(serializers.serialize("json", [institution]))
        original[0]["fields"]["country"] = "Land O' Tests"
        version = Version.objects.create(
            revision=revision,
            object_id=str(institution.pk),
            content_type=content_type,
            db="default",
            format="json",
            serialized_data=json.dumps(original),
            object_repr="Library",
        )
        historical = json.loads(serializers.serialize("json", [duplicate]))
        historical[0]["fields"]["country"] = "Vatican City"
        history_only = Version.objects.create(
            revision=revision,
            object_id=str(duplicate.pk),
            content_type=content_type,
            db="default",
            format="json",
            serialized_data=json.dumps(historical),
            object_repr=duplicate.name,
        )
        timestamp = institution.date_updated
        apps = self.migrate(self.new)
        Institution = apps.get_model("main_app", "Institution")
        Version = apps.get_model("reversion", "Version")
        institution = Institution.objects.get(pk=institution.pk)
        Country = apps.get_model("main_app", "Country")
        self.assertEqual(institution.country.getty_id, "7012149")
        self.assertEqual(
            Institution.objects.get(pk=duplicate.pk).country_id, institution.country_id
        )
        self.assertEqual(
            Institution.objects.get(pk=local.pk).country.name, "Local territory"
        )
        self.assertIsNone(Institution.objects.get(pk=local.pk).country.getty_id)
        self.assertSetEqual(
            set(Country.objects.values_list("name", flat=True)),
            {"Unknown", "Not recorded", "United States", "Local territory", "Holy See"},
        )
        self.assertEqual(institution.country.name, "United States")
        columns = {
            column.name
            for column in connection.introspection.get_table_description(
                connection.cursor(), "main_app_institution"
            )
        }
        self.assertNotIn("country_legacy", columns)
        self.assertNotIn("country_text", columns)
        self.assertEqual(institution.date_updated, timestamp)
        self.assertEqual(Institution.objects.get(pk=unknown.pk).country.name, "Unknown")
        self.assertEqual(
            Institution.objects.get(pk=absent.pk).country.name, "Not recorded"
        )
        fields = json.loads(Version.objects.get(pk=version.pk).serialized_data)[0][
            "fields"
        ]
        self.assertEqual(fields["country"], Country.objects.get(name="Unknown").pk)
        self.assertEqual(set(fields), set(original[0]["fields"]))
        self.assertNotIn("Land O' Tests", json.dumps(fields))

        from reversion.models import Version as LiveVersion

        self.assertEqual(
            LiveVersion.objects.get(
                pk=history_only.pk
            )._object_version.object.country.name,
            "Holy See",
        )
        recovered = LiveVersion.objects.get(pk=version.pk)._object_version.object
        self.assertEqual(recovered.country.name, "Unknown")
        self.assertFalse(hasattr(recovered, "country_legacy"))

        # Institutions and revisions created after migration use the same rollback.
        new_institution = Institution.objects.create(
            name="New library", siglum="XX-New"
        )
        new_version = Version.objects.create(
            revision_id=revision.pk,
            object_id=str(new_institution.pk),
            content_type_id=content_type.pk,
            db="default",
            format="json",
            serialized_data=serializers.serialize("json", [new_institution]),
            object_repr="New library",
        )

        # Rollback uses canonical names; discarded spellings cannot be recovered.
        apps = self.migrate(self.old)
        Institution = apps.get_model("main_app", "Institution")
        Version = apps.get_model("reversion", "Version")
        self.assertEqual(
            Institution.objects.get(pk=institution.pk).country, "United States"
        )
        original[0]["fields"]["country"] = "Unknown"
        self.assertEqual(
            json.loads(Version.objects.get(pk=version.pk).serialized_data), original
        )
        self.assertEqual(Institution.objects.get(pk=absent.pk).country, "[No Country]")

        self.assertEqual(
            Institution.objects.get(pk=new_institution.pk).country, "[No Country]"
        )
        new_fields = json.loads(Version.objects.get(pk=new_version.pk).serialized_data)[
            0
        ]["fields"]
        self.assertEqual(new_fields["country"], "[No Country]")
        self.assertNotIn("country_legacy", new_fields)

        # If someone edits the country after deployment, rollback keeps that edit.
        apps = self.migrate(self.new)
        canada = apps.get_model("main_app", "Country").objects.create(name="Canada")
        apps.get_model("main_app", "Institution").objects.filter(
            pk=institution.pk
        ).update(country_id=canada.pk)
        apps = self.migrate(self.old)
        self.assertEqual(
            apps.get_model("main_app", "Institution")
            .objects.get(pk=institution.pk)
            .country,
            "Canada",
        )
