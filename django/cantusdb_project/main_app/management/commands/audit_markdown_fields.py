"""
Audits `Source.description` and `Source.selected_bibliography` for raw HTML
tags left over from legacy (pre-markdown) data entry.

Written for issue #1239 ("Source Detail: we should stop preserving
linebreaks in Description field"), where the team asked for "a list of
sources that have no html tags in their description as ones to take a
look at before/when this goes live" -- i.e. before the display template
is switched over to actually render markdown (see #1957, #1972).

Reports, for each of the two fields, which sources contain raw HTML tags
(candidates for cleanup/conversion) and which don't (safe to render as
markdown as-is).
"""

from django.core.management.base import BaseCommand

from main_app.models import Source
from main_app.templatetags.helper_tags import contains_html_tags

FIELDS = ["description", "selected_bibliography"]


def describe(source):
    return (
        f"  id={source.id}  siglum={source.siglum or '-'}  "
        f"shelfmark={source.shelfmark or '-'}  title={source.title or '-'}"
    )


class Command(BaseCommand):
    help = (
        "Report which Source.description / Source.selected_bibliography "
        "values contain raw HTML tags (legacy formatting) vs. plain "
        "text/markdown, ahead of wiring up markdown rendering (#1239)."
    )

    def handle(self, *args, **options):
        sources = Source.objects.all().only(
            "id", "published", "siglum", "shelfmark", "title", *FIELDS
        )

        # bucket[field][published][category] -> list of sources
        buckets = {
            field: {
                True: {"html": [], "no_html": [], "blank": []},
                False: {"html": [], "no_html": [], "blank": []},
            }
            for field in FIELDS
        }

        for source in sources:
            for field in FIELDS:
                value = getattr(source, field)
                bucket = buckets[field][source.published]
                if not value or not value.strip():
                    bucket["blank"].append(source)
                elif contains_html_tags(value):
                    bucket["html"].append(source)
                else:
                    bucket["no_html"].append(source)

        for field in FIELDS:
            published = buckets[field][True]
            unpublished = buckets[field][False]
            n_published = sum(len(v) for v in published.values())
            n_unpublished = sum(len(v) for v in unpublished.values())

            self.stdout.write(self.style.SUCCESS(f"\n=== {field.upper()} ==="))
            self.stdout.write(
                f"Published ({n_published}) | Unpublished ({n_unpublished})\n"
            )

            for label, group in (
                ("PUBLISHED", published),
                ("UNPUBLISHED", unpublished),
            ):
                self.stdout.write(f"--- {label} ---")
                self.stdout.write(
                    f"  contains raw HTML tags: {len(group['html'])}\n"
                    f"  plain text/markdown (no tags): {len(group['no_html'])}\n"
                    f"  blank: {len(group['blank'])}\n"
                )

                self.stdout.write(f"  -- WITH raw HTML tags ({len(group['html'])}) --")
                for source in group["html"]:
                    self.stdout.write(describe(source))

                self.stdout.write(
                    f"\n  -- WITHOUT raw HTML tags ({len(group['no_html'])}) --"
                )
                for source in group["no_html"]:
                    self.stdout.write(describe(source))
                self.stdout.write("")

        self.stdout.write(self.style.SUCCESS("\nDone."))
