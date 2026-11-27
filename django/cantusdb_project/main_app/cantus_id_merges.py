"""
Cantus IDs that Cantus Index has merged into another one (issue #2197).

Cantus Index lists every merge at /json-merged-chants: an old Cantus ID, the
ID it was merged into, and the date. Some merges were later merged again
(A into B, then B into C), so each old ID is followed to the ID it ends up as.
A few old IDs were merged into more than one ID; those need a person.

Used by the audit_merged_cantus_ids command (a report of every record that
still uses a merged ID) and by the data checks, which replace the IDs of
merges made since settings.CANTUS_ID_MERGES_SINCE. Earlier merges are left
for the editors: some old IDs were reused on purpose.
"""

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Optional

import reversion  # type: ignore[import-untyped]
from django.conf import settings
from django.db import transaction

from cantusindex import get_merged_cantus_ids
from main_app.models import Chant, Sequence, Source

# The list is about 170 KB; Cantus Index can take a while to send it.
FETCH_TIMEOUT = 60


@dataclass
class Merge:
    old: str
    # the ID(s) Cantus Index merged `old` into, with the date of each merge
    new: dict[str, str] = field(default_factory=dict)

    @property
    def ambiguous(self) -> bool:
        return len(self.new) > 1


def _merge_date(value: Any) -> Optional[date]:
    try:
        return date.fromisoformat(str(value))
    except ValueError:  # e.g. "0000-00-00"
        return None


def read_merges(events: list[Any], since: Optional[date] = None) -> dict[str, Merge]:
    """Group Cantus Index's merge events by old Cantus ID; with `since`, keep
    only merges made on or after that date."""
    merges: dict[str, Merge] = {}
    for event in events:
        if not isinstance(event, dict):
            continue
        old = str(event.get("old") or "").strip()
        new = str(event.get("new") or "").strip()
        if not old or not new or old == new:
            continue
        if since is not None:
            made = _merge_date(event.get("date"))
            if made is None or made < since:
                continue
        merge = merges.setdefault(old, Merge(old))
        merge.new[new] = str(event.get("date") or "")
    return merges


def follow(old: str, merges: dict[str, Merge]) -> tuple[list[str], str]:
    """
    Follow `old` through later merges to the ID it ends up as.

    Returns the chain of IDs (starting with `old`) and a note: "" when the
    chain ends at a single ID, otherwise why it stops early (an ID merged into
    more than one ID, or a loop).
    """
    chain = [old]
    while chain[-1] in merges:
        merge = merges[chain[-1]]
        if merge.ambiguous:
            options = ", ".join(sorted(merge.new))
            return chain, f"{merge.old} was merged into more than one ID ({options})"
        (next_id,) = merge.new
        if next_id in chain:
            return chain, "the merges form a loop"
        chain.append(next_id)
    return chain, ""


def records_using(
    merges: dict[str, Merge], include_sequences: bool, source_id: Optional[int] = None
) -> list[dict[str, Any]]:
    """Every chant (and sequence) whose Cantus ID is an old ID in `merges`,
    with the ID it should become ("" when someone has to choose)."""
    models = [(Chant, "chant", "c_sequence")]
    if include_sequences:
        models.append((Sequence, "sequence", "s_sequence"))
    rows = []
    for model, kind, order_field in models:
        records = model.objects.filter(cantus_id__in=list(merges))
        if source_id is not None:
            records = records.filter(source_id=source_id)
        for record in records.values(
            "id", "cantus_id", "folio", order_field, "incipit", "source_id"
        ):
            chain, note = follow(record["cantus_id"], merges)
            rows.append(
                {
                    "kind": kind,
                    "id": record["id"],
                    "source_id": record["source_id"],
                    "folio": record["folio"] or "",
                    "order": record[order_field] or "",
                    "incipit": record["incipit"] or "",
                    "cantus_id": record["cantus_id"],
                    "new_cantus_id": "" if note else chain[-1],
                    "chain": " → ".join(chain),
                    "merged": ", ".join(sorted(set(merges[chain[0]].new.values()))),
                    "note": note,
                }
            )

    sources = Source.objects.select_related("holding_institution").in_bulk(
        {row["source_id"] for row in rows}
    )
    for row in rows:
        source = sources.get(row["source_id"])
        row["source"] = source.short_heading if source else ""
        row["published"] = bool(source and source.published)
    rows.sort(key=lambda row: (row["cantus_id"], row["source"], row["kind"], row["id"]))
    return rows


def replace_merged_cantus_ids() -> dict[str, Any]:
    """
    Replace the Cantus IDs of merges made since settings.CANTUS_ID_MERGES_SINCE.

    Each changed record gets its own "before" and "after" revision, and only
    the Cantus ID is written, so last-modified dates stay as they were.
    Returns the records replaced, those that need a person (merged into more
    than one ID) and an error message if Cantus Index couldn't be reached.
    """
    events = get_merged_cantus_ids(timeout=FETCH_TIMEOUT)
    if not events:
        return {
            "replaced": [],
            "needs_decision": [],
            "error": "Couldn't get the list of merged Cantus IDs from Cantus Index.",
        }
    merges = read_merges(events, since=settings.CANTUS_ID_MERGES_SINCE)
    rows = records_using(merges, settings.CANTUS_ID_MERGES_INCLUDE_SEQUENCES)
    replaced = [row for row in rows if row["new_cantus_id"]]
    needs_decision = [row for row in rows if not row["new_cantus_id"]]

    with transaction.atomic():
        for model, kind in ((Chant, "chant"), (Sequence, "sequence")):
            new_ids = {
                row["id"]: row["new_cantus_id"]
                for row in replaced
                if row["kind"] == kind
            }
            if not new_ids:
                continue
            # lock the rows, and skip any whose ID changed since they were read
            records = list(
                model.objects.select_for_update().filter(
                    id__in=new_ids,
                    cantus_id__in=list(merges),
                )
            )
            for record in records:
                with reversion.create_revision():
                    reversion.set_comment("Merged Cantus ID: before (issue #2197)")
                    reversion.add_to_revision(record)
                record.cantus_id = new_ids[record.id]
                with reversion.create_revision():
                    reversion.set_comment(
                        "Merged Cantus ID replaced from Cantus Index (issue #2197)"
                    )
                    reversion.add_to_revision(record)
            # bulk_update writes only the Cantus ID and skips save(), so the
            # records' and sources' last-modified dates are left alone
            model.objects.bulk_update(records, ["cantus_id"], batch_size=500)
            changed = {record.id for record in records}
            replaced = [
                row for row in replaced if row["kind"] != kind or row["id"] in changed
            ]
    return {"replaced": replaced, "needs_decision": needs_decision, "error": None}
