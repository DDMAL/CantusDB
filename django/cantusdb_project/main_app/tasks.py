import json
from typing import List, Dict, Any

import requests
from celery import shared_task, Task
from django.db.models import Count

from main_app.models import Chant
from main_app.forms import BrowseChantsBulkEditFormset


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


def check_cantus_ids_not_in_ci() -> dict:
    """
    Returns chants whose cantus_id does not exist in Cantus Index,
    split into published and unpublished.

    Returns None values for published/unpublished if the CI request fails.
    """
    ci_ids = get_all_ci_ids()
    if ci_ids is None:
        return {"published": None, "unpublished": None, "error": "Failed to fetch CI IDs"}

    local_ids: list[str] = list(
        Chant.objects.exclude(cantus_id__isnull=True)
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
