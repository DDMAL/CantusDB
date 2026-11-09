"""Apply the agreed formatting corrections to sources 123619 and 714555.

This one-time repair accepts the original HTML and the converted Markdown seen
in the production/staging audit. It changes only recognized passages in current
fields, never reconstructing a field from its legacy backup. Dry-run by default.
"""

from argparse import ArgumentParser
from difflib import unified_diff
from typing import Any

import reversion
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from main_app.models import Source


def replace_once(value: str, originals: tuple[str, ...], corrected: str) -> str:
    """Require one known original or corrected passage; reject changed wording."""
    if sum(value.count(text) for text in (*originals, corrected)) != 1:
        raise ValueError(f"Expected one recognized occurrence of {corrected!r}.")
    for original in originals:
        value = value.replace(original, corrected, 1)
    return value


def repair_radiocarbon(value: str, suffixes: tuple[str, ...]) -> str:
    for suffix in suffixes:
        # Unicode superscripts survive a later HTML-to-Markdown conversion,
        # which would otherwise unwrap <sup> and flatten these references again.
        value = replace_once(
            value,
            (f"14C {suffix}", f"<sup>14</sup>C {suffix}"),
            f"¹⁴C {suffix}",
        )
    return value


def repair_ridgefield(value: str) -> str:
    fragment = "https://fragmentarium.ms/view/page/F-k0iy"
    cantus = "https://cantusdatabase.org/source/1000027"
    original_html = f'<a href="{fragment}"> Group G (Antiphoner):  <i></a>{cantus} </i>'
    corrected_html = f'<a href="{fragment}">Group G (Antiphoner):</a> <i>{cantus}</i>'
    if original_html in value or corrected_html in value:
        return replace_once(value, (original_html,), corrected_html)
    label = f"[Group G (Antiphoner):]({fragment})"
    return replace_once(value, (f"{label}{cantus}",), f"{label} *{cantus}*")


class Command(BaseCommand):
    help = (
        "Restore radiocarbon superscripts in source 123619 and Group G URL "
        "italics in source 714555. Dry-run unless --apply is supplied."
    )

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument("--apply", action="store_true", help="Apply the repairs.")

    def handle(self, *args: Any, **options: Any) -> None:
        apply = options["apply"]
        with transaction.atomic():
            queryset = Source.objects.filter(pk__in=(123619, 714555)).order_by("pk")
            if apply:
                # Read the latest fields after acquiring both row locks. Keep
                # them until the corrections and both revision snapshots commit.
                queryset = queryset.select_for_update()
            sources = {source.pk: source for source in queryset}
            if set(sources) != {123619, 714555}:
                raise CommandError("Both sources 123619 and 714555 must exist.")

            pending: dict[int, dict[str, str]] = {}
            for source_id, field, suffixes in (
                (123619, "description", ("Results [see below]",)),
                (
                    123619,
                    "selected_bibliography",
                    ("Results for M1250 [sic]", "Laboratoire"),
                ),
                (714555, "description", ()),
            ):
                before = getattr(sources[source_id], field)
                try:
                    if not before:
                        raise ValueError("The field is empty.")
                    after = (
                        repair_radiocarbon(before, suffixes)
                        if suffixes
                        else repair_ridgefield(before)
                    )
                except ValueError as error:
                    raise CommandError(
                        f"Source {source_id}, {field}: {error} No changes applied."
                    ) from error
                if before != after:
                    pending.setdefault(source_id, {})[field] = after
                    self.stdout.write(
                        "\n".join(
                            unified_diff(
                                before.splitlines(),
                                after.splitlines(),
                                fromfile=f"{source_id}/{field}/before",
                                tofile=f"{source_id}/{field}/after",
                                lineterm="",
                            )
                        )
                    )

            if apply and pending:
                # Store the current state as well as the repaired state, even
                # for a source that has never had a revision. QuerySet.update
                # intentionally avoids full_clean() on unrelated legacy fields
                # and preserves editorial timestamps and attribution. It emits
                # no save signal, so revision capture must be explicit.
                with reversion.create_revision():
                    reversion.set_comment("Before source editorial formatting repair")
                    for source_id in pending:
                        reversion.add_to_revision(sources[source_id])
                with reversion.create_revision():
                    reversion.set_comment(
                        "Restore radiocarbon superscripts and Ridgefield Group G italics"
                    )
                    for source_id, changes in pending.items():
                        Source.objects.filter(pk=source_id).update(**changes)
                        for field, value in changes.items():
                            setattr(sources[source_id], field, value)
                        reversion.add_to_revision(sources[source_id])

        action = "Updated" if apply else "Would update"
        self.stdout.write(f"{action} {len(pending)} source(s).")
        if not apply:
            self.stdout.write(
                "Dry run: no data changed. Use --apply to apply these repairs."
            )
