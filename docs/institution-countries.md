# Institution countries

Run `python manage.py migrate`, then `python manage.py load_countries` before
resuming writes or running an institution import. Both commands work offline.

The migration creates records only for countries referenced by institutions
or their saved revisions. A small, frozen list maps legacy spellings to the
original 36 Cantus IDs, including Canada at 6. Local countries receive IDs
starting at 37. An empty country or `[No Country]` becomes a blank field.
Explicitly unknown countries remain “Unknown”. Unrecognized text found only
in a revision also becomes “Unknown” so the revision can still be restored.

The management command reads [countries.csv](../django/cantusdb_project/countries.csv).
It adds missing countries, alternate names, RISM codes, and authority URLs.
Rerunning it preserves current names and populated values and restores missing
catalogue entries. The CSV accepts IDs 1 through 36. Add new countries in
Django admin. A country may have several authority records, each stored as a
full HTTP or HTTPS URL.

To roll back, run `python manage.py migrate main_app 0047` with this version
of the code. Institutions and revisions regain the current display names, and
blank countries regain `[No Country]`. Export country metadata first if you
need to retain it. For a local database that ran an earlier draft of this PR,
use the matching old checkout to roll back to the migration before countries
(0046 for the original 0047 draft, otherwise 0047) before upgrading.

The catalogue uses Getty Thesaurus of Geographic Names data from the J. Paul
Getty Trust, Getty Research Institute, under the Open Data Commons Attribution
License. [Getty TGN](https://www.getty.edu/research/tools/vocabularies/tgn/) · [License](https://opendatacommons.org/licenses/by/1-0/)

RISM codes identify countries in library sigla. [RISM Library Sigla](https://rism.info/fileadmin/content/site-content/BIBVERZ_2008_10.pdf#page=179)
