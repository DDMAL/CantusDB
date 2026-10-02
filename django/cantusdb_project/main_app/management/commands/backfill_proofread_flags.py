from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Count, Q, QuerySet

from main_app.models import Chant, Sequence

# (report label, proofread flag, field whose content the flag vouches for)
PROOFREAD_FIELDS = [
    ("volpiano", "volpiano_proofread", "volpiano"),
    ("ms_full_text", "manuscript_full_text_proofread", "manuscript_full_text"),
    (
        "ms_std_spelling",
        "manuscript_full_text_std_proofread",
        "manuscript_full_text_std_spelling",
    ),
]


def unproofread_with_content(flag: str, field: str) -> Q:
    """Chants or sequences that have content in `field` but whose `flag` is not ticked."""
    return (
        Q(**{f"{field}__isnull": False})
        & ~Q(**{field: ""})
        & (Q(**{flag: False}) | Q(**{f"{flag}__isnull": True}))
    )


class Command(BaseCommand):
    help = (
        "Mark the volpiano, MS full text and MS standardized spelling of chants and "
        "sequences in published sources as proofread. This content is already public and was "
        "checked before the proofread checkboxes existed, so ticking them keeps it "
        "public once unproofread fields are hidden (#1100). Only fields that have "
        "content are ticked, so anything added later still starts unproofread. "
        "Writes with a bulk update, so no signals fire and no revisions are recorded."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would change without writing anything.",
        )
        parser.add_argument(
            "--exclude",
            nargs="+",
            type=int,
            default=[],
            metavar="SOURCE_ID",
            help="IDs of published sources whose content has not been proofread.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        querysets = [
            model.objects.filter(source__published=True).exclude(
                source_id__in=options["exclude"]
            )
            for model in (Chant, Sequence)
        ]

        for queryset in querysets:
            self.report(queryset)

        if dry_run:
            self.stdout.write(self.style.WARNING("Dry run: nothing was written."))
            return

        with transaction.atomic():
            for queryset in querysets:
                name = queryset.model.get_verbose_name_plural()
                for _, flag, field in PROOFREAD_FIELDS:
                    updated = queryset.filter(
                        unproofread_with_content(flag, field)
                    ).update(**{flag: True})
                    self.stdout.write(
                        self.style.SUCCESS(f"Set {flag} on {updated} {name}.")
                    )

    def report(self, queryset: QuerySet[Chant] | QuerySet[Sequence]) -> None:
        """Print, per source, how many records each flag would be ticked on."""
        labels = [label for label, _, _ in PROOFREAD_FIELDS]
        rows = (
            queryset.values("source_id")
            .annotate(
                **{
                    label: Count("id", filter=unproofread_with_content(flag, field))
                    for label, flag, field in PROOFREAD_FIELDS
                }
            )
            .order_by("source_id")
        )
        totals = dict.fromkeys(labels, 0)
        self.stdout.write(queryset.model.get_verbose_name_plural().capitalize())
        self.stdout.write("\t".join(["source_id", *labels]))
        for row in rows:
            if not any(row[label] for label in labels):
                continue
            self.stdout.write(
                "\t".join(str(row[key]) for key in ["source_id", *labels])
            )
            for label in labels:
                totals[label] += row[label]
        self.stdout.write(
            "\t".join(["Total", *(str(totals[label]) for label in labels)])
        )
