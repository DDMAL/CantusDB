# Institution countries

Institutions and their saved revisions refer to countries by their Cantus IDs.
The original 36 countries have fixed positive IDs, assigned once in the
catalogue's original alphabetical order. Argentina is 1 and Canada is 6.
“Not recorded” is 37 and “Unknown” is 38. The database allocates new local
IDs starting at 39, even before the catalogue is loaded. Renaming or
reordering countries leaves their IDs intact. The Canadian Chant Database
uses Canada's fixed ID to find holdings.

## Database setup

Run `python manage.py migrate`, then `python manage.py load_countries`.
Both commands work offline.

On a fresh upgrade, Django applies one country migration,
`0048_squashed_0053_institution_countries`. It creates the two missing-value
choices and the countries needed by existing institutions and saved revisions.
It uses the catalogue to recognize old spellings and assign stable IDs. It
retains alternate spellings found in those records. An empty database has
only the two missing-value choices after migration.

The management command loads the 36 curated countries. Its first run for each
country fills missing Getty and Wikidata IDs and adds catalogue aliases,
preserving existing names, alias spellings, and authority values. It records
that the country has been loaded. Later runs preserve deletions as well as
edits. Databases upgraded from earlier PR versions have no record of earlier
loader runs. Their first run of the updated command can therefore restore a
previously removed catalogue alias or identifier.

Databases partway through an earlier PR migration can also run the two
commands above. Django finishes the original chain in place. This preserves
local edits and moves institutions and saved revisions to the stable IDs when
earlier versions created duplicate countries. Conflicting authority IDs stop
the migration and identify the rows to correct.

On databases using the earlier negative IDs, `0053_positive_country_ids`
updates the institutions, their saved revisions, and country admin history.
A local record occupying one of the 38 reserved IDs moves to a new local ID
with its references. Bookmarks for these displaced local records need their
new URLs. Other local records keep their IDs. Old negative catalogue URLs
redirect to their positive URLs. When rolling back this step,
relocated local countries retain their newly allocated positive IDs.

The original migration files remain available for these partial upgrades.
`_institution_country_versions.py` is a helper used by migration code to
translate the country field in saved institution revisions. Django skips
files beginning with an underscore when discovering migration steps.

Rolling back to `0048_getty_countries` restores the Getty ID column. Export
any additional authority IDs you want to keep before rolling back, because
that schema can represent only Getty. Rolling back further to
`0047_notation_clavis_sequentiarum_labels` writes the countries' current
display names back to institutions and revisions.

## Authority identifiers

In the Country admin, enter a database name and the full HTTP or HTTPS URL
of its record. For example, Canada's entry can include
`{"GeoNames": "https://www.geonames.org/6251999/"}`. On an institution
page, selecting the country name opens its Cantus country page. This page
lists the external records and links to the country data credits in its
footer. Links identifying the institution itself appear on the institution
page. Each external country
record URL can belong to one country.

Getty TGN and Wikidata also accept compact identifiers, such as
`{"getty_tgn": "7005685", "wikidata": "Q16"}` for Canada. Those entries can
be combined with full links to other databases. A known Wikidata ID alone
also identifies a curated country. For example, entering `Q16` with a local
display name assigns Canada's stable ID. Rolling back to `0050` leaves the
links in the database. The older country editor accepts only Getty TGN and
Wikidata on save.

The 36 Wikidata matches were checked against the catalogue's Getty IDs using
Wikidata's Getty Thesaurus of Geographic Names ID property. The match for
Getty `7001168` is the geographical entity Vatican City (`Q237`), listed as
Holy See in the Cantus catalogue. [Wikidata property P1667](https://www.wikidata.org/wiki/Property:P1667)

The initial catalogue uses preferred names and numeric identifiers from the
Getty Thesaurus of Geographic Names, checked on 2026-11-15. The J. Paul Getty
Trust, Getty Research Institute makes this data available under the Open Data
Commons Attribution License. [Getty TGN](https://www.getty.edu/research/tools/vocabularies/tgn/) · [ODC Attribution License](https://opendatacommons.org/licenses/by/1-0/)

Aliases include RISM country prefixes used in library sigla. For example,
`ZA` identifies South Africa and `RC` identifies Taiwan.
[RISM Library Sigla, p. 179](https://rism.info/fileadmin/content/site-content/BIBVERZ_2008_10.pdf#page=179) · [RISM Online country list](https://rism.online/countries/list)
