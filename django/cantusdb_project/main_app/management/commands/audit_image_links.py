"""
Check which external image links still work (issue #2170).

Requests every source-level link (a source's image link and its source URLs:
IIIF manifests, host institution records, external images) and, for each
source, the first and last chant or sequence image link on each site. Most
broken links are broken for a whole source, so a sample per source is enough;
pass --all-chant-links to check every chant link (best with --source or --site).

Results are printed in the terminal, grouped by result, site and source:
- Broken: the site answered "not found" (404, 410) or another client error,
  the domain no longer exists, or the link isn't a valid web address.
- Couldn't reach: timeouts, connection errors and server errors. These are
  often temporary (e.g. manuscripta.at in November 2026), so rerun later
  before fixing anything.
- Blocked: the site refused the request (401, 403, 429).
- Not checked: sites that can't be checked automatically (see
  SITES_WE_CANNOT_CHECK); spot-check those by hand.

Each site gets one request at a time, with a pause between requests, so the
libraries' servers aren't flooded. Broken and unreachable links are tried
once more at the end before being reported. Nothing is changed in the database.

Usage:
    python manage.py audit_image_links
    python manage.py audit_image_links --source 123610 --all-chant-links
    python manage.py audit_image_links --site manuscripta.at --all-chant-links
"""

import argparse
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Iterable, Optional
from urllib.parse import urlparse

import requests
from django.core.management.base import BaseCommand
from django.db.models import Q

from main_app.models import Chant, Sequence, Source, SourceURL

USER_AGENT = "CantusDB image link audit (https://cantusdatabase.org)"

# Sites whose answers say nothing about whether a link works. They are listed
# in the report but not requested.
SITES_WE_CANNOT_CHECK = {
    "gallica.bnf.fr": "refuses automated requests, even for working links",
    "bvmm.irht.cnrs.fr": "doesn't answer automated requests",
    "unipub.uni-graz.at": "answers OK even for pages that don't exist",
}

WORKING = "working"
BROKEN = "broken"
UNREACHABLE = "unreachable"
BLOCKED = "blocked"
NOT_CHECKED = "not checked"


@dataclass
class Link:
    url: str
    site: str
    # (source id, kind of link), one entry per place the URL is used
    uses: set[tuple[int, str]] = field(default_factory=set)
    result: str = ""
    detail: str = ""


def site_of(url: str) -> str:
    try:
        return urlparse(url).netloc.lower()
    except ValueError:  # e.g. "https://[bad"
        return ""


def cannot_check(site: str) -> Optional[str]:
    for unchecked_site, reason in SITES_WE_CANNOT_CHECK.items():
        if site == unchecked_site or site.endswith("." + unchecked_site):
            return reason
    return None


def classify(status_code: int) -> str:
    if status_code < 400:
        return WORKING
    if status_code in (401, 403, 429):
        return BLOCKED
    if status_code >= 500:
        return UNREACHABLE
    return BROKEN


def check_url(session: requests.Session, url: str, timeout: float) -> tuple[str, str]:
    """Request `url` and return its result and a short detail for the report."""
    if not site_of(url) or urlparse(url).scheme not in ("http", "https"):
        return BROKEN, "not a web address"
    try:
        # GET rather than HEAD: many library viewers mishandle HEAD. The body
        # is streamed and never read.
        response = session.get(url, timeout=timeout, allow_redirects=True, stream=True)
        response.close()
    except requests.Timeout:
        return UNREACHABLE, "timed out"
    except requests.exceptions.SSLError:
        return UNREACHABLE, "certificate problem"
    except (requests.exceptions.InvalidURL, requests.exceptions.MissingSchema):
        return BROKEN, "not a web address"
    except requests.ConnectionError as error:
        if "NameResolution" in str(error) or "Failed to resolve" in str(error):
            # The domain no longer exists (checked twice before reporting).
            return BROKEN, "domain not found"
        return UNREACHABLE, "connection failed"
    except (requests.RequestException, ValueError) as error:
        return UNREACHABLE, type(error).__name__
    return classify(response.status_code), str(response.status_code)


