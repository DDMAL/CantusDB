# Institution countries

For the first upgrade of a database with institution records or saved revisions,
pause writes and background jobs. Run these commands in order with the new code:

```bash
python manage.py migrate main_app 0048_create_country
python manage.py load_countries
python manage.py migrate
```

The first migration creates the country table. The command loads the catalogue
from [countries.csv](../django/cantusdb_project/countries.csv). The second
migration uses the stored names, aliases and RISM codes to link institutions
and saved revisions to countries, then removes the old text field. These steps
work offline. Use this sequence for a restored database that predates the
country table too. On an empty database, you can run `migrate` followed by
`load_countries`. On an already upgraded database, use the normal `migrate`
command and rerun the loader when the catalogue changes.

If a name in an institution or a revision cannot be matched, the conversion
reports it and rolls back. Add the spelling as an alias on the appropriate
country, or create a country for a genuine local entry, then rerun `migrate`.
Blank values and `[No Country]` become blank. An explicit `Unknown` or
`[Unknown Country]` retains the separate “Unknown” entry.

Catalogue IDs are permanent. Keep each country's ID when editing the CSV.
The loader accepts new positive IDs, fills missing values, and preserves populated
fields. If an ID is occupied, the loader checks for a matching name, alias,
RISM code or authority URL before enriching the record. Resolve conflicts
before retrying. Countries added in Django admin receive a database-generated ID.

To roll back, run `python manage.py migrate main_app 0047` with this version
of the code. Institutions and revisions regain the current display names, and
blank countries regain `[No Country]`. Export country metadata first if you
need to retain it.

The catalogue uses Getty Thesaurus of Geographic Names data from the J. Paul
Getty Trust, Getty Research Institute, under the Open Data Commons Attribution
License. [Getty TGN](https://www.getty.edu/research/tools/vocabularies/tgn/) · [License](https://opendatacommons.org/licenses/by/1-0/)

RISM codes identify countries in library sigla. [RISM Library Sigla](https://rism.info/fileadmin/content/site-content/BIBVERZ_2008_10.pdf#page=179)
