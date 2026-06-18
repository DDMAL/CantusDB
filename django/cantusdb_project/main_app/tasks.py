import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import timedelta
from typing import List, Dict, Any, Optional

import requests
from celery import shared_task, Task
from django.core.mail import EmailMessage
from django.db.models import Count, Q
from django.utils import timezone

from main_app.models import Chant, Sequence
from main_app.models.data_check_config import DataCheckConfig
from main_app.forms import BrowseChantsBulkEditFormset

CI_DOMAIN = "https://cantusindex.uwaterloo.ca"
CI_WORKERS = 10


def get_all_ci_ids() -> set[str] | None:
    """
    Fetches the full set of Cantus IDs from Cantus Index in a single request.
    Returns None if the request fails.
    """
    try:
        response = requests.get(
            "https://cantusindex.uwaterloo.ca/json-cids", timeout=30
        )
    except requests.exceptions.RequestException:
        return None

    if response.status_code != 200:
        return None

    text = response.text.encode().decode("utf-8-sig")
    data = json.loads(text)
    return {entry["cid"] for entry in data if isinstance(entry, dict)}


def check_cantus_ids_not_in_ci(chant_ids: Optional[List[int]] = None) -> dict:
    """
    Returns chants whose cantus_id does not exist in Cantus Index,
    split into published and unpublished.
    """
    ci_ids = get_all_ci_ids()
    if ci_ids is None:
        return {"published": None, "unpublished": None, "error": "Failed to fetch CI IDs"}

    qs = Chant.objects.filter(id__in=chant_ids) if chant_ids is not None else Chant.objects.all()

    local_ids: list[str] = list(
        qs.exclude(cantus_id__isnull=True)
        .exclude(cantus_id="")
        .values_list("cantus_id", flat=True)
        .distinct()
    )

    invalid_ids = {cid for cid in local_ids if cid not in ci_ids}

    base_qs = Chant.objects.filter(cantus_id__in=invalid_ids).select_related("source")
    return {
        "published": list(base_qs.filter(source__published=True).order_by("cantus_id")),
        "unpublished": list(base_qs.filter(source__published=False).order_by("cantus_id")),
    }


def check_duplicate_folio_sequence(chant_ids: Optional[List[int]] = None) -> dict:
    """
    Returns groups where (source, folio, sequence) is duplicated.
    Each row is one unique combination with a count of how many chants share it.
    """
    base_qs = Chant.objects.filter(id__in=chant_ids) if chant_ids is not None else Chant.objects.all()

    chant_dups = (
        base_qs.exclude(folio__isnull=True)
        .exclude(c_sequence__isnull=True)
        .values("source_id", "source__published", "folio", "c_sequence")
        .annotate(count=Count("id"))
        .filter(count__gt=1)
        .order_by("source_id", "folio", "c_sequence")
    )

    seq_dups = (
        Sequence.objects.exclude(folio__isnull=True)
        .exclude(s_sequence__isnull=True)
        .values("source_id", "source__published", "folio", "s_sequence")
        .annotate(count=Count("id"))
        .filter(count__gt=1)
        .order_by("source_id", "folio", "s_sequence")
    )

    published = [g for g in chant_dups if g["source__published"]] + \
                [g for g in seq_dups if g["source__published"]]
    unpublished = [g for g in chant_dups if not g["source__published"]] + \
                  [g for g in seq_dups if not g["source__published"]]

    return {"published": published, "unpublished": unpublished}


def _fetch_ci_genre(cantus_id: str) -> tuple[str, Optional[str]]:
    """Fetch the genre for a single cantus_id from CI. Returns (cantus_id, genre_or_None)."""
    try:
        response = requests.get(f"{CI_DOMAIN}/json-cid/{cantus_id}", timeout=10)
        if response.status_code == 200:
            text = response.text.encode().decode("utf-8-sig")
            data = json.loads(text)
            if isinstance(data, dict) and data.get("info"):
                return cantus_id, data["info"].get("field_genre")
    except requests.exceptions.RequestException:
        pass
    return cantus_id, None