class Command(BaseCommand):
    help = (
        "Check which external image links still work (issue #2170). "
        "Changes nothing; prints a report."
    )

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--source",
            type=int,
            action="append",
            metavar="ID",
            help="Only check this source (can be repeated).",
        )
        parser.add_argument(
            "--site",
            metavar="HOST",
            help="Only check links on this site, e.g. manuscripta.at.",
        )
        parser.add_argument(
            "--all-chant-links",
            action="store_true",
            help="Check every chant and sequence link instead of a sample per source.",
        )
        parser.add_argument(
            "--delay",
            type=float,
            default=1.0,
            help="Seconds to wait between requests to the same site (default 1).",
        )
        parser.add_argument(
            "--timeout",
            type=float,
            default=15.0,
            help="Seconds to wait for a site to answer (default 15).",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        links = self._collect(options["source"], options["all_chant_links"])
        if options["site"]:
            wanted = options["site"].lower()
            links = {
                url: link
                for url, link in links.items()
                if link.site == wanted or link.site.endswith("." + wanted)
            }

        to_check = []
        for link in links.values():
            if reason := cannot_check(link.site):
                link.result, link.detail = NOT_CHECKED, reason
            else:
                to_check.append(link)

        sites = {link.site for link in to_check}
        self.stderr.write(
            f"Checking {len(to_check)} link(s) on {len(sites)} site(s)..."
        )
        self._check(to_check, options["delay"], options["timeout"])

        # A site that refused the request will refuse it again.
        failed = [link for link in to_check if link.result in (BROKEN, UNREACHABLE)]
        if failed:
            self.stderr.write(f"Trying the {len(failed)} failed link(s) again...")
            self._check(failed, options["delay"], options["timeout"])

        self._report(links.values())

    def _collect(
        self, source_ids: Optional[list[int]], all_chant_links: bool
    ) -> dict[str, Link]:
        links: dict[str, Link] = {}

        def add(url: Optional[str], source_id: int, kind: str) -> None:
            url = (url or "").strip()
            if not url:
                return
            link = links.setdefault(url, Link(url=url, site=site_of(url)))
            link.uses.add((source_id, kind))

        sources = Source.objects.exclude(Q(image_link__isnull=True) | Q(image_link=""))
        source_urls = SourceURL.objects.all()
        if source_ids:
            sources = sources.filter(pk__in=source_ids)
            source_urls = source_urls.filter(source_id__in=source_ids)
        for source_id, url in sources.values_list("pk", "image_link"):
            add(url, source_id, "source image link")
        for source_id, url, url_type in source_urls.values_list(
            "source_id", "url", "url_type"
        ):
            add(url, source_id, f"source link ({SourceURL.URLTypes(url_type).label})")

        for model, order in ((Chant, "c_sequence"), (Sequence, "s_sequence")):
            rows = model.objects.exclude(
                Q(image_link__isnull=True) | Q(image_link="")
            ).order_by("source_id", "folio", order, "pk")
            if source_ids:
                rows = rows.filter(source_id__in=source_ids)
            kind = f"{model._meta.verbose_name} link"
            for source_id, url in self._chant_links(
                rows.values_list("source_id", "image_link").iterator(),
                all_chant_links,
            ):
                add(url, source_id, kind)
        return links

    @staticmethod
    def _chant_links(
        rows: Iterable[tuple[int, str]], all_chant_links: bool
    ) -> Iterable[tuple[int, str]]:
        """
        Yield (source id, url) for the chant links to check: all of them, or
        the first and last link on each site within each source.
        """
        if all_chant_links:
            seen = set()
            for row in rows:
                if row not in seen:
                    seen.add(row)
                    yield row
            return
        first_and_last: dict[tuple[int, str], list[str]] = {}
        for source_id, url in rows:
            key = (source_id, site_of(url.strip()))
            if key not in first_and_last:
                first_and_last[key] = [url, url]
            else:
                first_and_last[key][1] = url
        for (source_id, _site), urls in first_and_last.items():
            for url in dict.fromkeys(urls):
                yield source_id, url

    def _check(self, links: list[Link], delay: float, timeout: float) -> None:
        by_site: dict[str, list[Link]] = defaultdict(list)
        for link in links:
            by_site[link.site].append(link)

        def check_site(site_links: list[Link]) -> None:
            # One session per site: sessions aren't shared between threads.
            session = requests.Session()
            session.headers["User-Agent"] = USER_AGENT
            for index, link in enumerate(site_links):
                if index and delay:
                    time.sleep(delay)
                try:
                    link.result, link.detail = check_url(session, link.url, timeout)
                except Exception as error:  # one odd link mustn't stop the run
                    link.result, link.detail = UNREACHABLE, type(error).__name__

        # Sites are checked in parallel, but each site one request at a time.
        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(check_site, by_site.values()))

    def _list_links(self, links: list[Link], names: dict[int, str]) -> None:
        """One line per source and URL, naming every place the URL is used."""
        by_source: dict[int, dict[str, list[str]]] = defaultdict(dict)
        details = {}
        for link in links:
            details[link.url] = link.detail
            for source_id, kind in link.uses:
                by_source[source_id].setdefault(link.url, []).append(kind)
        for source_id, urls in sorted(by_source.items()):
            self.stdout.write(f"    source {source_id} ({names.get(source_id, '?')})")
            for url, kinds in urls.items():
                self.stdout.write(
                    f"      {url} [{details[url]}] ({', '.join(sorted(kinds))})"
                )

    def _report(self, links: Iterable[Link]) -> None:
        links = list(links)
        source_ids = {source_id for link in links for source_id, _ in link.uses}
        names = {
            source.pk: str(source)
            for source in Source.objects.filter(pk__in=source_ids).select_related(
                "holding_institution"
            )
        }
        # Broken and unreachable links are listed one by one, by site and
        # source. For blocked and unchecked sites the answer says nothing about
        # single links, so they get one line per site.
        sections = [
            (
                BROKEN,
                "BROKEN: the page or site doesn't exist, or the link is malformed",
                True,
            ),
            (UNREACHABLE, "COULDN'T REACH: often temporary, rerun before fixing", True),
            (BLOCKED, "BLOCKED: the site refused automated requests", False),
            (NOT_CHECKED, "NOT CHECKED: spot-check these by hand", False),
        ]
        for result, heading, list_links in sections:
            matching = [link for link in links if link.result == result]
            if not matching:
                continue
            self.stdout.write(f"\n{heading} ({len(matching)} link(s))")
            by_site: dict[str, list[Link]] = defaultdict(list)
            for link in matching:
                by_site[link.site].append(link)
            for site, site_links in sorted(by_site.items()):
                site_sources = {s for link in site_links for s, _ in link.uses}
                summary = f"  {site}: {len(site_links)} link(s) in {len(site_sources)} source(s)"
                if result == NOT_CHECKED:
                    summary += f"; {site_links[0].detail}"
                self.stdout.write(summary)
                if list_links:
                    self._list_links(site_links, names)

        counts = {
            result: sum(1 for link in links if link.result == result)
            for result in (WORKING, BROKEN, UNREACHABLE, BLOCKED, NOT_CHECKED)
        }
        self.stdout.write(
            self.style.SUCCESS(
                f"\n{len(links)} link(s): {counts[WORKING]} working, "
                f"{counts[BROKEN]} broken, {counts[UNREACHABLE]} couldn't reach, "
                f"{counts[BLOCKED]} blocked, {counts[NOT_CHECKED]} not checked."
            )
        )
