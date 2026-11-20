"""Wikidata P1667 matches for the curated Cantus countries, frozen for migration 0050."""

from main_app.data.countries_v1 import matching_ids

# Keys are stable Cantus country IDs. Each item was verified against its Getty TGN ID.
WIKIDATA_BY_COUNTRY = {
    -101: "Q414",  # Argentina
    -102: "Q408",  # Australia
    -103: "Q40",  # Austria
    -104: "Q31",  # Belgium
    -105: "Q155",  # Brazil
    -106: "Q16",  # Canada
    -107: "Q148",  # China
    -108: "Q224",  # Croatia
    -109: "Q213",  # Czech Republic
    -110: "Q35",  # Denmark
    -111: "Q736",  # Ecuador
    -112: "Q33",  # Finland
    -113: "Q142",  # France
    -114: "Q183",  # Germany
    -115: "Q41",  # Greece
    -116: "Q237",  # Holy See
    -117: "Q28",  # Hungary
    -118: "Q27",  # Ireland
    -119: "Q38",  # Italy
    -120: "Q17",  # Japan
    -121: "Q55",  # Netherlands
    -122: "Q664",  # New Zealand
    -123: "Q20",  # Norway
    -124: "Q36",  # Poland
    -125: "Q45",  # Portugal
    -126: "Q218",  # Romania
    -127: "Q214",  # Slovakia
    -128: "Q215",  # Slovenia
    -129: "Q258",  # South Africa
    -130: "Q29",  # Spain
    -131: "Q34",  # Sweden
    -132: "Q39",  # Switzerland
    -133: "Q865",  # Taiwan
    -134: "Q43",  # Turkey
    -135: "Q145",  # United Kingdom
    -136: "Q30",  # United States
}
COUNTRY_BY_WIKIDATA = {qid: pk for pk, qid in WIKIDATA_BY_COUNTRY.items()}


def catalogue_ids(labels, authorities):
    ids = matching_ids(labels, authorities.get("getty_tgn"))
    wikidata_pk = COUNTRY_BY_WIKIDATA.get(authorities.get("wikidata"))
    if wikidata_pk is not None:
        ids.add(wikidata_pk)
    return ids
