from main_app.models import Chant


def next_chants(cantus_id):
    """find instances of the chant with the given cantus_id
    in all manuscripts, gather a list of other chants that follow the
    specified chant in those manuscripts, and count how often each
    following chant occurs.

    Returns:
        list of duples, each representing a cantusID-count pair
    """
    cantus_ids = []
    counts = []
    concordances = Chant.objects.filter(cantus_id=cantus_id).only(
        "source", "folio", "sequence_number"
    )
    for chant in concordances:
        next_chant = chant.get_next_chant()
        if next_chant:
            # return the number of occurence in the suggestions (not in the entire db)
            if next_chant.cantus_id in cantus_ids:
                idx = cantus_ids.index(next_chant.cantus_id)
                counts[idx] += 1
            else:
                # cantus_id can be None (some chants don't have one)
                if next_chant.cantus_id:
                    # add the new cantus_id to the list, count starts from 1
                    cantus_ids.append(next_chant.cantus_id)
                    counts.append(1)
    
    ids_and_counts = list(zip(cantus_ids, counts))

    return ids_and_counts