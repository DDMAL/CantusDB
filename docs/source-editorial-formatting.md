# One-time source formatting corrections

`repair_source_editorial_formatting` applies the editorial decisions made on
9 November 2026:

- Source **123619**: use **¹⁴C** once in Description and twice in Selected
  Bibliography. Unicode superscript digits preserve the notation through a
  later HTML-to-Markdown conversion.
- Source **714555**: italicize the Group G Cantus URL and separate it from its
  linked label with a space.

The command accepts the original HTML or the converted Markdown found in the
audited records. It replaces only the identified passages in the current fields,
preserving surrounding edits and the original `*_html_legacy` backups. It does
not change other groups, sources, table layout, timestamps or attribution.

Run any planned HTML-to-Markdown conversion first, then this repair. That order
keeps the original HTML in the conversion's legacy backups. After deploying the
code through the normal release process, preview the changes in the application's
management-command environment:

```sh
python manage.py repair_source_editorial_formatting
```

Inspect the displayed differences, then apply them explicitly:

```sh
python manage.py repair_source_editorial_formatting --apply
```

Both sources must exist. Unrecognized, missing or repeated passages stop the
command without applying any corrections; inspect the current content rather
than forcing a replacement. A rerun leaves already-corrected content unchanged.
Applying the command reads both sources under database row locks and commits the
field changes and revision history together.

The command creates revisions with the comments **Before source editorial
formatting repair** and **Restore radiocarbon superscripts and Ridgefield Group G
italics**. To undo a correction, recover the relevant text from the first revision.
Avoid reverting an entire source after subsequent editorial changes.

Verify all three radiocarbon references and the Group G link on the source pages
after applying the command. A later `convert_html_to_markdown --force` or
`--revert` can restore the old formatting from the unchanged legacy backups;
rerun this targeted repair afterward if these corrections should remain.
Merging this PR alone does not change stored data.
