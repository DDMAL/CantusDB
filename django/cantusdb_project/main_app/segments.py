from django.conf import settings

from main_app.models import Source


def is_sequence_source(source: Source) -> bool:
    """True if `source` holds sequences rather than chants.

    Sources in the Sequence Database (Bower) segment hold sequences. One put
    in that segment that has only chants is still a chant source, so its
    chant links, inventory, CSV export and search keep working (#2252).
    """
    return (
        source.segment_m2m.filter(id=settings.BOWER_SEGMENT_ID).exists()
        and source.sequence_set.exists()
    )
