# Institution countries

## Manual upgrade

For the first upgrade of a populated database, including a restored backup,
pause application writes and background jobs. Run these three commands yourself
with the new checkout, before restarting services or resuming the usual deployment:

```bash
python manage.py migrate main_app 0049_prepare_institution_countries
python manage.py load_countries
python manage.py migrate
```

1. Migration 0049 follows `0048_gabc_melody`. It creates the country table and
   a nullable link on each institution, keeping the original country in `country_text`.
2. The management command reads the bundled catalogue and loads its permanent IDs,
   names, aliases, RISM codes and authority IDs. [Country catalogue](../django/cantusdb_project/countries.csv)
3. Migration 0050 matches live country text against the loaded names, aliases and
   RISM codes. It reports all unmatched spellings before writing any links. If it
   stops, use the Django shell to add the missing spelling to the correct country's
   aliases, or create a country for a genuine local entry. Rerun `python manage.py migrate`.
   Migration 0051 removes the old text column once the conversion succeeds.

Blank values, `[No Country]` and `Not recorded` become empty links. The catalogue
reserves ID 37 for both `Unknown` and `[Unknown Country]`, including when those
spellings occur only in revision history.

On an empty database, run `python manage.py migrate` and then
`python manage.py load_countries`. On subsequent upgrades, run the loader manually
when the catalogue changes. The legacy institution rebuild commands are separate
from this upgrade.

## Revisions and catalogue edits

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

## Rollback

Export country metadata you need to keep. With this version of the code, run
`python manage.py migrate main_app 0048_gabc_melody` before switching back
to the previous release. Live institutions regain the current country names,
and empty links become `[No Country]`. New institution revisions retain both the
country ID and the spelling at the time of the edit so either release can restore
them.

For a local database running an unpublished draft, use its matching checkout to
reverse its country migrations before switching to this version. The original
`0047_getty_countries` draft rolls back to 0046. Drafts that started with
`0048_create_country` roll back to `0047_notation_clavis_sequentiarum_labels`.
If a draft rewrote saved revisions, a backup from before that migration preserves
their original spelling.

The catalogue uses Getty Thesaurus of Geographic Names data from the J. Paul
Getty Trust, Getty Research Institute, under the Open Data Commons Attribution
License. [Getty TGN](https://www.getty.edu/research/tools/vocabularies/tgn/) · [License](https://opendatacommons.org/licenses/by/1-0/)

RISM codes identify countries in library sigla. [RISM Library Sigla](https://rism.info/fileadmin/content/site-content/BIBVERZ_2008_10.pdf#page=179)
