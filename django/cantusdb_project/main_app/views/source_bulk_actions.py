"""
This module contains views that are used to make bulk additions or edits to chants
(or some subset of chants) associated with a particular source.
"""

from typing import Any, Optional
from django.http import (
    HttpRequest,
    HttpResponse,
    HttpResponseRedirect,
    JsonResponse,
)
from django.views.generic.edit import FormView
from django.views.generic.detail import SingleObjectMixin
from django.contrib import messages
from django.contrib.auth.mixins import UserPassesTestMixin
from django.urls import reverse
from django.db.models.query import QuerySet
from django.forms.models import BaseInlineFormSet

from main_app.models import Source, Chant
from main_app.forms import AddImageLinksForm, ChantCreateFormset, ChantCreateFromCSVForm
from main_app.permissions import user_can_manage_source_editors


class AddImageLinksView(UserPassesTestMixin, SingleObjectMixin, FormView):  # type: ignore
    template_name = "source_bulk_actions/add_image_links.html"
    pk_url_kwarg = "source_id"
    queryset = Source.objects.select_related("holding_institution")
    context_object_name = "source"
    form_class = AddImageLinksForm
    object: Source
    http_method_names = ["get", "post"]

    def test_func(self) -> bool:
        return user_can_manage_source_editors(self.request.user)

    def get_success_url(self) -> str:
        return reverse("source-detail", args=[self.object.id])

    def get(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        self.object = self.get_object()
        return super().get(request, *args, **kwargs)

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        self.object = self.get_object()
        return super().post(request, *args, **kwargs)

    def get_initial(self) -> dict[str, Any]:
        """
        Set the initial data required by the ImageLinkForm
        on GET requests.
        """
        folios: QuerySet[Chant, Optional[str]] = (
            self.object.chant_set.values_list("folio", flat=True)
            .distinct()
            .order_by("folio")
        )
        return {folio: "" for folio in folios if folio}

    def form_valid(self, form: AddImageLinksForm) -> HttpResponseRedirect:
        """
        Save the image links to the database.
        """
        form.save(self.object)
        return HttpResponseRedirect(self.get_success_url())


class AddChantsView(UserPassesTestMixin, SingleObjectMixin, FormView):  # type: ignore
    template_name = "source_bulk_actions/add_chants.html"
    http_method_names = ["get", "post"]
    pk_url_kwarg = "source_id"
    queryset = Source.objects.select_related("holding_institution")
    context_object_name = "source"
    object: Source
    form_class = ChantCreateFromCSVForm
    # The field_name map is used to map field names in the CSV file to
    # field names on the Chant model.
    field_name_map = {
        "sequence": "c_sequence",
        "full_text_std_spelling": "manuscript_full_text_std_spelling",
        "full_text_source_spelling": "manuscript_full_text",
    }

    def get_success_url(self) -> str:
        return reverse("browse-chants", args=[self.object.id])

    def test_func(self) -> bool:
        return user_can_manage_source_editors(self.request.user)

    def get(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        """
        The default `FormView` get method does not call the `SingleObjectMixin`
        `get_object` method, so we need to call it manually.
        """
        self.object = self.get_object()
        return super().get(request, *args, **kwargs)

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        """
        The default `FormView` post method does not call the `SingleObjectMixin`
        `get_object` method, so we need to call it manually.
        """
        self.object = self.get_object()
        return super().post(request, *args, **kwargs)

    def form_valid(self, form: ChantCreateFromCSVForm) -> HttpResponse:
        """
        If the form is valid, we need to save the new chants to the database.
        For this, we create a formset with the data from the ChantCreateCSVForm's
        cleaned and validated data.

        We use the ChantCreateFromCSVForm (which puts all new chant data in a single
        JSON Field) since otherwise we would quickly run into an issue with having
        too many fields (governed by the DATA_UPLOAD_MAX_NUMBER_FILES setting, because
        of how the form data is encoded client-side) in the form. Rather than fine-tune
        that setting to account for the varying number of chants that could be added and
        dealing with formset management on the front-end, we use this single-field form.
        """
        chant_data = form.cleaned_data["new_chants"]
        # Add the management form data to the formset data
        formset_data = {
            "chant_set-TOTAL_FORMS": len(chant_data),
            "chant_set-INITIAL_FORMS": 0,
        }
        form_count = 0
        for chant in chant_data:
            for key, value in chant.items():
                mapped_field_name = self.field_name_map.get(key, key)
                formset_data[f"chant_set-{form_count}-{mapped_field_name}"] = value
            form_count += 1
        new_chant_formset = ChantCreateFormset(formset_data, instance=self.object)
        if new_chant_formset.is_valid():
            new_chant_formset.save()
            messages.success(self.request, f"{form_count} chants added successfully.")
            return HttpResponseRedirect(self.get_success_url())
        return self.chant_formset_invalid(new_chant_formset)

    def form_invalid(self, form: ChantCreateFromCSVForm) -> HttpResponse:
        """
        If the form is invalid, we'll pass back a 400 response.
        """
        return JsonResponse(
            status=400,
            data={"form_error": "The submitted form is invalid. Please try again."},
        )

    def chant_formset_invalid(
        self, formset: BaseInlineFormSet  # type: ignore[type-arg]
    ) -> HttpResponse:
        """
        If the formset is invalid, we'll pass back errors in the response
        to be displayed to the user.
        """
        # Errors will reference the model field names, so we need to map them
        # back to the field names in the CSV file for display.
        errors_list = []
        swapped_field_name_map = {v: k for k, v in self.field_name_map.items()}
        for form_idx, form_errors in enumerate(formset.errors):
            if form_errors:
                for (
                    field_name,
                    error,
                ) in form_errors.items():  # type:ignore[attr-defined]
                    mapped_field_name = swapped_field_name_map.get(
                        field_name, field_name
                    )
                    errors_list.append(
                        {
                            "form_idx": form_idx,
                            "field_name": mapped_field_name,
                            "error": error,
                        }
                    )
        return JsonResponse(
            status=400,
            data={"formset_errors": errors_list},
        )
