"""
One-off command: move Cantorales sources' users from inventoried_by to
source_data_contributed_by.

The pre-fix import_cantorales command put contributor names into inventoried_by
by mistake. Cantorales sources have no chant inventory, so every user in
inventoried_by on one of these sources is really a data contributor. This
command corrects that in place. It is idempotent: once moved, inventoried_by is
empty and re-running is a no-op.

Run: python manage.py move_cantorales_contributors
"""

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from main_app.models import Segment


class Command(BaseCommand):
    help = (
        "Move Cantorales sources' users from inventoried_by to "
        "source_data_contributed_by (corrects the pre-fix import_cantorales)."
    )

    @transaction.atomic
    def handle(self, *args, **options):
        segment = Segment.objects.filter(pk=settings.CANTORALES_SEGMENT_ID).first()
        if segment is None:
            self.stdout.write(
                f"Cantorales segment (pk={settings.CANTORALES_SEGMENT_ID}) not "
                "found; nothing to do."
            )
            return

        moved_sources = 0
        moved_users = 0
        for source in segment.sources.prefetch_related("inventoried_by").all():
            contributors = list(source.inventoried_by.all())
            if not contributors:
                continue
            source.source_data_contributed_by.add(*contributors)
            source.inventoried_by.remove(*contributors)
            moved_sources += 1
            moved_users += len(contributors)

        self.stdout.write(
            f"Done. Moved {moved_users} user link(s) across {moved_sources} "
            "Cantorales source(s) from inventoried_by -> "
            "source_data_contributed_by."
        )
