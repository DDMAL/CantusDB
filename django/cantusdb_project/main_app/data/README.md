# Institution countries

Institutions and their saved revisions refer to countries by their Cantus IDs.
The curated countries have fixed negative IDs. The database allocates positive
IDs to local additions. An administrator can rename a country without breaking
references to it. The Canadian Chant Database uses Canada's fixed ID.

## Database setup

Run `python manage.py migrate` on a new database or a restored backup. During
an upgrade, the migration creates the country rows needed to convert existing
institutions and their saved revisions. A database already on the previous PR
version of `0048_getty_countries` can migrate directly to
the latest migration. Existing Getty IDs and name edits carry over.
`0050_reconcile_wikidata_country_ids` also moves previously entered
Wikidata-only countries to their stable IDs. If the loader already created
the same country, its display name is retained, the other name becomes an
alias, and both institutions and saved revisions follow the stable ID.
Conflicting authority IDs stop the migration and identify the rows to correct.

To install the complete curated Cantus list, run
`python manage.py load_countries` after migrating. This command uses a small
local catalogue of countries from Cantus holdings and legacy imports. It adds
missing records with their aliases and verified Getty and Wikidata IDs. Rerunning it keeps
existing records, including edits to display names, aliases and authority IDs.
The migration and loader work offline.

Rolling back to `0048_getty_countries` restores the Getty ID column. Export
any additional authority IDs you want to keep before rolling back, because
that schema can represent only Getty. Rolling back further to
`0047_notation_clavis_sequentiarum_labels` writes the countries' current
display names back to institutions and revisions.

## Authority identifiers

In the Country admin, enter optional external identifiers as a JSON object,
such as `{"getty_tgn": "7005685", "wikidata": "Q16"}` for Canada. Enter the IDs
as strings. A Getty TGN ID contains digits and a Wikidata item ID starts with
`Q`. Each identifier belongs to one country within its authority. Both links
appear on the institution detail page when both IDs are recorded. A known
Wikidata ID alone also identifies a curated country. For example, entering
`Q16` with a local display name assigns Canada's stable ID.

The 36 Wikidata matches were checked against the catalogue's Getty IDs using
Wikidata's Getty Thesaurus of Geographic Names ID property. The match for
Getty `7001168` is the geographical entity Vatican City (`Q237`), listed as
Holy See in the Cantus catalogue. [Wikidata property P1667](https://www.wikidata.org/wiki/Property:P1667)

The initial catalogue uses preferred names and numeric identifiers from the
Getty Thesaurus of Geographic Names, checked on 2026-11-15. The J. Paul Getty
Trust, Getty Research Institute makes this data available under the Open Data
Commons Attribution License. [Getty TGN](https://www.getty.edu/research-conservation/tools-databases/vocabularies/tgn/) · [ODC Attribution License](https://opendatacommons.org/licenses/by/1-0/)

Aliases include RISM country prefixes used in library sigla. For example,
`ZA` identifies South Africa and `RC` identifies Taiwan.
[RISM Library Sigla, p. 179](https://rism.info/fileadmin/content/site-content/BIBVERZ_2008_10.pdf#page=179) · [RISM Online country list](https://rism.online/countries/list)
