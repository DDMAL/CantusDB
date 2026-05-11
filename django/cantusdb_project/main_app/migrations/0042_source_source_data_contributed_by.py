from django.conf import settings
from django.db import migrations, models
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps


def move_cantorales_contributors(
    apps: StateApps, schema_editor: BaseDatabaseSchemaEditor
) -> None:
    """
    Move users from inventoried_by to source_data_contributed_by for all
    sources in the "Cantorales in the Americas" segment.

    These sources were populated by the import_cantorales management command,
    which put contributor names into inventoried_by by mistake.  Since
    Cantorales sources have no chant inventory, every user in inventoried_by
    on one of these sources is a data contributor, not an inventorier.
    """
    Segment = apps.get_model("main_app", "Segment")
    try:
        cantorales = Segment.objects.get(pk=4067)
    except Segment.DoesNotExist:
        return  # segment not yet created (e.g. fresh database)

    for source in cantorales.sources.prefetch_related("inventoried_by").all():
        contributors = list(source.inventoried_by.all())
        if contributors:
            source.source_data_contributed_by.add(*contributors)
            source.inventoried_by.remove(*contributors)


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("main_app", "0041_alter_source_source_completeness"),
    ]

    operations = [
        migrations.AddField(
            model_name="source",
            name="source_data_contributed_by",
            field=models.ManyToManyField(
                blank=True,
                related_name="contributed_data_for_sources",
                to=settings.AUTH_USER_MODEL,
                verbose_name="source metadata contributed by",
            ),
        ),
        migrations.RunPython(
            move_cantorales_contributors,
            migrations.RunPython.noop,
        ),
    ]
