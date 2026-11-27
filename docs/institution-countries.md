# Institution countries

For the first upgrade of a database with institution records,
pause writes and background jobs. Run these commands in order with the new code:

```bash
python manage.py migrate main_app 0048_create_country
python manage.py load_countries
python manage.py migrate
```

The first migration creates the country table. The command loads the catalogue
from [countries.csv](../django/cantusdb_project/countries.csv). The second
migration uses the stored names, aliases and RISM codes to link live institutions
to countries, then removes the old text field. These steps
work offline. Use this sequence for a restored database that predates the
country table too. On an empty database, you can run `migrate` followed by
`load_countries`. On an already upgraded database, use the normal `migrate`
command and rerun the loader when the catalogue changes.

If a name in a live institution cannot be matched, the conversion
reports it and rolls back. Add the spelling as an alias on the appropriate
country, or create a country for a genuine local entry, then rerun `migrate`.
Blank values and `[No Country]` become blank. An explicit `Unknown` or
`[Unknown Country]` retains the separate “Unknown” entry.

The migration leaves saved revisions intact. When you open a legacy revision in
the admin, the form shows the country text as originally entered and selects
the matching country for restoration. If a historical spelling has no unique
match, correct the country or its aliases and reopen the revision. This also
applies when recovering a deleted institution.

Catalogue IDs are permanent. Keep each country's ID when editing the CSV.
The loader accepts new positive IDs, fills missing values, and preserves populated
fields. If an ID is occupied, the loader checks for a matching name, alias,
RISM code or an ID from the same authority before filling missing values. Resolve conflicts
before retrying. Countries added in Django admin receive a database-generated ID.

Store authority IDs in the CSV and in the admin, for example
`{"Getty TGN": "7005685", "Wikidata": "Q16"}` for Canada. The admin builds
links for Getty TGN, Wikidata and GeoNames. Other authorities can store a
local identifier. Repeated aliases keep their first spelling, ignoring case
and surrounding whitespace.

If a database used full authority URLs from an earlier draft, rerun
`load_countries` with the new code. It converts recognized record URLs on
catalogue and local countries. If a URL cannot be matched to its authority,
the command reports the country and value and rolls back. Correct the ID in
the country admin and rerun the command.

To roll back, run `python manage.py migrate main_app 0047` with this version
of the code. Live institutions regain the current display names, and
blank countries regain `[No Country]`. New revisions record the country ID
and the spelling at the time of the edit so that either schema can restore
them. Export country metadata first if you need to retain it.

If a local database applied the earlier draft that rewrote revision data,
use a backup from before that migration to recover the original spellings.

The catalogue uses Getty Thesaurus of Geographic Names data from the J. Paul
Getty Trust, Getty Research Institute, under the Open Data Commons Attribution
License. [Getty TGN](https://www.getty.edu/research/tools/vocabularies/tgn/) · [License](https://opendatacommons.org/licenses/by/1-0/)

RISM codes identify countries in library sigla. [RISM Library Sigla](https://rism.info/fileadmin/content/site-content/BIBVERZ_2008_10.pdf#page=179)
