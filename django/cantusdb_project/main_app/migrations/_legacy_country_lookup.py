"""Frozen matches for converting country names and IDs in migrations 0048–0053."""

# Earlier versions assigned -101 to Argentina through -136 to the United States.
# Preserve these matches when the management command’s CSV is edited.
COUNTRIES = (
    (-101, "Argentina", "7006477", "Q414", "RA"),
    (-102, "Australia", "7000490", "Q408", "AUS"),
    (-103, "Austria", "1000062", "Q40", "A"),
    (-104, "Belgium", "1000063", "Q31", "B"),
    (-105, "Brazil", "1000047", "Q155", "BR"),
    (-106, "Canada", "7005685", "Q16", "CDN", "CA", "CAN"),
    (-107, "China", "1000111", "Q148", "CN", "CHN", "People's Republic of China"),
    (-108, "Croatia", "7006663", "Q224", "HR"),
    (-109, "Czech Republic", "1001780", "Q213", "CZ", "Czechia"),
    (-110, "Denmark", "1000066", "Q35", "DK"),
    (-111, "Ecuador", "1000051", "Q736", "EC"),
    (-112, "Finland", "1000069", "Q33", "FIN"),
    (-113, "France", "1000070", "Q142", "F"),
    (-114, "Germany", "7000084", "Q183", "D"),
    (-115, "Greece", "1000074", "Q41", "GR"),
    (-116, "Holy See", "7001168", "Q237", "V", "Vatican City", "Vatican"),
    (-117, "Hungary", "7006278", "Q28", "H"),
    (-118, "Ireland", "1000078", "Q27", "IRL"),
    (-119, "Italy", "1000080", "Q38", "I"),
    (-120, "Japan", "1000120", "Q17", "J"),
    (-121, "Netherlands", "7016845", "Q55", "NL", "The Netherlands"),
    (-122, "New Zealand", "1000226", "Q664", "NZ"),
    (-123, "Norway", "1000088", "Q20", "N"),
    (-124, "Poland", "7006366", "Q36", "PL"),
    (-125, "Portugal", "1000090", "Q45", "P"),
    (-126, "Romania", "1000091", "Q218", "RO"),
    (-127, "Slovakia", "7011765", "Q214", "SK"),
    (-128, "Slovenia", "7006670", "Q215", "SI"),
    (-129, "South Africa", "1000193", "Q258", "ZA"),
    (-130, "Spain", "1000095", "Q29", "E"),
    (-131, "Sweden", "1000097", "Q34", "S"),
    (-132, "Switzerland", "7011731", "Q39", "CH"),
    (-133, "Taiwan", "1000141", "Q865", "RC"),
    (-134, "Turkey", "1000144", "Q43", "TR", "Türkiye"),
    (
        -135,
        "United Kingdom",
        "7008591",
        "Q145",
        "GB",
        "UK",
        "U.K.",
        "GBR",
        "Great Britain",
    ),
    (-136, "United States", "7012149", "Q30", "US", "USA", "United States of America"),
)
NAMES = {pk: name for pk, name, *_ in COUNTRIES}
IDS_BY_LABEL = {
    label.casefold(): pk
    for pk, name, _, _, *aliases in COUNTRIES
    for label in (name, *aliases)
}
_BY_GETTY = {getty_id: pk for pk, _, getty_id, *_ in COUNTRIES}
COUNTRY_BY_WIKIDATA = {qid: pk for pk, _, _, qid, *_ in COUNTRIES}


def catalogue_ids(labels, authorities):
    normalized = {label.strip().casefold() for label in labels}
    ids = {IDS_BY_LABEL[label] for label in normalized if label in IDS_BY_LABEL}
    for key, index in (("getty_tgn", _BY_GETTY), ("wikidata", COUNTRY_BY_WIKIDATA)):
        pk = index.get(authorities.get(key))
        if pk is not None:
            ids.add(pk)
    return ids