def check_cantus_ids_genre_mismatch(chant_ids: Optional[List[int]] = None) -> dict:
    """
    Returns chants where the genre stored in CantusDB does not match
    the genre CI has for the same cantus_id, split into published and unpublished.

    Uses 10 parallel workers to fetch CI genres efficiently.
    """
    qs = Chant.objects.filter(id__in=chant_ids) if chant_ids is not None else Chant.objects.all()

    ci_ids = get_all_ci_ids()
    if ci_ids is None:
        return {"published": None, "unpublished": None, "error": "Failed to fetch CI IDs"}

    # Collect distinct (cantus_id, local_genre) pairs, limited to IDs that exist in CI
    pairs = list(
        qs.exclude(cantus_id__isnull=True)
        .exclude(cantus_id="")
        .exclude(genre__isnull=True)
        .filter(cantus_id__in=ci_ids)
        .values_list("cantus_id", "genre__name")
        .distinct()
    )
    local_genres: dict[str, str] = {cid: genre for cid, genre in pairs}

    # Fetch CI genres in parallel
    ci_genres: dict[str, Optional[str]] = {}
    with ThreadPoolExecutor(max_workers=CI_WORKERS) as executor:
        futures = {executor.submit(_fetch_ci_genre, cid): cid for cid in local_genres}
        for future in as_completed(futures):
            cid, ci_genre = future.result()
            ci_genres[cid] = ci_genre

    # Build a Q filter for chants where their specific (cantus_id, genre) pair mismatches CI
    mismatch_q = Q()
    for cid, local_genre in local_genres.items():
        ci_genre = ci_genres.get(cid)
        if ci_genre is not None and ci_genre != local_genre:
            mismatch_q |= Q(cantus_id=cid, genre__name=local_genre)

    if not mismatch_q:
        return {"published": [], "unpublished": []}

    base_qs = (
        Chant.objects.filter(mismatch_q)
        .select_related("source", "genre")
        .order_by("cantus_id")
    )
    return {
        "published": list(base_qs.filter(source__published=True)),
        "unpublished": list(base_qs.filter(source__published=False)),
    }


def check_position_service_mismatch(chant_ids: Optional[List[int]] = None) -> dict:
    """
    Flags chants where position and service are inconsistent:
      - position "M" must only appear in Vespers (service V or V2)
      - position "B" must only appear in Lauds (service L)
    Split into published and unpublished.
    """
    qs = Chant.objects.filter(id__in=chant_ids) if chant_ids is not None else Chant.objects.all()

    invalid = qs.filter(
        Q(position="M") & ~Q(service__name__in=["V", "V2"]) |
        Q(position="B") & ~Q(service__name="L")
    ).select_related("source", "service")

    return {
        "published": list(invalid.filter(source__published=True).order_by("position", "source_id")),
        "unpublished": list(invalid.filter(source__published=False).order_by("position", "source_id")),
    }


def check_blank_cantus_id(chant_ids: Optional[List[int]] = None) -> dict:
    """
    Returns chants with a blank or null cantus_id, split into published and unpublished.
    """
    qs = Chant.objects.filter(id__in=chant_ids) if chant_ids is not None else Chant.objects.all()
    invalid = qs.filter(Q(cantus_id__isnull=True) | Q(cantus_id="")).select_related("source")
    return {
        "published": list(invalid.filter(source__published=True).order_by("source_id")),
        "unpublished": list(invalid.filter(source__published=False).order_by("source_id")),
    }


def check_blank_mode(chant_ids: Optional[List[int]] = None) -> dict:
    """
    Returns chants with a blank or null mode field, split into published and unpublished.
    """
    qs = Chant.objects.filter(id__in=chant_ids) if chant_ids is not None else Chant.objects.all()
    invalid = qs.filter(Q(mode__isnull=True) | Q(mode="")).select_related("source")
    return {
        "published": list(invalid.filter(source__published=True).order_by("source_id")),
        "unpublished": list(invalid.filter(source__published=False).order_by("source_id")),
    }


FREQUENCY_DELTAS = {
    "daily": timedelta(days=1),
    "weekly": timedelta(weeks=1),
    "monthly": timedelta(days=30),
}

CHECK_LABELS = {
    "cantus_ids_not_in_ci": "Cantus IDs not found in Cantus Index",
    "duplicate_folio_sequence": "Duplicate folio/sequence numbers",
    "genre_mismatch": "Genre mismatch with Cantus Index",
    "position_service_mismatch": "Position/service mismatch",
    "blank_cantus_id": "Blank Cantus ID",
    "blank_mode": "Blank mode",
}


