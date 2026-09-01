from typing import Dict, Any

from django.views.generic import DetailView, ListView, UpdateView
from django.db.models import Q, QuerySet
from django.contrib import messages
from django.http import HttpResponse

from main_app.forms import SequenceEditForm
from main_app.models import Sequence
from main_app.permissions import CustomAccessMixin


class SequenceDetailView(CustomAccessMixin, DetailView):  # type: ignore[type-arg]
    """
    Displays a single Sequence object. Accessed with ``sequences/<int:pk>``
    """

    model = Sequence
    context_object_name = "sequence"
    template_name = "sequence_detail.html"

    def test_func(self) -> bool:
        sequence = self.get_object()
        source = sequence.source
        return (
            source.published
            or self.user_assigned_to_source(source)
            or self.user_is_global_viewer
        )

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        sequence = context["sequence"]
        context["concordances"] = (
            Sequence.objects.select_related("source__holding_institution")
            .filter(cantus_id=sequence.cantus_id)
            .select_related("source")
            .order_by("siglum")
        )

        context["user_can_edit_sequence"] = self.user_can_edit_chants(sequence.source)
        return context


class SequenceListView(CustomAccessMixin, ListView):  # type: ignore[type-arg]
    """
    Displays a list of Sequence objects. Accessed with ``sequences/``
    """

    paginate_by = 100
    context_object_name = "sequences"
    template_name = "sequence_list.html"
    test_req = False

    def get_queryset(self) -> QuerySet[Sequence]:
        if self.user.is_superuser or self.user_is_global_viewer:
            queryset = Sequence.objects.select_related("source__holding_institution")
        else:
            queryset = Sequence.objects.select_related(
                "source__holding_institution"
            ).filter(source__in=self.published_and_assigned_sources)

        q_obj_filter = Q()

        if self.request.GET.get("incipit"):
            incipit = self.request.GET.get("incipit")
            q_obj_filter &= Q(incipit__icontains=incipit)
        if self.request.GET.get("siglum"):
            siglum = self.request.GET.get("siglum")
            q_obj_filter &= Q(siglum__icontains=siglum)
        if self.request.GET.get("cantus_id"):
            cantus_id = self.request.GET.get("cantus_id")
            q_obj_filter &= Q(cantus_id__icontains=cantus_id)

        return queryset.filter(q_obj_filter).order_by(
            "source__holding_institution__siglum",
            "source__shelfmark",
            "folio",
            "s_sequence",
        )


class SequenceEditView(CustomAccessMixin, UpdateView):  # type: ignore[type-arg]
    template_name = "sequence_edit.html"
    model = Sequence
    form_class = SequenceEditForm
    pk_url_kwarg = "sequence_id"

    def form_valid(self, form: SequenceEditForm) -> HttpResponse:
        form.instance.last_updated_by = self.request.user
        messages.success(
            self.request,
            "Sequence updated successfully!",
        )
        return super().form_valid(form)

    def test_func(self) -> bool:
        sequence = self.get_object()
        source = sequence.source
        return self.user_can_edit_chants(source)
