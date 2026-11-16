# Country catalogue

`countries_20261115.json` contains Getty TGN preferred English names and identifiers
retrieved on 2026-11-15, plus CantusDB's separate Unknown and Not recorded entries.
It includes 195 current nations returned by the Getty nation search. Historical
nations (including Pandya) and results whose preferred type is not nation were
excluded. Getty marks Germany as both current and historical; it is included.
This is a geographic vocabulary, not a statement about recognition or sovereignty.

Sources:

- https://www.getty.edu/vow/TGNServlet?english=Y&find=&place=nation&nation=&page=1
  (all nine pages)
- Each record's full display, for example:
  https://www.getty.edu/vow/TGNFullDisplay?english=Y&find=&nation=&place=&subjectid=7012149
- https://www.getty.edu/research-conservation/tools-databases/vocabularies/data-services/

Names use the record's English-Preferred flag, even when the name differs from
common modern usage (for example Holy See and Czech Republic). Aliases include
current English names and alphabetic country codes; ambiguous aliases are omitted.
The two bracketed legacy missing-value labels are CantusDB aliases.

Contains information from the J. Paul Getty Trust, Getty Research Institute,
Getty Thesaurus of Geographic Names, which is made available under the
[ODC Attribution License](https://opendatacommons.org/licenses/by/1-0/).

The catalogue is local so institution editing and migration work without network
access. It is read-only in the admin. To add a newly represented territory or update
a Getty name, verify the record with Getty and add a reviewed data migration and
a new dated catalogue. Keep this file unchanged: migration 0047 uses it for recovery.

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
resuming. Reverting code alone does not restore the old column. If forward migration
rejects an unrecognized country, the transaction leaves the old schema intact;
restore the previous code before reopening the site and reconcile the reported rows
there before retrying.

Migration 0047 preserves original country
text and converts institution revision history. Unrecognized current countries
stop the migration with institution IDs; reconcile those before retrying.
Unrecognized historical values become Unknown, with their exact text preserved
in the read-only original-country field. Reversing the migration restores original
text unless an editor has since selected a different country; in that case it
retains the selected country's name. New institutions left at Not recorded return
to the old `[No Country]` default on reversal. The retired US cleanup command is
unnecessary.
