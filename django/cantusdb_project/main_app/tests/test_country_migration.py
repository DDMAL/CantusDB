import json
from io import StringIO

from django.core import serializers
from django.core.management import call_command
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from django.utils import timezone


class CountryMigrationTests(TransactionTestCase):
    old = [
        ("main_app", "0047_notation_clavis_sequentiarum_labels"),
        ("reversion", "0002_add_index_on_version_for_content_type_and_db"),
    ]
    new = [("main_app", "0048_squashed_0053_institution_countries")]

    def migrate(self, target):
        executor = MigrationExecutor(connection)
        if target == self.new:
            # Django selects the original chain when it is partially applied.
            target = executor.loader.graph.leaf_nodes("main_app")
        executor.migrate(target)
        return executor.loader.project_state(target).apps

    def tearDown(self):
        self.migrate(self.new)
        super().tearDown()

    def test_fresh_database_uses_one_country_migration_and_loads_catalogue_on_demand(
        self,
    ):
        from main_app.models import Country

        self.migrate(self.old)
        plan = MigrationExecutor(connection).migration_plan(self.new)
        self.assertEqual(
            [(m.app_label, m.name) for m, _ in plan if m.app_label == "main_app"],
            self.new,
        )
        self.migrate(self.new)
        self.assertEqual(
            set(Country.objects.values_list("pk", flat=True)),
            {Country.NOT_RECORDED, Country.UNKNOWN},
        )
        local = Country.objects.create(name="Local territory")
        self.assertGreater(local.pk, 38)
        call_command("load_countries", stdout=StringIO())
        self.assertEqual(Country.objects.count(), 39)
        self.assertEqual(Country.objects.get(name="Canada").pk, 6)
        self.assertEqual(
            Country.objects.get(pk=Country.CANADA).authorities,
            {"getty_tgn": "7005685", "wikidata": "Q16"},
        )

    def test_wikidata_only_rows_keep_holdings_and_history_when_reconciled(self):
        from main_app.models import Country as LiveCountry
        from reversion.models import Version as LiveVersion

        apps = self.migrate([("main_app", "0049_country_authorities")])
        countries = apps.get_model("main_app", "Country").objects
        countries.create(
            pk=-106,
            name="Canada",
            aliases="CA",
            authorities={"getty_tgn": "7005685"},
        )
        version_ids = []
        content_type, _ = apps.get_model(
            "contenttypes", "ContentType"
        ).objects.get_or_create(app_label="main_app", model="institution")
        revision = apps.get_model("reversion", "Revision").objects.create(
            date_created=timezone.now()
        )
        for name, qid in (("Dominion of Canada", "Q16"), ("Nippon", "Q17")):
            country = countries.create(
                name=name, aliases="Local " + qid, authorities={"wikidata": qid}
            )
            institution = apps.get_model("main_app", "Institution").objects.create(
                name="Library", siglum=qid, country=country
            )
            version_ids.append(
                apps.get_model("reversion", "Version")
                .objects.create(
                    revision=revision,
                    object_id=str(institution.pk),
                    content_type=content_type,
                    db="default",
                    format="json",
                    serialized_data=serializers.serialize("json", [institution]),
                    object_repr=institution.name,
                )
                .pk
            )
        apps = self.migrate(self.new)
        institutions = apps.get_model("main_app", "Institution").objects
        for qid, version_id, expected_pk in zip(
            ("Q16", "Q17"), version_ids, (LiveCountry.CANADA, 20)
        ):
            self.assertEqual(institutions.get(siglum=qid).country_id, expected_pk)
            self.assertEqual(
                LiveVersion.objects.get(
                    pk=version_id
                )._object_version.object.country_id,
                expected_pk,
            )
        canada = LiveCountry.objects.get(pk=LiveCountry.CANADA)
        self.assertEqual(canada.name, "Canada")
        self.assertEqual(
            canada.aliases.splitlines(), ["CA", "Dominion of Canada", "Local Q16"]
        )
        self.assertEqual(
            canada.authorities, {"getty_tgn": "7005685", "wikidata": "Q16"}
        )
        self.assertEqual(LiveCountry.objects.get(pk=20).name, "Nippon")
        self.assertFalse(LiveCountry.objects.filter(pk__gt=38).exists())

    def test_positive_ids_preserve_colliding_local_countries_and_their_references(self):
        from main_app.models import Country

        previous = [("main_app", "0052_country_catalogue_loaded")]
        apps = self.migrate(previous)
        countries = apps.get_model("main_app", "Country").objects
        institutions = apps.get_model("main_app", "Institution").objects
        types = apps.get_model("contenttypes", "ContentType").objects
        country_type, _ = types.get_or_create(app_label="main_app", model="country")
        institution_type, _ = types.get_or_create(
            app_label="main_app", model="institution"
        )
        logs = apps.get_model("admin", "LogEntry").objects
        user = apps.get_model("users", "User").objects.create(
            email="review@example.org"
        )
        versions = apps.get_model("reversion", "Version").objects
        revision = apps.get_model("reversion", "Revision").objects.create(
            date_created=timezone.now()
        )
        examples = [
            (-106, "Dominion of Canada"),
            (6, "Local territory"),
            (37, "Another local country"),
            (120, "Existing local country"),
        ]
        for pk, name in examples:
            country = countries.create(pk=pk, name=name, aliases=name + " alias")
            library = institutions.create(name=name, siglum=str(pk), country=country)
            logs.create(
                user_id=user.pk,
                content_type=country_type,
                object_id=str(pk),
                object_repr=name,
                action_flag=2,
            )
            versions.create(
                revision=revision,
                object_id=str(library.pk),
                content_type=institution_type,
                db="default",
                format="json",
                serialized_data=serializers.serialize("json", [library]),
                object_repr=name,
            )
        self.migrate(self.new)
        for old, name in examples:
            country = Country.objects.get(name=name)
            self.assertEqual(country.aliases, name + " alias")
            if old == -106:
                self.assertEqual(country.pk, Country.CANADA)
            elif old == 120:
                self.assertEqual(country.pk, old)
            else:
                self.assertGreater(country.pk, 120)
            self.assertEqual(institutions.get(name=name).country_id, country.pk)
            self.assertEqual(logs.get(object_repr=name).object_id, str(country.pk))
            saved = json.loads(versions.get(object_repr=name).serialized_data)
            self.assertEqual(saved[0]["fields"]["country"], country.pk)
        high = max(Country.objects.values_list("pk", flat=True))
        self.assertGreater(Country.objects.create(name="New local country").pk, high)
        self.migrate(previous)
        self.assertEqual(institutions.get(name="Dominion of Canada").country_id, -106)
        self.assertEqual(logs.get(object_repr="Dominion of Canada").object_id, "-106")
        self.assertGreater(institutions.get(name="Local territory").country_id, 120)

    def test_wikidata_reconciliation_preserves_rows_on_authority_conflict(self):
        from main_app.models import Country as LiveCountry

        apps = self.migrate([("main_app", "0049_country_authorities")])
        countries = apps.get_model("main_app", "Country").objects
        target = countries.create(
            pk=-106, name="Canada", authorities={"wikidata": "Q99"}
        )
        old = countries.create(
            name="Dominion of Canada", authorities={"wikidata": "Q16"}
        )
        institutions = apps.get_model("main_app", "Institution").objects
        library = institutions.create(name="Library", siglum="CDN-X", country=old)
        with self.assertRaisesMessage(ValueError, "conflicting wikidata IDs"):
            self.migrate(self.new)
        self.assertEqual(institutions.get(pk=library.pk).country_id, old.pk)
        self.assertEqual(countries.get(pk=target.pk).authorities, {"wikidata": "Q99"})
        countries.filter(pk=target.pk).update(authorities={})
        self.migrate(self.new)
        self.assertEqual(institutions.get(pk=library.pk).country_id, LiveCountry.CANADA)

    def test_upgrade_from_previously_applied_0048_keeps_country_references(self):
        from main_app.models import Country as LiveCountry

        intermediate = [
            ("main_app", "0048_getty_countries"),
            ("admin", "0003_logentry_add_action_flag_choices"),
        ]
        apps = self.migrate(intermediate)
        countries = apps.get_model("main_app", "Country").objects
        canada = countries.create(
            pk=301, name="Renamed country", getty_id="7005685", aliases="Custom name"
        )
        local = countries.create(pk=302, name="Local territory", getty_id="98765432")
        institutions = apps.get_model("main_app", "Institution").objects
        institution = institutions.create(
            name="Library", siglum="CDN-Test", country=canada
        )
        content_types = apps.get_model("contenttypes", "ContentType").objects
        content_type, _ = content_types.get_or_create(
            app_label="main_app", model="institution"
        )
        revision = apps.get_model("reversion", "Revision").objects.create(
            date_created=timezone.now()
        )
        version = apps.get_model("reversion", "Version").objects.create(
            revision=revision,
            object_id=str(institution.pk),
            content_type=content_type,
            db="default",
            format="json",
            serialized_data=serializers.serialize("json", [institution]),
            object_repr=institution.name,
        )

        apps = self.migrate(self.new)
        self.assertEqual(
            apps.get_model("main_app", "Institution")
            .objects.get(pk=institution.pk)
            .country_id,
            LiveCountry.CANADA,
        )
        updated = LiveCountry.objects.get(pk=LiveCountry.CANADA)
        self.assertEqual(
            (updated.name, updated.aliases, updated.authorities),
            ("Renamed country", "Custom name", {"getty_tgn": "7005685"}),
        )
        self.assertEqual(
            LiveCountry.objects.get(pk=local.pk).authorities, {"getty_tgn": "98765432"}
        )
        self.assertFalse(LiveCountry.objects.filter(pk=301).exists())
        from reversion.models import Version

        self.assertEqual(
            Version.objects.get(pk=version.pk)._object_version.object.country, updated
        )

        apps = self.migrate(intermediate)
        country = apps.get_model("main_app", "Country").objects.get(pk=-106)
        self.assertEqual(country.getty_id, "7005685")
        self.assertEqual(
            apps.get_model("main_app", "Institution")
            .objects.get(pk=institution.pk)
            .country,
            country,
        )

    def test_loader_supplies_authorities_and_catalogue_aliases_after_conversion(self):
        from main_app.countries import find_country
        from main_app.models import Country

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
        for name, siglum, _ in represented:
            country = Country.objects.get(name=name)
            self.assertEqual(country.authorities, {})
            self.assertEqual(country.aliases, "")
            self.assertIsNone(find_country(siglum))

        call_command("load_countries", stdout=StringIO())
        for name, siglum, getty_id in represented:
            with self.subTest(country=name):
                country = find_country(siglum.lower())
                self.assertEqual(country.name, name)
                self.assertEqual(country.authorities["getty_tgn"], getty_id)
                self.assertIn("wikidata", country.authorities)
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
        self.assertEqual(institution.country.authorities, {})
        self.assertEqual(institution.country.aliases, "USA")
        self.assertEqual(
            Institution.objects.get(pk=duplicate.pk).country_id, institution.country_id
        )
        self.assertEqual(
            Institution.objects.get(pk=local.pk).country.name, "Local territory"
        )
        self.assertEqual(Institution.objects.get(pk=local.pk).country.authorities, {})
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
