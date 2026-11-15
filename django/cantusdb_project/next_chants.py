from main_app.models import Chant
from collections import Counter


def next_chants(cantus_id, display_unpublished=False):
    """find instances of the chant with the given cantus_id
    in all manuscripts, gather a list of other chants that follow the
    specified chant in those manuscripts, and count how often each
    following chant occurs.

    Returns:
        list of duples, each representing a cantusID-count pair
    """
    concordances = Chant.objects.filter(cantus_id=cantus_id)
    if not display_unpublished:
        concordances = concordances.filter(source__published=True)

    # Read successor IDs in one joined query, without loading deferred foreign
    # keys and then fetching a successor object for every concordance.
    ids = (
        cid
        for cid in concordances.values_list("next_chant__cantus_id", flat=True)
        if cid is not None
    )
    counts = Counter(ids)
    ids_and_counts = [
        item for item in counts.items()
    ]  # each item is an id-count key-value pair

    return ids_and_counts
