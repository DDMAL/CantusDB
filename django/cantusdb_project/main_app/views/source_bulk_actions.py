"""
This module contains views that are used to make bulk additions or edits to chants
(or some subset of chants) associated with a particular source.
"""

from typing import Any, Optional
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.views.generic.edit import FormView
from django.views.generic.detail import SingleObjectMixin
from django.contrib.auth.mixins import UserPassesTestMixin
from django.urls import reverse
from django.db.models.query import QuerySet

from main_app.models import Source, Chant
from main_app.forms import AddImageLinksForm, ChantCreateFormset, ChantCreateCSVForm
from main_app.permissions import user_can_manage_source_editors


class AddImageLinksView(UserPassesTestMixin, SingleObjectMixin, FormView):  # type: ignore
    template_name = "source_bulk_add/add_image_links.html"
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

