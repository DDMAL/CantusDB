# Institution countries

Institutions share country records. In the Django admin, open **Countries** to
add a country or correct its name. Add alternate spellings, translations, and
RISM country codes under **Aliases**, one per line. When renaming a country,
keep the former name as an alias if old search links or imports use it.
Institution forms, imports, and search use the same records. If an import
reports an unrecognized country, add the country or its alias and rerun the import.

The Getty TGN ID is optional. Enter the numeric ID to link the country on
institution pages. Migration 0047 includes names and IDs for countries found
in Cantus data and legacy import mappings, reconciled with the
[Getty Thesaurus of Geographic Names](https://www.getty.edu/research-conservation/tools-databases/vocabularies/tgn/)
on 2026-11-15. Getty data is provided by the J. Paul Getty Trust, Getty
Research Institute under the [ODC Attribution License](https://opendatacommons.org/licenses/by/1-0/).

The migration creates one country per distinct institution country, combining
known aliases such as USA and United States. It preserves other current names
as local countries. Unknown and Not recorded remain separate choices.
Institution revisions use the same records. A known country used only in a
revision is retained for recovery. Unmatched historical text becomes Unknown.

If a development installation ran the earlier draft of 0047 that imported
the full Getty catalogue, roll it back with that draft's code using
`python manage.py migrate main_app 0046` before switching to this revision.

Deploy code and schema together during a short maintenance window: pause public
requests and background jobs, install the new code, run `python manage.py migrate`
with that code, then resume traffic and jobs. The normal application-update playbook
does not run migrations. The old code requires the text column; the new code requires
the foreign-key column. Any page or job that loads an institution needs matching
code and schema, including Browse Sources, source detail/edit pages, the admin,
autocomplete and scheduled data checks. Follow the normal develop → staging → production release
process, including testing the migration on staging.

The infrastructure repository provides `nginx_conf_temp_maintenance.j2` for the
maintenance page. Keep that configuration active and keep `celery-worker` and
`celery-beat` stopped while updating/restarting only Django and applying the migration.
Do not use the ordinary update playbook for that intermediate step: it restarts the
workers too. Its Django health check only opens TCP port 8000 and does not verify the
schema. After migration and checks succeed, restore/reload the normal nginx
configuration and resume the workers and scheduler.

For rollback, pause traffic and jobs again, use the new code to run
`python manage.py migrate main_app 0046`, then restore the previous code before
resuming. Rollback restores the selected country names as text,
including countries added or corrected in the admin. Not recorded becomes
the old `[No Country]` default. Original spellings cannot be recovered.
