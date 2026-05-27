import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Optional

import requests
from celery import shared_task, Task
from django.db.models import Count, Q

from main_app.models import Chant, Sequence
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
