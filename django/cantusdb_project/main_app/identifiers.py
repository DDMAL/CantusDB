class ExternalIdentifiers:
    RISM = 1
    VIAF = 2
    WIKIDATA = 3
    GND = 4
    BNF = 5
    LC = 6
    DIAMM = 7


IDENTIFIER_TYPES = (
    (ExternalIdentifiers.RISM, "RISM Online"),
    (ExternalIdentifiers.VIAF, "VIAF"),
    (ExternalIdentifiers.WIKIDATA, "Wikidata"),
    (ExternalIdentifiers.GND, "GND (Gemeinsame Normdatei)"),
    (ExternalIdentifiers.BNF, "Bibliothèque national de France"),
    (ExternalIdentifiers.LC, "Library of Congress"),
    (ExternalIdentifiers.DIAMM, "Digital Image Archive of Medieval Music"),
)

TYPE_PREFIX = {
    ExternalIdentifiers.RISM: ("rism", "https://rism.online/"),
    ExternalIdentifiers.VIAF: ("viaf", "https://viaf.org/viaf/"),
    ExternalIdentifiers.WIKIDATA: ("wkp", "https://www.wikidata.org/wiki/"),
    ExternalIdentifiers.GND: ("dnb", "https://d-nb.info/gnd/"),
    ExternalIdentifiers.BNF: ("bnf", "https://catalogue.bnf.fr/ark:/12148/cb"),
    ExternalIdentifiers.LC: ("lc", "https://id.loc.gov/authorities/"),
    ExternalIdentifiers.DIAMM: ("diamm", "https://www.diamm.ac.uk/"),
}
