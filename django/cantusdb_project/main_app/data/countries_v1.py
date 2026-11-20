"""Frozen country identities for the institution country conversion and initial import.

Earlier PR migrations used negative keys. Keep this snapshot fixed so existing
databases can upgrade. The current public IDs are defined in countries_v2.
"""

CANADA_ID = -106

# Stable Cantus ID, preferred name, verified Getty TGN ID, then aliases / RISM sigla.
COUNTRIES = (
    (-101, "Argentina", "7006477", "RA"),
    (-102, "Australia", "7000490", "AUS"),
    (-103, "Austria", "1000062", "A"),
    (-104, "Belgium", "1000063", "B"),
    (-105, "Brazil", "1000047", "BR"),
    (CANADA_ID, "Canada", "7005685", "CDN", "CA", "CAN"),
    (-107, "China", "1000111", "CN", "CHN", "People's Republic of China"),
    (-108, "Croatia", "7006663", "HR"),
    (-109, "Czech Republic", "1001780", "CZ", "Czechia"),
    (-110, "Denmark", "1000066", "DK"),
    (-111, "Ecuador", "1000051", "EC"),
    (-112, "Finland", "1000069", "FIN"),
    (-113, "France", "1000070", "F"),
    (-114, "Germany", "7000084", "D"),
    (-115, "Greece", "1000074", "GR"),
    (-116, "Holy See", "7001168", "V", "Vatican City", "Vatican"),
    (-117, "Hungary", "7006278", "H"),
    (-118, "Ireland", "1000078", "IRL"),
    (-119, "Italy", "1000080", "I"),
    (-120, "Japan", "1000120", "J"),
    (-121, "Netherlands", "7016845", "NL", "The Netherlands"),
    (-122, "New Zealand", "1000226", "NZ"),
    (-123, "Norway", "1000088", "N"),
    (-124, "Poland", "7006366", "PL"),
    (-125, "Portugal", "1000090", "P"),
    (-126, "Romania", "1000091", "RO"),
    (-127, "Slovakia", "7011765", "SK"),
    (-128, "Slovenia", "7006670", "SI"),
    (-129, "South Africa", "1000193", "ZA"),
    (-130, "Spain", "1000095", "E"),
    (-131, "Sweden", "1000097", "S"),
    (-132, "Switzerland", "7011731", "CH"),
    (-133, "Taiwan", "1000141", "RC"),
    (-134, "Turkey", "1000144", "TR", "Türkiye"),
    (-135, "United Kingdom", "7008591", "GB", "UK", "U.K.", "GBR", "Great Britain"),
    (-136, "United States", "7012149", "US", "USA", "United States of America"),
)


IDS_BY_LABEL = {
    label.casefold(): pk
    for pk, name, _, *aliases in COUNTRIES
    for label in (name, *aliases)
}
_IDS_BY_GETTY = {getty_id: pk for pk, _, getty_id, *_ in COUNTRIES}


def matching_ids(labels, getty_id):
    normalized = {label.strip().casefold() for label in labels}
    matches = {IDS_BY_LABEL[label] for label in normalized if label in IDS_BY_LABEL}
    if getty_id in _IDS_BY_GETTY:
        matches.add(_IDS_BY_GETTY[getty_id])
    return matches
