# Text field cleanup (#1585)

Missing values use `""`, with `blank=True` retained for optional form fields.
Migrations 0045 and 0046 normalize existing data and then add `NOT NULL` for:

- Chant and Sequence: manuscript full text, standardized and syllabized full
  text, image link, indexing notes, Volpiano, Volpiano notes and intervals.
- Source: description, selected bibliography and summary.

This covers the fields reported in #1585 and the associated syllabized text.
Other nullable text fields, identifiers, JSON and nullable proofreading flags
are unchanged and need separate consideration before conversion.

Chant text and melody fields lose only surrounding whitespace; interior spaces
and line breaks remain. Whitespace-only values become `""`. Populated indexing
notes and source prose retain their exact formatting, including indentation and
trailing spaces used by Markdown. Existing URL normalization is retained.

Ordinary model saves and literal ORM updates/bulk operations normalize new
values. SQL expressions and raw SQL bypass Python normalization, although the
database rejects NULL for these columns. Code writing such expressions must
provide normalized strings. Empty melodies are excluded from melody searches,
concordances and the JSON melody export. JSON keys and access rules stay the
same; missing values in the affected fields are now empty strings instead of
sometimes JSON `null`. CSV missing values remain empty cells.

## Deployment and recovery

1. Back up the database and verify that it can be restored. Keep that backup
   until the cleanup has been checked. Stop application and background writers
   for the migration window.
2. Deploy through the normal develop → staging → production release process.
   Run `python manage.py migrate` in the appropriate deployment environment.
   Migrations do not run automatically.
3. Check text search, melody filters and source melody counts before restarting
   writers. Test on staging before a production release.

0045 scans Chant, Sequence and Source using primary-key batches of 500, updating
only changed records. It runs in one database transaction; batching bounds Python
memory, but does not shorten the transaction or release its locks. Allow time
and database/WAL space for large tables. 0046 adds the constraints separately,
after the data transaction commits. Measure the migration on a restored database
of representative size before scheduling production; local regression tests do
not establish production runtime.

The cleanup does not call application save signals or create per-record
django-reversion revisions. It preserves editorial timestamps, attribution,
curated incipits and existing revision history. It explicitly recalculates
derived melody fields when trimming a melody, clears them when no melody remains,
and refreshes the existing Chant-only source melody counts. Trimming surrounding
whitespace does not change the words in the full-text search vectors.

Reversing to migration 0044 restores nullable columns but deliberately leaves
normalized data in place. Original NULL values and removed whitespace cannot be
reconstructed from the cleaned values. Exact recovery requires the database
backup; restoring it also discards later changes, so decide rollback before
reopening editing. Existing revisions are not a complete cleanup backup.

No cleanup should be run against staging or production by a local agent. Local
migration tests use a disposable test database.
