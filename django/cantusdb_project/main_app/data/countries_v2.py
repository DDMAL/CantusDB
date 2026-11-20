"""Positive Cantus IDs for the frozen set of 36 countries. Never renumber entries."""

from main_app.data import countries_v1, country_wikidata_v1

# Assign IDs once from the original catalogue order. The source tuple is frozen
# for migrations; editing a display name or changing admin ordering has no effect.
COUNTRIES = tuple(
    (pk, name, getty_id, country_wikidata_v1.WIKIDATA_BY_COUNTRY[old_pk], *aliases)
    for pk, (old_pk, name, getty_id, *aliases) in enumerate(
        countries_v1.COUNTRIES, start=1
    )
)
CANADA_ID = 6
NOT_RECORDED = 37
UNKNOWN = 38
FIRST_LOCAL_ID = 39
IDS_BY_LABEL = {
    label.casefold(): pk
    for pk, name, _, _, *aliases in COUNTRIES
    for label in (name, *aliases)
}
_BY_GETTY = {getty_id: pk for pk, _, getty_id, _, *_ in COUNTRIES}
_BY_WIKIDATA = {qid: pk for pk, _, _, qid, *_ in COUNTRIES}
LEGACY_TO_POSITIVE = {
    old[0]: new[0] for old, new in zip(countries_v1.COUNTRIES, COUNTRIES, strict=True)
} | {-1: NOT_RECORDED, -2: UNKNOWN}


def catalogue_ids(labels, authorities):
    matches = {IDS_BY_LABEL[label] for label in labels if label in IDS_BY_LABEL}
    for key, index in (("getty_tgn", _BY_GETTY), ("wikidata", _BY_WIKIDATA)):
        pk = index.get(authorities.get(key))
        if pk is not None:
            matches.add(pk)
    return matches
