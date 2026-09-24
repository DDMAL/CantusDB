"""
Converts legacy raw-HTML content in Source.description / Source.selected_bibliography
into markdown *in place*, backing the original HTML up into the
`description_html_legacy` / `selected_bibliography_html_legacy` columns first (#1239).

A non-null legacy column means "this field has been converted", and is the only
backup of the pre-conversion content -- see the notes on reversion below. The
command's guards exist to keep that column truthful: it is written exactly once,
at the moment the live field is overwritten.

Fields whose conversion leaves residual HTML are reported for manual review and
left untouched rather than half-converted; `source_detail.html` keeps rendering
those with the legacy `linebreaks` path via the `contains_html_tags` fallback.

Dry-run by default -- pass --apply to write. `--revert` undoes a conversion by
restoring the legacy column back into the live field.

Two things worth knowing about how this writes:

- It uses `bulk_update`, which does not call `save()`, so `date_updated`
  (`auto_now`) is not bumped. A bulk data conversion should not surface as an
  editorial edit in "recently updated" listings.
- `bulk_update` fires no signals, and management commands run outside
  `RevisionMiddleware`, so django-reversion records nothing for this change.
  The `*_html_legacy` column is the sole backup.
"""

from django.core.management.base import BaseCommand, CommandError

from main_app.html_to_markdown import html_to_markdown
from main_app.models import Source
from main_app.templatetags.helper_tags import contains_html_tags

FIELDS = ["description", "selected_bibliography"]
LEGACY_SUFFIX = "_html_legacy"


def describe(source):
    return (
        f"  id={source.id}  siglum={source.siglum or '-'}  "
        f"shelfmark={source.shelfmark or '-'}  title={source.title or '-'}"
    )


class Command(BaseCommand):
    help = (
        "Convert legacy HTML in Source.description/selected_bibliography to markdown "
        "in place, backing the original HTML up into the *_html_legacy columns "
        "(#1239). Dry-run by default; --revert restores from the backup."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Actually write the changes (default is dry-run/report only).",
        )
        parser.add_argument(
            "--revert",
            action="store_true",
            help=(
                "Restore the original HTML from the *_html_legacy columns back into "
                "the live fields, clearing the backup."
            ),
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help=(
                "Reconvert fields that have already been converted, re-running the "
                "converter over the HTML held in the *_html_legacy column. The backup "
                "itself is left as it is."
            ),
        )
        parser.add_argument(
            "--source-id",
            type=int,
            action="append",
            dest="source_ids",
            help=(
                "Limit to this source (repeatable), for spot-checking a few sources "
                "before running over everything."
            ),
        )

    def get_queryset(self, source_ids):
        fields = [f + LEGACY_SUFFIX for f in FIELDS]
        sources = Source.objects.all().only(
            "id", "siglum", "shelfmark", "title", *FIELDS, *fields
        )
        if source_ids:
            sources = sources.filter(id__in=source_ids)
            found = set(sources.values_list("id", flat=True))
            missing = sorted(set(source_ids) - found)
            if missing:
                raise CommandError(
                    f"No source with id {', '.join(str(i) for i in missing)}."
                )
        return sources

    def handle(self, *args, **options):
        if options["revert"]:
            if options["force"]:
                raise CommandError("--force does not apply to --revert.")
            return self.handle_revert(options)
        return self.handle_convert(options)

    def handle_convert(self, options):
        apply_changes = options["apply"]
        force = options["force"]
        sources = self.get_queryset(options["source_ids"])

        blank = {field: [] for field in FIELDS}
        already_markdown = {field: [] for field in FIELDS}
        already_converted = {field: [] for field in FIELDS}
        converted = {field: [] for field in FIELDS}
        needs_review = {field: [] for field in FIELDS}

        to_save = []
        for source in sources:
            touched = False
            for field in FIELDS:
                legacy_field = field + LEGACY_SUFFIX
                value = getattr(source, field)
                backup = getattr(source, legacy_field)

                if backup is not None:
                    # Already converted. Reconverting from `value` would overwrite the
                    # backup with markdown and lose the original HTML for good, so
                    # --force re-runs the converter over the backup instead.
                    if not force:
                        already_converted[field].append(source)
                        continue
                    value = backup
                elif not value or not value.strip():
                    blank[field].append(source)
                    continue
                elif not contains_html_tags(value):
                    # Already markdown. Leave the legacy column null -- null has to
                    # keep meaning "never converted".
                    already_markdown[field].append(source)
                    continue

                markdown = html_to_markdown(value)
                if contains_html_tags(markdown):
                    needs_review[field].append(source)
                    continue

                converted[field].append(source)
                if apply_changes:
                    if backup is None:
                        setattr(source, legacy_field, value)
                    setattr(source, field, markdown)
                    touched = True

            if touched:
                to_save.append(source)

        if apply_changes and to_save:
            Source.objects.bulk_update(
                to_save,
                FIELDS + [f + LEGACY_SUFFIX for f in FIELDS],
                batch_size=200,
            )

        for field in FIELDS:
            self.stdout.write(self.style.SUCCESS(f"\n=== {field.upper()} ==="))
            self.stdout.write(
                f"  converted: {len(converted[field])}\n"
                f"  needs manual review (residual HTML after conversion, "
                f"left untouched): {len(needs_review[field])}\n"
                f"  already markdown (no HTML, left alone): "
                f"{len(already_markdown[field])}\n"
                f"  already converted (skipped): {len(already_converted[field])}\n"
                f"  blank: {len(blank[field])}\n"
            )
            if needs_review[field]:
                self.stdout.write(
                    f"  -- NEEDS MANUAL REVIEW ({len(needs_review[field])}) --"
                )
                for source in needs_review[field]:
                    self.stdout.write(describe(source))
                self.stdout.write("")

        if apply_changes:
            self.stdout.write(
                self.style.SUCCESS(f"\nConverted fields on {len(to_save)} sources.")
            )
        else:
            self.stdout.write(
                self.style.WARNING(
                    "\nDry run only -- no changes written. Pass --apply to convert."
                )
            )

    def handle_revert(self, options):
        apply_changes = options["apply"]
        sources = self.get_queryset(options["source_ids"])

        reverted = {field: [] for field in FIELDS}

        to_save = []
        for source in sources:
            touched = False
            for field in FIELDS:
                legacy_field = field + LEGACY_SUFFIX
                backup = getattr(source, legacy_field)
                if backup is None:
                    continue

                reverted[field].append(source)
                if apply_changes:
                    setattr(source, field, backup)
                    setattr(source, legacy_field, None)
                    touched = True

            if touched:
                to_save.append(source)

        if apply_changes and to_save:
            Source.objects.bulk_update(
                to_save,
                FIELDS + [f + LEGACY_SUFFIX for f in FIELDS],
                batch_size=200,
            )

        for field in FIELDS:
            self.stdout.write(
                self.style.SUCCESS(
                    f"\n=== {field.upper()} ===\n"
                    f"  to restore from backup: {len(reverted[field])}"
                )
            )

        if apply_changes:
            self.stdout.write(
                self.style.SUCCESS(
                    f"\nRestored original HTML on {len(to_save)} sources."
                )
            )
        else:
            self.stdout.write(
                self.style.WARNING(
                    "\nDry run only -- no changes written. Pass --apply to revert."
                )
            )
