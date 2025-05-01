from typing import List, Dict, Any

from celery import shared_task, Task

from main_app.models import Chant
from main_app.forms import BrowseChantsBulkEditFormset


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
