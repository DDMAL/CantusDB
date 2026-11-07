"""Preserve a range's previous value without merging it into an active revision."""

from datetime import timedelta

import reversion
from django.contrib.contenttypes.models import ContentType
from django.core import serializers
from django.db.models import Model
from reversion.models import Revision, Version


def record_range_baseline(record: Model, database: str) -> None:
    """Write a separate before-version inside the caller's transaction.

    Nested create_revision() blocks coalesce into the active revision, which
    retains only the last version of each object. Use the revision models for
    this baseline instead. Chant and Sequence use reversion's default full-row
    JSON registration, without followed relations or natural foreign keys.
    """
    revision = Revision.objects.using(database).create(
        date_created=reversion.get_date_created() - timedelta(microseconds=1),
        user=reversion.get_user(),
        comment="Before save that recalculates chant range",
    )
    Version.objects.using(database).create(
        revision=revision,
        object_id=str(record.pk),
        content_type=ContentType.objects.db_manager(database).get_for_model(record),
        db=database,
        format="json",
        serialized_data=serializers.serialize("json", [record]),
        object_repr=str(record),
    )
