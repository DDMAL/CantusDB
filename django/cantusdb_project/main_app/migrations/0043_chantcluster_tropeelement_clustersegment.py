import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("main_app", "0042_datacheckconfig"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="TropeElement",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "date_created",
                    models.DateTimeField(
                        auto_now_add=True, help_text="The date this entry was created"
                    ),
                ),
                (
                    "date_updated",
                    models.DateTimeField(
                        auto_now=True, help_text="The date this entry was updated"
                    ),
                ),
                (
                    "cantus_id",
                    models.CharField(
                        max_length=255, unique=True, verbose_name="cantus ID"
                    ),
                ),
                ("text", models.TextField()),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="%(class)s_created_by_user",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "genre",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        to="main_app.genre",
                    ),
                ),
                (
                    "last_updated_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="%(class)s_last_updated_by_user",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["cantus_id"],
            },
        ),
        migrations.CreateModel(
            name="ChantCluster",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "date_created",
                    models.DateTimeField(
                        auto_now_add=True, help_text="The date this entry was created"
                    ),
                ),
                (
                    "date_updated",
                    models.DateTimeField(
                        auto_now=True, help_text="The date this entry was updated"
                    ),
                ),
                (
                    "base_cantus_id",
                    models.CharField(max_length=255, verbose_name="base cantus ID"),
                ),
                (
                    "base_text",
                    models.TextField(
                        help_text="The untroped base text. Frozen once segments exist."
                    ),
                ),
                (
                    "base_text_hash",
                    models.CharField(
                        blank=True,
                        help_text="Digest of the base text as Cantus Index served it, for drift detection",
                        max_length=64,
                    ),
                ),
                (
                    "token_scheme",
                    models.CharField(
                        choices=[("whitespace", "Whitespace-delimited words")],
                        default="whitespace",
                        max_length=16,
                    ),
                ),
                (
                    "chant",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="cluster",
                        to="main_app.chant",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="%(class)s_created_by_user",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "last_updated_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="%(class)s_last_updated_by_user",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "abstract": False,
            },
        ),
        migrations.CreateModel(
            name="ClusterSegment",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "date_created",
                    models.DateTimeField(
                        auto_now_add=True, help_text="The date this entry was created"
                    ),
                ),
                (
                    "date_updated",
                    models.DateTimeField(
                        auto_now=True, help_text="The date this entry was updated"
                    ),
                ),
                ("order", models.PositiveSmallIntegerField()),
                (
                    "start",
                    models.PositiveSmallIntegerField(
                        blank=True,
                        help_text="First base-text token, inclusive",
                        null=True,
                    ),
                ),
                (
                    "end",
                    models.PositiveSmallIntegerField(
                        blank=True,
                        help_text="Last base-text token, exclusive",
                        null=True,
                    ),
                ),
                ("text", models.TextField(blank=True, default="")),
                (
                    "cluster",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="segments",
                        to="main_app.chantcluster",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="%(class)s_created_by_user",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "element",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        to="main_app.tropeelement",
                    ),
                ),
                (
                    "last_updated_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="%(class)s_last_updated_by_user",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["order"],
            },
        ),
        migrations.AddConstraint(
            model_name="clustersegment",
            constraint=models.UniqueConstraint(
                deferrable=models.Deferrable.DEFERRED,
                fields=("cluster", "order"),
                name="cluster_segment_unique_order",
            ),
        ),
        migrations.AddConstraint(
            model_name="clustersegment",
            constraint=models.CheckConstraint(
                condition=models.Q(("start__isnull", True))
                | models.Q(("end__gt", models.F("start"))),
                name="cluster_segment_end_after_start",
            ),
        ),
        migrations.AddConstraint(
            model_name="clustersegment",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    models.Q(
                        ("start__isnull", False),
                        ("end__isnull", False),
                        ("element__isnull", True),
                        ("text", ""),
                    )
                    | models.Q(
                        ("start__isnull", True),
                        ("end__isnull", True),
                        ("element__isnull", False),
                        ("text", ""),
                    )
                    | models.Q(
                        ("start__isnull", True),
                        ("end__isnull", True),
                        ("element__isnull", True),
                        models.Q(("text", ""), _negated=True),
                    )
                ),
                name="cluster_segment_exactly_one_shape",
            ),
        ),
    ]
