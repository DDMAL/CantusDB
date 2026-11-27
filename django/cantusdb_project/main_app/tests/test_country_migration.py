import json
from io import StringIO
from unittest.mock import patch

from django.contrib.contenttypes.models import ContentType
from django.core import serializers
from django.core.management import call_command
from django.core.serializers.json import Deserializer as DjangoJSONDeserializer
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone
from reversion import add_to_revision, create_revision
from reversion.errors import RevertError
from reversion.models import Revision, Version as LiveVersion

from main_app.models import Country, Institution as LiveInstitution
from main_app.tests.make_fakes import make_fake_user


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
        originals = {}
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
            originals[version.pk] = version.serialized_data

        apps = self.migrate(self.schema)
        Country = apps.get_model("main_app", "Country")
        with self.assertRaisesMessage(ValueError, "load_countries"):
            self.migrate(self.new)
        call_command("load_countries", stdout=StringIO())
        with self.assertRaisesMessage(ValueError, "Local territory"):
            self.migrate(self.new)
        self.assertEqual(Institution.objects.get(pk=institutions[0]).country, "USA")
        local_country = Country.objects.create(name="Local territory")
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
        # This spelling exists only in history. It cannot block the upgrade.
        with self.assertRaisesMessage(RevertError, "Land O' Tests"):
            LiveVersion.objects.get(pk=versions[1]).revert()
        local_country.aliases = "Land O' Tests"
        local_country.save()
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

        # Keep a snapshot taken on the new schema usable by either release.
        with create_revision():
            LiveInstitution.objects.get(pk=us.pk).save()
        modern = LiveVersion.objects.get_for_object_reference(
            LiveInstitution, us.pk
        ).first()
        originals[modern.pk] = modern.serialized_data
        self.assertEqual(
            json.loads(modern.serialized_data)[0]["fields"]["country"], "Holy See"
        )

        # Modern snapshots identify the same country even after a rename.
        Country.objects.filter(pk=holy_see.pk).update(name="Renamed country")
        self.assertEqual(modern.field_dict["country_id"], holy_see.pk)

        apps = self.migrate(self.old)
        # Use Django's stock reader with the pre-upgrade models, as the old
        # release would when reverting a snapshot taken on the new release.
        with patch("django.core.serializers.python.apps", apps):
            restored = next(
                DjangoJSONDeserializer(modern.serialized_data, ignorenonexistent=True)
            )
            self.assertEqual(restored.object.country, "Holy See")
        records = apps.get_model("main_app", "Institution").objects
        self.assertEqual(records.get(pk=us.pk).country, "Renamed country")
        self.assertEqual(
            records.get(pk=duplicate.pk).country, "United States of America"
        )
        self.assertEqual(records.get(pk=blank.pk).country, "[No Country]")
        self.assertEqual(
            dict(
                LiveVersion.objects.filter(pk__in=originals).values_list(
                    "pk", "serialized_data"
                )
            ),
            originals,
        )


class InstitutionRevisionAdminTests(TestCase):
    def test_new_revision_reads_country_names_once_for_multiple_institutions(self):
        canada = Country.objects.create(name="Canada")
        institutions = [
            LiveInstitution.objects.create(
                name="Library", siglum=f"CDN-{i}", country=country
            )
            for i, country in enumerate((canada, canada, None))
        ]
        with CaptureQueriesContext(connection) as queries, create_revision():
            for institution in institutions:
                add_to_revision(institution)
        # Reversion also joins Country when checking that the institutions
        # still exist, because Institution's default ordering uses country.
        name_reads = [
            q["sql"] for q in queries if 'FROM "main_app_country"' in q["sql"]
        ]
        self.assertEqual(len(name_reads), 1, name_reads)
        blank = LiveVersion.objects.get_for_object(institutions[-1]).get()
        self.assertIsNone(blank.field_dict["country_id"])
        self.assertEqual(
            json.loads(blank.serialized_data)[0]["fields"]["country"], "[No Country]"
        )

        # A numeric string in a Django fixture is still an ordinary foreign key.
        data = json.loads(serializers.serialize("json", [institutions[0]]))
        data[0]["fields"]["country"] = str(canada.pk)
        loaded = next(
            serializers.deserialize("json", json.dumps(data), ignorenonexistent=True)
        )
        self.assertEqual(loaded.object.country_id, canada.pk)

    def test_preview_restore_and_recover_show_original_spelling(self):
        self.client.force_login(make_fake_user(is_superuser=True))
        country = Country.objects.create(name="Holy See", aliases="Vatican City")
        institution = LiveInstitution.objects.create(name="Library", siglum="V-Lib")
        data = json.loads(serializers.serialize("json", [institution]))
        data[0]["fields"]["country"] = "Vatican City"
        snapshot = json.dumps(data)
        version = LiveVersion.objects.create(
            revision=Revision.objects.create(date_created=timezone.now()),
            object_id=str(institution.pk),
            content_type=ContentType.objects.get_for_model(LiveInstitution),
            db="default",
            format="json",
            serialized_data=snapshot,
            object_repr="Library",
        )
        records = LiveInstitution.objects.filter(pk=institution.pk)
        for recover in (False, True):
            if recover:
                records.delete()
                url = reverse("admin:main_app_institution_recover", args=[version.pk])
            else:
                url = reverse(
                    "admin:main_app_institution_revision",
                    args=[institution.pk, version.pk],
                )
            preview = self.client.get(url)
            self.assertContains(preview, "Vatican City")
            self.assertEqual(
                preview.context["adminform"].form.instance.country_id, country.pk
            )
            self.assertEqual(
                list(records.values_list("country_id", flat=True)),
                [] if recover else [None],
            )
            form_data = {
                "name": "Library",
                "siglum": "V-Lib",
                "country": country.pk,
                "_save": "Save",
            }
            for inline in preview.context["inline_admin_formsets"]:
                formset = inline.formset
                for field, value in formset.management_form.initial.items():
                    form_data[f"{formset.prefix}-{field}"] = value
            self.assertEqual(self.client.post(url, form_data).status_code, 302)
            self.assertEqual(records.get().country_id, country.pk)
            version.refresh_from_db()
            self.assertEqual(version.serialized_data, snapshot)
