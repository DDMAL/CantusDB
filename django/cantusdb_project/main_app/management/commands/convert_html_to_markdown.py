"""
Converts legacy raw-HTML content in Source.description / Source.selected_bibliography
into markdown, writing the result into the `description_markdown_draft` /
`selected_bibliography_markdown_draft` staging fields for review (#1239).

Fields with no HTML are copied over unchanged (nothing to convert). Fields
with HTML are run through `main_app.html_to_markdown.html_to_markdown`; the
*output* is re-checked with `contains_html_tags` and any residual HTML is
flagged as needing manual review rather than silently written.

Dry-run by default -- pass --apply to actually write the draft fields.
"""

from django.core.management.base import BaseCommand

from main_app.html_to_markdown import html_to_markdown
from main_app.models import Source
from main_app.templatetags.helper_tags import contains_html_tags

FIELDS = ["description", "selected_bibliography"]
DRAFT_SUFFIX = "_markdown_draft"


def describe(source):
    return (
        f"  id={source.id}  siglum={source.siglum or '-'}  "
        f"shelfmark={source.shelfmark or '-'}  title={source.title or '-'}"
    )


class Command(BaseCommand):
    help = (
        "Convert legacy HTML in Source.description/selected_bibliography to "
        "markdown, writing into the *_markdown_draft staging fields for "
        "review before promotion (#1239). Dry-run by default."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Actually write the draft fields (default is dry-run/report only).",
        )

    def handle(self, *args, **options):
        apply_changes = options["apply"]
        sources = Source.objects.all().only(
            "id", "siglum", "shelfmark", "title", *FIELDS
        )

        already_clean = {field: [] for field in FIELDS}
        converted = {field: [] for field in FIELDS}
        needs_review = {field: [] for field in FIELDS}
        blank = {field: [] for field in FIELDS}

        to_save = []
        for source in sources:
            touched = False
            for field in FIELDS:
                value = getattr(source, field)
                draft_field = field + DRAFT_SUFFIX

                if not value or not value.strip():
                    blank[field].append(source)
                    continue

                if not contains_html_tags(value):
                    already_clean[field].append(source)
                    draft = value
                else:
                    draft = html_to_markdown(value)
                    if contains_html_tags(draft):
                        needs_review[field].append(source)
                    else:
                        converted[field].append(source)

                if apply_changes:
                    setattr(source, draft_field, draft)
                    touched = True

            if touched:
                to_save.append(source)

        if apply_changes:
            Source.objects.bulk_update(
                to_save,
                [f + DRAFT_SUFFIX for f in FIELDS],
                batch_size=200,
            )

        for field in FIELDS:
            self.stdout.write(self.style.SUCCESS(f"\n=== {field.upper()} ==="))
            self.stdout.write(
                f"  already clean (copied as-is): {len(already_clean[field])}\n"
                f"  converted cleanly: {len(converted[field])}\n"
                f"  needs manual review (residual HTML after conversion): "
                f"{len(needs_review[field])}\n"
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
                self.style.SUCCESS(f"\nWrote draft fields for {len(to_save)} sources.")
            )
        else:
            self.stdout.write(
                self.style.WARNING(
                    "\nDry run only -- no changes written. Pass --apply to write "
                    "the *_markdown_draft fields."
                )
            )