def _format_check_attachment(label: str, result: dict) -> str:
    lines = [label, "=" * len(label), ""]

    if "error" in result:
        lines.append(f"ERROR: {result['error']}")
        return "\n".join(lines)

    for section in ("published", "unpublished"):
        items = result.get(section) or []
        lines.append(f"--- {section.capitalize()} ({len(items)}) ---")
        if not items:
            lines.append("No issues found.")
        else:
            for item in items:
                if isinstance(item, dict):
                    # duplicate folio/sequence results are dicts
                    lines.append(
                        f"  source_id={item.get('source_id')}  "
                        f"folio={item.get('folio')}  "
                        f"sequence={item.get('c_sequence', item.get('s_sequence'))}  "
                        f"count={item.get('count')}"
                    )
                else:
                    # Chant model instances
                    lines.append(
                        f"  chant_id={item.id}  "
                        f"source={getattr(item.source, 'siglum', item.source_id)}  "
                        f"folio={item.folio}  "
                        f"cantus_id={item.cantus_id}  "
                        f"genre={getattr(item.genre, 'name', '')}  "
                        f"mode={item.mode}"
                    )
        lines.append("")

    return "\n".join(lines)


@shared_task(name="cantusdb.run_data_checks")
def run_data_checks() -> None:
    config = DataCheckConfig.objects.order_by("-id").first()
    if config is None:
        return

    now = timezone.now()

    # Skip if not enough time has passed since the last run
    if config.last_run is not None:
        delta = FREQUENCY_DELTAS.get(config.frequency)
        if delta and now - config.last_run < delta:
            return

    # Determine which chants to check
    chant_ids = None
    if config.scope == "edited" and config.last_run is not None:
        chant_ids = list(
            Chant.objects.filter(date_updated__gte=config.last_run)
            .values_list("id", flat=True)
        )

    # Run all checks
    results = {
        "cantus_ids_not_in_ci": check_cantus_ids_not_in_ci(chant_ids),
        "duplicate_folio_sequence": check_duplicate_folio_sequence(chant_ids),
        "genre_mismatch": check_cantus_ids_genre_mismatch(chant_ids),
        "position_service_mismatch": check_position_service_mismatch(chant_ids),
        "blank_cantus_id": check_blank_cantus_id(chant_ids),
        "blank_mode": check_blank_mode(chant_ids),
    }

    # Update last_run before sending so a mail failure doesn't trigger a re-run
    DataCheckConfig.objects.filter(pk=config.pk).update(last_run=now)

    recipients = [r.strip() for r in config.recipients.split(",") if r.strip()]
    if not recipients:
        return

    date_str = now.strftime("%Y-%m-%d")
    scope_note = (
        f"Scope: records edited since {config.last_run.strftime('%Y-%m-%d')}"
        if config.scope == "edited" and config.last_run
        else "Scope: all records"
    )

    email = EmailMessage(
        subject=f"CantusDB Data Check Report — {date_str}",
        body=f"CantusDB Data Check Report — {date_str}\n{scope_note}\n\nSee attached files for full results.",
        to=recipients,
    )

    for key, label in CHECK_LABELS.items():
        content = _format_check_attachment(label, results[key])
        filename = f"{key}_{date_str}.txt"
        email.attach(filename, content, "text/plain")

    email.send()


@shared_task(name="cantusdb.save_browse_chants_formset", bind=True)
def save_browse_chants_formset(
    self: Task, data: Dict[str, Any], chant_ids: List[int]
) -> Dict[str, Any]:
    self.update_state(state="PROCESSING")
    chants = Chant.objects.filter(id__in=chant_ids)
    formset = BrowseChantsBulkEditFormset(data=data, queryset=chants)
    if formset.is_valid():
        formset.save()
    non_form_errors = formset.non_form_errors().get_json_data(escape_html=True)
    form_errors = []
    for form_num, errors in enumerate(formset.errors):
        if errors:
            json_errors = errors.get_json_data(escape_html=True)
            form_errors.extend(
                [
                    (form_num, field, err[0]["message"])
                    for field, err in json_errors.items()
                ]
            )
    return {
        "non_form_errors": non_form_errors,
        "form_errors": form_errors,
        "error_count": formset.total_error_count(),
    }
