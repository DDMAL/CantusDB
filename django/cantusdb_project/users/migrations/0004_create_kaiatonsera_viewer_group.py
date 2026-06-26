from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps

# Keep in sync with main_app.permissions.KAIATONSERA_VIEWER_GROUP.
# Inlined here so the migration stays self-contained. See issue #2077.
KAIATONSERA_VIEWER_GROUP = "kaiatonsera viewer"


def create_kaiatonsera_viewer_group(
    apps: StateApps, schema_editor: BaseDatabaseSchemaEditor
) -> None:
    """
    Create the "kaiatonsera viewer" group.

    Members of this group can see the "Chant record created by" field on chants
    in the Kaiatonsera master sources. Membership (the people in the class) is
    managed by admins through the admin interface.
    """
    Group = apps.get_model("users", "Group")
    Group.objects.get_or_create(
        name=KAIATONSERA_VIEWER_GROUP,
        defaults={
            "description": (
                "Members of the Kaiatonsera (Kanien'kehá / Mohawk) chant class. "
                "Users in this group can see the 'Chant record created by' field "
                "on chants in the project's master sources."
            )
        },
    )


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0003_alter_groupmembership_expiration"),
    ]

    operations = [
        migrations.RunPython(
            create_kaiatonsera_viewer_group,
            migrations.RunPython.noop,
        ),
    ]
